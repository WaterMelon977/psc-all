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

# google/gemini-2.5-flash-lite offers high speed, high reasoning accuracy,
# and ultra-low pricing ($0.10/M prompt, $0.40/M completion).
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_topics(topics_path: str) -> List[str]:
    """
    Loads topic names from a topics.md or topics.txt file.
    Accepts:
    - Markdown headings (### Topic)
    - Markdown lists (- Topic, * Topic, 1. Topic)
    - Plain text lines
    """
    p = Path(topics_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Topics file not found: {topics_path}")

    topics = []
    with open(p, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            # Skip top-level title lines like # Topics ...
            if line.startswith("# ") and "topic" in line.lower():
                continue
            # Strip markdown heading
            line = re.sub(r"^#+\s*", "", line).strip()
            # Strip list numbers or bullets
            line = re.sub(r"^(\d+\.|\-|\*)\s*", "", line).strip()
            # Strip backticks
            line = line.strip("`").strip()
            # Skip horizontal rules or empty strings
            if not line or line.startswith("---") or line.lower().startswith("markdown tag") or line.lower().startswith("all topics") or "topics for classification" in line.lower():
                continue
            if line not in topics:
                topics.append(line)

    if not topics:
        raise ValueError(f"No valid topics could be extracted from {topics_path}")

    return topics


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

        # Extract existing topic
        top_match = re.search(r"\*\*Topic:\*\*\s*(.+)", raw_text)
        curr_topic = top_match.group(1).strip() if top_match else ""

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

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def classify_only_batch(batch: List[Dict], topics: List[str], api_key: str, model: str) -> Dict[int, Dict[str, Any]]:
    """
    Sends minimal text (question only, plus options only if question < 50 chars)
    for topic classification only (no spacing rewrite). Most minimal token consumption.
    """
    topics_list_str = "\n".join(f"- {t}" for t in topics)

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
        data = {str(item.get("id")): item.get("topic") for item in data["questions"]}

    results = {}
    topic_set = set(topics)
    topic_lower_map = {t.lower(): t for t in topics}

    for k, v in data.items():
        try:
            q_id = int(k)
        except ValueError:
            continue

        raw_assigned = str(v).strip()
        assigned_topic = topics[0]

        if raw_assigned in topic_set:
            assigned_topic = raw_assigned
        elif raw_assigned.lower() in topic_lower_map:
            assigned_topic = topic_lower_map[raw_assigned.lower()]
        else:
            for t in topics:
                if t.lower() in raw_assigned.lower() or raw_assigned.lower() in t.lower():
                    assigned_topic = t
                    break

        results[q_id] = {
            "topic": assigned_topic,
            "q": None,
            "opts": None
        }

    return results


def classify_and_clean_batch(batch: List[Dict], topics: List[str], api_key: str, model: str) -> Dict[int, Dict[str, Any]]:
    """
    Sends a compact batch of questions and options to LLM.
    Returns:
    {
       q_id: {
           "topic": "<Classified Topic>",
           "q": "<Properly spaced question text>",
           "opts": { "1": "<Properly spaced opt 1>", ... }
       }
    }
    """
    topics_list_str = "\n".join(f"- {t}" for t in topics)

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
    topic_set = set(topics)
    topic_lower_map = {t.lower(): t for t in topics}

    for k, v in parsed_items.items():
        try:
            q_id = int(k)
        except ValueError:
            continue

        if not isinstance(v, dict):
            continue

        raw_assigned = str(v.get("topic") or v.get("t") or "").strip()
        assigned_topic = topics[0]

        if raw_assigned in topic_set:
            assigned_topic = raw_assigned
        elif raw_assigned.lower() in topic_lower_map:
            assigned_topic = topic_lower_map[raw_assigned.lower()]
        else:
            for t in topics:
                if t.lower() in raw_assigned.lower() or raw_assigned.lower() in t.lower():
                    assigned_topic = t
                    break

        cleaned_q = v.get("q") or v.get("question")
        cleaned_opts = v.get("opts") or v.get("options") or {}

        results[q_id] = {
            "topic": assigned_topic,
            "q": cleaned_q,
            "opts": cleaned_opts
        }

    return results


def update_markdown_file(
    md_path: str,
    results_map: Dict[int, Dict[str, Any]],
    topics: List[str],
    output_path: Optional[str] = None
) -> Path:
    p = Path(md_path).resolve()
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    def replace_question_block(match):
        q_num = int(match.group(1))
        block_body = match.group(2)

        if q_num not in results_map:
            return match.group(0)

        res = results_map[q_num]
        new_topic = res["topic"]
        cleaned_q = res.get("q")
        cleaned_opts = res.get("opts")

        # 1. Update Topic
        if re.search(r"\*\*Topic:\*\*[^\n]+", block_body):
            block_body = re.sub(r"\*\*Topic:\*\*[^\n]+", f"**Topic:** {new_topic}", block_body)
        else:
            block_body = f"\n\n**Topic:** {new_topic}\n" + block_body

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

        return f"## Question {q_num}{block_body}"

    # Match each ## Question block
    content = re.sub(
        r"^## Question\s+(\d+)([\s\S]*?)(?=^## Question\s+\d+|\Z)",
        replace_question_block,
        content,
        flags=re.MULTILINE
    )

    # Rebuild Topic Index
    topic_to_qs = defaultdict(list)
    for q_num, res in sorted(results_map.items()):
        topic_to_qs[res["topic"]].append(f"Q{q_num}")

    index_lines = ["## Topic Index\n\n"]
    for top in topics:
        index_lines.append(f"### {top}\n\n")
        qs = topic_to_qs[top]
        if qs:
            for q in qs:
                index_lines.append(f"- {q}\n")
        else:
            index_lines.append("*(No questions)*\n")
        index_lines.append("\n")

    new_index_str = "".join(index_lines).strip()

    if re.search(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*# Questions)", content):
        content = re.sub(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*# Questions)", new_index_str + "\n\n", content)
    else:
        content = re.sub(r"(# [^\n]+\n+)", r"\1" + new_index_str + "\n\n---\n\n", content, count=1)

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
    topics = load_topics(args.topics)
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
    print("Starting processing...\n")

    results_map = {}
    batch_size = args.batch_size

    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        start_q = batch[0]["num"]
        end_q = batch[-1]["num"]
        print(f"  Processing questions Q{start_q} - Q{end_q} ({len(batch)} questions)...")

        if mode == "fix_spacing":
            batch_result = classify_and_clean_batch(batch, topics, api_key, args.model)
        else:
            batch_result = classify_only_batch(batch, topics, api_key, args.model)

        results_map.update(batch_result)

    print(f"\nSuccessfully processed {len(results_map)} questions.")

    out_file = update_markdown_file(args.md_file, results_map, topics, args.output)
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
        sorted_file = sort_markdown_by_topic(str(out_file), topics)
        print(f"Questions successfully sorted by topic: {sorted_file}")


if __name__ == "__main__":
    main()
