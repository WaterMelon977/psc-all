"""
Topic Classifier for Question Bank Markdown files.
Uses OpenRouter API (e.g. deepseek/deepseek-chat or custom model) with batching
to classify questions into predefined topics and rebuild the Markdown Topic Index.
"""

import os
import re
import sys
import json
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

# Try loading from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also load from classify/.env if present
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

DEFAULT_MODEL = "deepseek/deepseek-chat"
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
    Parses questions from the standard markdown format:
    ## Question <number>
    **Topic:** <topic>
    ### Question
    <text>
    ### Options
    ...
    """
    q_blocks = re.split(r"(?m)^## Question\s+(\d+)", md_content)
    # q_blocks[0] is preamble before first question
    # then pairs: (question_number, content)
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

        # Extract Options
        opts_match = re.search(r"### Options\s*\n\s*([\s\S]*?)(?=\n### Answer|\n### Exam|\n---|\Z)", raw_text)
        opts_text = opts_match.group(1).strip() if opts_match else ""

        questions.append({
            "num": q_num,
            "topic": curr_topic,
            "text": q_text,
            "options": opts_text
        })
    return questions


def call_openrouter(prompt: str, api_key: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/appsc-loaded",
        "X-Title": "APPSC Question Classifier"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert examiner and classifier for APPSC and State PSC competitive exams. "
                    "You classify questions strictly into the provided list of allowed topics. "
                    "Respond ONLY with a valid JSON array or object as requested."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def classify_batch(batch: List[Dict], topics: List[str], api_key: str, model: str) -> Dict[int, str]:
    """
    Sends a batch of questions to OpenRouter and returns {q_num: topic}.
    """
    topics_list_str = "\n".join(f"- \"{t}\"" for t in topics)

    items_to_classify = []
    for q in batch:
        q_text = q['text'].replace('\n', ' ').strip()
        item = {
            "id": q["num"],
            "q": q_text[:200]
        }
        # Only include options if question text is very short (< 50 chars) or missing
        if len(q_text) < 50 and q.get('options'):
            opts_clean = q['options'].replace('\n', ' ').strip()
            if opts_clean:
                item["opts"] = opts_clean[:100]
        items_to_classify.append(item)

    prompt = f"""Given the following allowed topics:
{topics_list_str}

Classify each of the following exam questions into exactly ONE of the allowed topics.
Pick the most appropriate topic.

Questions to classify:
{json.dumps(items_to_classify, indent=2, ensure_ascii=False)}

Return your output strictly as a JSON object where keys are question IDs as strings and values are the exact topic string from the allowed topics list.
Example format:
{{
  "1": "Logical Reasoning and Analytical Ability",
  "2": "Current Events and Issues"
}}
"""

    raw_resp = call_openrouter(prompt, api_key, model)

    # Clean code fences if present
    cleaned = raw_resp
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    data = json.loads(cleaned)

    # Handle either { "1": "Topic" } or { "classifications": { ... } }
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

        assigned = str(v).strip()
        # Exact match
        if assigned in topic_set:
            results[q_id] = assigned
        # Case insensitive match
        elif assigned.lower() in topic_lower_map:
            results[q_id] = topic_lower_map[assigned.lower()]
        else:
            # Substring match fallback
            matched = False
            for t in topics:
                if t.lower() in assigned.lower() or assigned.lower() in t.lower():
                    results[q_id] = t
                    matched = True
                    break
            if not matched:
                results[q_id] = topics[0]  # Fallback to first

    return results


def update_markdown_file(md_path: str, classification_map: Dict[int, str], topics: List[str], output_path: Optional[str] = None):
    p = Path(md_path).resolve()
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update individual question topic tags
    def replace_topic(match):
        q_num = int(match.group(1))
        if q_num in classification_map:
            return f"## Question {q_num}\n\n**Topic:** {classification_map[q_num]}"
        return match.group(0)

    content = re.sub(r"## Question (\d+)\s*\n\s*\*\*Topic:\*\*[^\n]+", replace_topic, content)

    # 2. Rebuild the Topic Index section
    topic_to_qs = defaultdict(list)
    # Collect all question numbers present in the document
    q_nums = sorted(classification_map.keys())
    for qn in q_nums:
        t = classification_map[qn]
        topic_to_qs[t].append(f"Q{qn}")

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

    # Substitute Topic Index if it exists
    if re.search(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*# Questions)", content):
        content = re.sub(r"## Topic Index\s+[\s\S]*?(?=---\s*\n\s*# Questions)", new_index_str + "\n\n", content)
    else:
        # If no previous topic index, insert after title
        content = re.sub(r"(# [^\n]+\n+)", r"\1" + new_index_str + "\n\n---\n\n", content, count=1)

    dest = Path(output_path).resolve() if output_path else p
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

    return dest


def main():
    parser = argparse.ArgumentParser(description="Classify questions in an APPSC markdown file into topics.")
    parser.add_argument("md_file", help="Path to the questions markdown file (e.g. 2022-ae-various-gsma.md)")
    parser.add_argument("-t", "--topics", default="classify/topics.md", help="Path to topics.md file (default: classify/topics.md)")
    parser.add_argument("-o", "--output", default=None, help="Output markdown file path (default: overwrite input in-place)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    parser.add_argument("-k", "--api-key", default=None, help="OpenRouter API Key (or set OPENROUTER_API_KEY environment variable)")
    parser.add_argument("-b", "--batch-size", type=int, default=25, help="Number of questions per LLM classification request (default: 25)")
    parser.add_argument("--no-sort", action="store_true", help="Do not automatically sort/rearrange question blocks by topic")
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

    print(f"Found {len(questions)} questions. Starting classification using model: {args.model}...")

    classification_map = {}
    batch_size = args.batch_size

    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        start_q = batch[0]["num"]
        end_q = batch[-1]["num"]
        print(f"  Classifying questions Q{start_q} - Q{end_q} ({len(batch)} questions)...")

        batch_result = classify_batch(batch, topics, api_key, args.model)
        classification_map.update(batch_result)

    print(f"Successfully classified {len(classification_map)} questions.")

    out_file = update_markdown_file(args.md_file, classification_map, topics, args.output)
    print(f"Markdown file successfully updated: {out_file}")

    # Automatically run postsort unless --no-sort is specified
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
