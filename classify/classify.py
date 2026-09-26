"""
Topic Classifier & OCR Spacing Fixer for Question Bank Markdown files.
Uses OpenRouter API (defaults to google/gemini-2.5-flash-lite for ultra-low token cost and reliable output)
with batching to:
1. Fix OCR spacing issues in both Question text and Options (optional interactive mode)
2. Classify questions strictly into predefined topics
3. Rebuild the Markdown Topic Index and rearrange questions sorted by topic.
"""

import os
import re
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Any

# Try loading from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also load from classify/.env if present
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# Default model set to Qwen 2.5 72B Instruct for high-accuracy reasoning on State PSC syllabi
DEFAULT_MODEL = "qwen/qwen-2.5-72b-instruct"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_topic_hierarchy(topics_path: str) -> Dict[str, List[str]]:
    """
    Loads topic and subtopic hierarchy from a topics.md file.
    Returns:
        Ordered dict { topic: [subtopic1, subtopic2, ...] }
    If the file only has flat topics without subtopics, values will be empty lists.
    """
    p = Path(topics_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Topics file not found: {topics_path}")

    hierarchy = {}
    current_topic = None

    with open(p, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            # Skip title lines like # Topics ...
            if line.startswith("# ") and not line.startswith("### "):
                continue

            # Check if this is a topic heading (### Topic)
            if line.startswith("### "):
                clean_topic = re.sub(r"^###\s*", "", line).strip()
                clean_topic = clean_topic.strip("`").strip()
                if clean_topic:
                    current_topic = clean_topic
                    if current_topic not in hierarchy:
                        hierarchy[current_topic] = []
                continue

            # Check if this is a subtopic bullet under current_topic
            if (line.startswith("- ") or line.startswith("* ")) and current_topic:
                sub = re.sub(r"^(\-|\*)\s*", "", line).strip().strip("`").strip()
                if sub and not sub.startswith("---") and sub not in hierarchy[current_topic]:
                    hierarchy[current_topic].append(sub)
                continue

            # Flat fallback: numbered or bullet item before or without any ### heading
            flat_item = re.sub(r"^#+\s*", "", line).strip()
            flat_item = re.sub(r"^(\d+\.|\-|\*)\s*", "", flat_item).strip().strip("`").strip()
            if not flat_item or flat_item.startswith("---") or flat_item.lower().startswith("markdown tag") or flat_item.lower().startswith("all topics") or "topics for classification" in flat_item.lower():
                continue

            # If no heading was seen yet, treat as flat topic
            if current_topic is None:
                if flat_item not in hierarchy:
                    hierarchy[flat_item] = []

    if not hierarchy:
        raise ValueError(f"No valid topics could be extracted from {topics_path}")

    return hierarchy


def load_topics(topics_path: str) -> List[str]:
    """
    Loads flat topic names from a topics.md or topics.txt file.
    Accepts:
    - Markdown headings (### Topic)
    - Markdown lists (- Topic, * Topic, 1. Topic)
    - Plain text lines
    Maintains 100% backward compatibility for functions expecting List[str].
    """
    hierarchy = load_topic_hierarchy(topics_path)
    return list(hierarchy.keys())



def parse_markdown_questions(md_content: str) -> List[Dict]:
    """
    Parses questions from standard markdown format.
    Preserves raw options text, parsed options dict {key: text}, and entire question block.
    """
    q_blocks = re.split(r"^## Question\s+(\d+)", md_content, flags=re.MULTILINE)
    questions = []

    for i in range(1, len(q_blocks), 2):
        q_num = int(q_blocks[i])
        raw_text = q_blocks[i + 1]

        # Extract existing topic & subtopic
        top_match = re.search(r"\*\*Topic:\*\*\s*(.+)", raw_text)
        curr_topic = top_match.group(1).strip() if top_match else ""

        sub_match = re.search(r"\*\*Subtopic:\*\*\s*(.+)", raw_text)
        curr_subtopic = sub_match.group(1).strip() if sub_match else ""

        # Extract Question text
        q_match = re.search(r"### Question\s*\n\s*([\s\S]*?)(?=\n### Options|\n### Answer|\n### Exam|\n---|\Z)", raw_text)
        q_text = q_match.group(1).strip() if q_match else ""

        # Extract Options section text
        opts_match = re.search(r"### Options\s*\n\s*([\s\S]*?)(?=\n### Answer|\n### Exam|\n---|\Z)", raw_text)
        opts_raw = opts_match.group(1).strip() if opts_match else ""

        # Parse options into key -> text mapping
        opts_dict = {}
        for opt_line in opts_raw.splitlines():
            line_str = opt_line.strip()
            if not line_str:
                continue
            opt_m = re.match(r"^(\(?\d+\)?|[a-dA-D]\.|\d+\.)\s*(.*)$", line_str)
            if opt_m:
                key = re.sub(r"[^\w]", "", opt_m.group(1))
                text = opt_m.group(2).strip()
                opts_dict[key] = text

        questions.append({
            "num": q_num,
            "topic": curr_topic,
            "subtopic": curr_subtopic,
            "text": q_text,
            "options_raw": opts_raw,
            "options_dict": opts_dict
        })

    return questions


def call_openrouter(prompt_content: str, system_prompt: str, api_key: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/appsc-loaded",
        "X-Title": "APPSC Question Classifier & Spacing Formatter"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_content}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    max_retries = 8
    for attempt in range(max_retries):
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        
        # On rate limit (429) or transient provider errors (500, 502, 503, 504), wait and retry
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
            wait_time = min(45, (2 ** attempt) * 2 + 3)
            print(f"  [Rate Limit / Transient {resp.status_code}] Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait_time)
            continue

        raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text}")


def build_classification_prompt_context(topics: Any) -> Tuple[str, bool, Dict[str, List[str]]]:
    """
    Determines if topics parameter contains subtopics.
    topics can be List[str] or Dict[str, List[str]].
    Returns (topics_list_str, has_subtopics, hierarchy)
    """
    if isinstance(topics, dict):
        hierarchy = topics
    else:
        hierarchy = {t: [] for t in topics}

    has_subtopics = any(bool(subs) for subs in hierarchy.values())

    lines = []
    for top, subs in hierarchy.items():
        if subs:
            subs_fmt = ", ".join(subs)
            lines.append(f"- {top} (Subtopics: {subs_fmt})")
        else:
            lines.append(f"- {top}")

    topics_list_str = "\n".join(lines)
    return topics_list_str, has_subtopics, hierarchy


def match_best_topic_and_subtopic(
    raw_topic: str,
    raw_subtopic: Optional[str],
    hierarchy: Dict[str, List[str]]
) -> Tuple[str, Optional[str]]:
    """
    Matches raw strings from LLM to canonical topic and subtopic.
    """
    topic_list = list(hierarchy.keys())
    if not topic_list:
        return raw_topic, raw_subtopic

    topic_set = set(topic_list)
    topic_lower_map = {t.lower(): t for t in topic_list}
    def _alnum(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(s).lower())
    topic_alnum_map = {_alnum(t): t for t in topic_list}

    assigned_topic = topic_list[0]
    raw_topic_str = str(raw_topic or "").strip()

    if raw_topic_str in topic_set:
        assigned_topic = raw_topic_str
    elif raw_topic_str.lower() in topic_lower_map:
        assigned_topic = topic_lower_map[raw_topic_str.lower()]
    elif _alnum(raw_topic_str) in topic_alnum_map:
        assigned_topic = topic_alnum_map[_alnum(raw_topic_str)]
    else:
        for t in topic_list:
            if t.lower() in raw_topic_str.lower() or raw_topic_str.lower() in t.lower():
                assigned_topic = t
                break

    valid_subs = hierarchy.get(assigned_topic, [])
    if not valid_subs:
        return assigned_topic, None

    if not raw_subtopic:
        return assigned_topic, valid_subs[0]

    raw_sub_str = str(raw_subtopic).strip()
    sub_set = set(valid_subs)
    sub_lower_map = {s.lower(): s for s in valid_subs}
    sub_alnum_map = {_alnum(s): s for s in valid_subs}

    if raw_sub_str in sub_set:
        return assigned_topic, raw_sub_str
    elif raw_sub_str.lower() in sub_lower_map:
        return assigned_topic, sub_lower_map[raw_sub_str.lower()]
    elif _alnum(raw_sub_str) in sub_alnum_map:
        return assigned_topic, sub_alnum_map[_alnum(raw_sub_str)]
    else:
        for s in valid_subs:
            if s.lower() in raw_sub_str.lower() or raw_sub_str.lower() in s.lower():
                return assigned_topic, s

    return assigned_topic, valid_subs[0]


def classify_only_batch(batch: List[Dict], topics: Any, api_key: str, model: str) -> Dict[int, Dict[str, Any]]:
    """
    Sends minimal text (question only, plus options only if question < 50 chars)
    for topic (and optional subtopic) classification only.
    """
    topics_list_str, has_subtopics, hierarchy = build_classification_prompt_context(topics)

    if has_subtopics:
        system_prompt = f"""You are an expert exam classifier for APPSC exams.
Classify each question strictly into ONE of the allowed topics, and select the best matching subtopic:
{topics_list_str}

Respond strictly as a JSON object where keys are question IDs as strings.
Example:
{{"1": {{"topic": "1. Ramayanam", "subtopic": "Characters"}}, "2": {{"topic": "5. Temple Agamas", "subtopic": "Vaishnavam (Vaikhanasa, Pancharatra, Chattada Srivaishnava)"}}}}"""
    else:
        system_prompt = f"""You are an expert exam classifier for APPSC exams.
Classify each question strictly into ONE of the allowed topics:
{topics_list_str}

Respond strictly as a JSON object where keys are question IDs and values are topic strings.
Example:
{{"1": "Logical Reasoning and Analytical Ability", "2": "Environment"}}"""

    items_to_send = []
    for q in batch:
        q_text = q["text"].replace('\n', ' ').strip()
        item = {
            "id": q["num"],
            "q": q_text[:200]
        }
        if len(q_text) < 50 and q["options_dict"]:
            opts_clean = " | ".join(f"{k}: {v}" for k, v in q["options_dict"].items())
            if opts_clean:
                item["opts"] = opts_clean[:100]
        items_to_send.append(item)

    user_prompt = json.dumps(items_to_send, ensure_ascii=False)
    raw_resp = call_openrouter(user_prompt, system_prompt, api_key, model)

    cleaned = raw_resp
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    data = json.loads(cleaned)
    if "classifications" in data and isinstance(data["classifications"], dict):
        data = data["classifications"]
    elif "questions" in data and isinstance(data["questions"], list):
        data = {str(item.get("id")): item for item in data["questions"]}

    results = {}

    for k, v in data.items():
        try:
            q_id = int(k)
        except ValueError:
            continue

        if isinstance(v, dict):
            raw_top = v.get("topic") or v.get("t")
            raw_sub = v.get("subtopic") or v.get("s")
        else:
            raw_top = str(v).strip()
            raw_sub = None

        assigned_topic, assigned_subtopic = match_best_topic_and_subtopic(raw_top, raw_sub, hierarchy)

        results[q_id] = {
            "topic": assigned_topic,
            "subtopic": assigned_subtopic if has_subtopics else None,
            "q": None,
            "opts": None
        }

    return results


def classify_and_clean_batch(batch: List[Dict], topics: Any, api_key: str, model: str) -> Dict[int, Dict[str, Any]]:
    """
    Sends a compact batch of questions and options to LLM.
    Returns:
    {
       q_id: {
           "topic": "<Classified Topic>",
           "subtopic": "<Classified Subtopic or None>",
           "q": "<Properly spaced question text>",
           "opts": { "1": "<Properly spaced opt 1>", ... }
       }
    }
    """
    topics_list_str, has_subtopics, hierarchy = build_classification_prompt_context(topics)

    if has_subtopics:
        system_prompt = f"""You are an expert exam editor and topic classifier for APPSC exams.
Your tasks:
1. Fix OCR concatenation and spacing errors in question text ('q') and options ('opts') (e.g., 'RecentlyGovernmentof India' -> 'Recently Government of India', 'September23' -> 'September 23', 'TheWorldEconomicforum' -> 'The World Economic Forum'). Retain exact wording, casing, numbers, and meaning.
2. Classify each question into exactly ONE allowed topic and choose its matching subtopic:
{topics_list_str}

Output strictly a JSON object where keys are question IDs as strings.
Example format:
{{
  "12": {{
    "topic": "1. Ramayanam",
    "subtopic": "Characters",
    "q": "Recently Government of India declared",
    "opts": {{"1": "June 23", "2": "July 23", "3": "August 23", "4": "September 23"}}
  }}
}}"""
    else:
        system_prompt = f"""You are an expert exam editor and topic classifier for APPSC exams.
Your tasks:
1. Fix OCR concatenation and spacing errors in question text ('q') and options ('opts') (e.g., 'RecentlyGovernmentof India' -> 'Recently Government of India', 'September23' -> 'September 23', 'TheWorldEconomicforum' -> 'The World Economic Forum'). Retain exact wording, casing, numbers, and meaning.
2. Classify each question into exactly ONE allowed topic:
{topics_list_str}

Output strictly a JSON object where keys are question IDs as strings.
Example format:
{{
  "12": {{
    "topic": "Current Events and Issues",
    "q": "Recently Government of India declared",
    "opts": {{"1": "June 23", "2": "July 23", "3": "August 23", "4": "September 23"}}
  }}
}}"""

    items_to_send = []
    for q in batch:
        item = {
            "id": q["num"],
            "q": q["text"].replace('\n', ' ').strip()
        }
        if q["options_dict"]:
            item["opts"] = q["options_dict"]
        items_to_send.append(item)

    user_prompt = json.dumps(items_to_send, ensure_ascii=False)
    raw_resp = call_openrouter(user_prompt, system_prompt, api_key, model)

    cleaned = raw_resp
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{|\[)[\s\S]*(\}|\])", cleaned)
        if match:
            data = json.loads(match.group(0))
        else:
            raise

    parsed_items = {}
    if isinstance(data, list):
        for entry in data:
            if "id" in entry:
                parsed_items[str(entry["id"])] = entry
    elif isinstance(data, dict):
        if "questions" in data and isinstance(data["questions"], list):
            for entry in data["questions"]:
                if "id" in entry:
                    parsed_items[str(entry["id"])] = entry
        elif "classifications" in data and isinstance(data["classifications"], dict):
            parsed_items = data["classifications"]
        else:
            parsed_items = data

    results = {}

    for k, v in parsed_items.items():
        try:
            q_id = int(k)
        except ValueError:
            continue

        if not isinstance(v, dict):
            continue

        raw_top = v.get("topic") or v.get("t")
        raw_sub = v.get("subtopic") or v.get("s")

        assigned_topic, assigned_subtopic = match_best_topic_and_subtopic(raw_top, raw_sub, hierarchy)

        cleaned_q = v.get("q") or v.get("question")
        cleaned_opts = v.get("opts") or v.get("options") or {}

        results[q_id] = {
            "topic": assigned_topic,
            "subtopic": assigned_subtopic if has_subtopics else None,
            "q": cleaned_q,
            "opts": cleaned_opts
        }

    return results


def update_markdown_file(
    md_path: str,
    results_map: Dict[int, Dict[str, Any]],
    topics: Any,
    output_path: Optional[str] = None,
    exam_tag: Optional[str] = None
) -> Path:
    p = Path(md_path).resolve()
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # Determine topic list and hierarchy
    if isinstance(topics, dict):
        hierarchy = topics
        topic_list = list(topics.keys())
    else:
        hierarchy = {t: [] for t in topics}
        topic_list = list(topics)

    has_any_subtopics = any(res.get("subtopic") for res in results_map.values()) or any(bool(s) for s in hierarchy.values())

    def replace_question_block(match):
        q_num = int(match.group(1))
        block_body = match.group(2)

        if q_num not in results_map:
            return match.group(0)

        res = results_map[q_num]
        new_topic = res["topic"]
        new_subtopic = res.get("subtopic")
        cleaned_q = res.get("q")
        cleaned_opts = res.get("opts")

        # 1. Update Topic & Subtopic
        if re.search(r"\*\*Topic:\*\*[^\n]+", block_body):
            block_body = re.sub(r"\*\*Topic:\*\*[^\n]+", f"**Topic:** {new_topic}", block_body)
        else:
            block_body = f"\n\n**Topic:** {new_topic}\n" + block_body

        if new_subtopic:
            if re.search(r"\*\*Subtopic:\*\*[^\n]+", block_body):
                block_body = re.sub(r"\*\*Subtopic:\*\*[^\n]+", f"**Subtopic:** {new_subtopic}", block_body)
            else:
                # Insert directly after **Topic:** line
                block_body = re.sub(r"(\*\*Topic:\*\*[^\n]+)", r"\1\n**Subtopic:** " + new_subtopic, block_body, count=1)
        else:
            # If no subtopic assigned, remove any leftover Subtopic tag if present
            block_body = re.sub(r"\n?\*\*Subtopic:\*\*[^\n]+", "", block_body)

        # 2. Update Question text if cleaned text is provided and reasonable
        if cleaned_q and isinstance(cleaned_q, str) and len(cleaned_q.strip()) > 0:
            def q_repl(qm):
                return f"### Question\n\n{cleaned_q.strip()}\n"
            block_body = re.sub(
                r"### Question\s*\n\s*[\s\S]*?(?=\n### Options|\n### Answer|\n### Exam|\n---|\Z)",
                q_repl,
                block_body
            )

        # 3. Update Options if cleaned options are provided
        if cleaned_opts and isinstance(cleaned_opts, dict):
            opts_m = re.search(r"### Options\s*\n\s*([\s\S]*?)(?=\n### Answer|\n### Exam|\n---|\Z)", block_body)
            if opts_m:
                orig_opts_text = opts_m.group(1).strip()
                new_opt_lines = []
                for line in orig_opts_text.splitlines():
                    line_s = line.strip()
                    if not line_s:
                        continue
                    m = re.match(r"^(\(?\d+\)?|[a-dA-D]\.|\d+\.)\s*(.*)$", line_s)
                    if m:
                        key = re.sub(r"[^\w]", "", m.group(1))
                        if key in cleaned_opts and cleaned_opts[key]:
                            clean_val = str(cleaned_opts[key]).strip()
                            clean_val = re.sub(r"^(\(?\d+\)?|[a-dA-D]\.|\d+\.|\.)\s*", "", clean_val).strip()
                            fmt_prefix = f"{key}."
                            new_opt_lines.append(f"{fmt_prefix} {clean_val}")
                        else:
                            new_opt_lines.append(line_s)
                    else:
                        new_opt_lines.append(line_s)

                if new_opt_lines:
                    new_opts_section = "### Options\n\n" + "\n".join(new_opt_lines) + "\n"
                    block_body = re.sub(
                        r"### Options\s*\n\s*[\s\S]*?(?=\n### Answer|\n### Exam|\n---|\Z)",
                        lambda _: new_opts_section,
                        block_body
                    )

        # 4. Update Exam tag if provided
        if exam_tag:
            if re.search(r"### Exam\s*\n\s*[^\n]+", block_body):
                block_body = re.sub(r"### Exam\s*\n\s*[^\n]+", f"### Exam\n\n{exam_tag}", block_body)
            else:
                block_body = block_body.rstrip() + f"\n\n### Exam\n\n{exam_tag}\n"

        return f"## Question {q_num}{block_body}"

    # Match each ## Question block
    content = re.sub(
        r"^## Question\s+(\d+)([\s\S]*?)(?=^## Question\s+\d+|\Z)",
        replace_question_block,
        content,
        flags=re.MULTILINE
    )

    # Rebuild Topic Index
    # Map topic -> subtopic -> [Q#]
    topic_sub_to_qs = defaultdict(lambda: defaultdict(list))
    topic_to_qs = defaultdict(list)
    for q_num, res in sorted(results_map.items()):
        t = res["topic"]
        s = res.get("subtopic")
        topic_to_qs[t].append(f"Q{q_num}")
        if s:
            topic_sub_to_qs[t][s].append(f"Q{q_num}")

    index_lines = ["## Topic Index\n\n"]
    for top in topic_list:
        index_lines.append(f"### {top}\n\n")
        subs_defined = hierarchy.get(top, [])
        if has_any_subtopics and (subs_defined or topic_sub_to_qs[top]):
            all_subs = list(subs_defined)
            for s in topic_sub_to_qs[top]:
                if s not in all_subs:
                    all_subs.append(s)

            for s in all_subs:
                index_lines.append(f"#### {s}\n\n")
                qs = topic_sub_to_qs[top].get(s, [])
                if qs:
                    for q in qs:
                        index_lines.append(f"- {q}\n")
                else:
                    index_lines.append("*(No questions)*\n")
                index_lines.append("\n")
        else:
            qs = topic_to_qs[top]
            if qs:
                for q in qs:
                    index_lines.append(f"- {q}\n")
            else:
                index_lines.append("*(No questions)*\n")
            index_lines.append("\n")

    new_index_str = "".join(index_lines).strip()

    if re.search(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*(?:#|## Question))", content):
        content = re.sub(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*(?:#|## Question))", new_index_str + "\n\n", content, count=1)
    elif content.startswith("## Topic Index"):
        content = re.sub(r"^## Topic Index\s+[\s\S]*?(?=---\s*\n)", new_index_str + "\n\n", content, count=1)
    elif re.search(r"^# [^\n]+\n+", content):
        content = re.sub(r"(^# [^\n]+\n+)", r"\1" + new_index_str + "\n\n---\n\n", content, count=1)
    else:
        content = new_index_str + "\n\n---\n\n" + content

    dest = Path(output_path).resolve() if output_path else p
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

    return dest


def prompt_mode_interactive() -> str:
    """
    Prompts the user interactively in the terminal to choose between:
    1. Topic Classification + OCR Spacing Fix
    2. Topic Classification Only (Minimal tokens)
    """
    print("\n" + "=" * 60)
    print("APPSC Question Classifier - Select Mode")
    print("=" * 60)
    print("  [1] Classify + Fix OCR Spacing in Questions & Options")
    print("      (Sends question text + options, fixes OCR run-ons like 'Governmentof India' -> 'Government of India')")
    print("  [2] Topic Classification Only (Most Minimal Tokens)")
    print("      (Sends question text only, fastest & lowest token usage)")
    print("=" * 60)

    while True:
        try:
            choice = input("Select mode [1/2] (default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)

        if choice in ("", "1"):
            return "fix_spacing"
        elif choice == "2":
            return "classify_only"
        else:
            print("Invalid selection. Please enter 1 or 2.")


def main():
    parser = argparse.ArgumentParser(description="Classify questions and optionally fix OCR spacing in an APPSC markdown file.")
    parser.add_argument("md_file", help="Path to the questions markdown file (e.g. 2025-GSMA.md)")
    parser.add_argument("-t", "--topics", default="classify/topics.md", help="Path to topics.md file (default: classify/topics.md)")
    parser.add_argument("-o", "--output", default=None, help="Output markdown file path (default: overwrite input in-place)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    parser.add_argument("-k", "--api-key", default=None, help="OpenRouter API Key (or set OPENROUTER_API_KEY environment variable)")
    parser.add_argument("-b", "--batch-size", type=int, default=25, help="Number of questions per request (default: 25)")
    parser.add_argument("-e", "--exam", default=None, help="Exam tag to set/update in questions (e.g. FSO-2020, FSO-2026)")
    parser.add_argument("--no-sort", action="store_true", help="Do not automatically sort/rearrange question blocks by topic")

    # Non-interactive CLI flags for mode override
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fix-spacing", action="store_true", help="Fix OCR spacing in questions and options along with topic classification")
    group.add_argument("--classify-only", action="store_true", help="Topic classification only without modifying question or options text (minimal tokens)")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OpenRouter API key not found.", file=sys.stderr)
        print("Please provide it via --api-key <KEY>, set OPENROUTER_API_KEY in environment, or add it to classify/.env", file=sys.stderr)
        sys.exit(1)

    print(f"Loading topics from: {args.topics}")
    hierarchy = load_topic_hierarchy(args.topics)
    topics = list(hierarchy.keys())
    has_subtopics = any(bool(s) for s in hierarchy.values())
    total_subtopics = sum(len(s) for s in hierarchy.values())
    if has_subtopics:
        print(f"Loaded {len(topics)} topics with {total_subtopics} subtopics.")
    else:
        print(f"Loaded {len(topics)} topics.")

    print(f"Reading markdown questions from: {args.md_file}")
    with open(args.md_file, "r", encoding="utf-8") as f:
        content = f.read()

    questions = parse_markdown_questions(content)
    if not questions:
        print(f"No questions found in {args.md_file}", file=sys.stderr)
        sys.exit(1)

    # Determine mode: either from CLI flag or interactive prompt
    if args.fix_spacing:
        mode = "fix_spacing"
    elif args.classify_only:
        mode = "classify_only"
    else:
        # Check if stdin is interactive (terminal)
        if sys.stdin.isatty():
            mode = prompt_mode_interactive()
        else:
            mode = "fix_spacing"

    mode_desc = "Classification + Spacing Fix" if mode == "fix_spacing" else "Topic Classification Only (Minimal Tokens)"
    print(f"\nMode: {mode_desc}")
    print(f"Model: {args.model}")
    print(f"Questions: {len(questions)} | Batch Size: {args.batch_size}")
    if args.exam:
        print(f"Exam Tag: {args.exam}")
    print("Starting processing...\n")

    results_map = {}
    batch_size = args.batch_size

    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        start_q = batch[0]["num"]
        end_q = batch[-1]["num"]
        print(f"  Processing questions Q{start_q} - Q{end_q} ({len(batch)} questions)...")

        if mode == "fix_spacing":
            batch_result = classify_and_clean_batch(batch, hierarchy, api_key, args.model)
        else:
            batch_result = classify_only_batch(batch, hierarchy, api_key, args.model)

        results_map.update(batch_result)

    print(f"\nSuccessfully processed {len(results_map)} questions.")

    out_file = update_markdown_file(args.md_file, results_map, hierarchy, args.output, args.exam)
    print(f"Markdown file successfully updated: {out_file}")

    if not args.no_sort:
        try:
            from classify.postsort import sort_markdown_by_topic
        except ImportError:
            try:
                from postsort import sort_markdown_by_topic
            except ImportError:
                sys.path.insert(0, str(Path(__file__).parent))
                from postsort import sort_markdown_by_topic

        print("Auto-rearranging questions sorted by topic...")
        sorted_file = sort_markdown_by_topic(str(out_file), hierarchy)
        print(f"Questions successfully sorted by topic: {sorted_file}")


if __name__ == "__main__":
    main()
