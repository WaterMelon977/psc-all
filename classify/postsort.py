"""
Post-sorting utility for classified Question Bank Markdown files.
Rearranges question blocks grouped and sorted by Topic according to the order defined in topics.md
(or preserves natural topic order) and updates the Topic Index.
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional

# Re-use load_topics if available
try:
    from classify.classify import load_topics
except ImportError:
    def load_topics(topics_path: str) -> List[str]:
        p = Path(topics_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Topics file not found: {topics_path}")
        topics = []
        with open(p, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or (line.startswith("# ") and "topic" in line.lower()):
                    continue
                line = re.sub(r"^#+\s*", "", line).strip()
                line = re.sub(r"^(\d+\.|\-|\*)\s*", "", line).strip()
                line = line.strip("`").strip()
                if not line or line.startswith("---") or line.lower().startswith("markdown tag") or line.lower().startswith("all topics") or "topics for classification" in line.lower():
                    continue
                if line not in topics:
                    topics.append(line)
        return topics


def parse_header_and_blocks(md_content: str):
    """
    Extracts the document header (Title and Topic Index)
    and separates out all question blocks.
    """
    # Everything up to the first question header
    first_q = re.search(r"(?m)^## Question\s+\d+", md_content)
    if first_q:
        header_raw = md_content[:first_q.start()]
        questions_part = md_content[first_q.start():]
    else:
        header_raw = ""
        questions_part = md_content

    # Strip any trailing '# <Topic>', '# Questions', or dividers from header_raw
    # Keep only the title and ## Topic Index
    header_clean = re.sub(r"(?m)^# (?!APPSC)[^\n]+\n*", "", header_raw)
    header_clean = re.sub(r"-{3,}\s*$", "", header_clean.strip()).strip()

    # Extract individual question blocks
    # Blocks start with ## Question <N> and end with --- or EOF
    raw_blocks = re.split(r"(?m)(?=^## Question\s+\d+)", questions_part)
    question_blocks = []

    for b in raw_blocks:
        b_clean = b.strip()
        if not b_clean:
            continue
        q_match = re.match(r"^## Question\s+(\d+)", b_clean)
        if not q_match:
            continue
        q_num = int(q_match.group(1))

        # Extract topic
        top_match = re.search(r"\*\*Topic:\*\*\s*([^\n]+)", b_clean)
        topic = top_match.group(1).strip() if top_match else "Unclassified"

        # Normalize trailing separator: strip trailing dashes
        cleaned_body = re.sub(r"\n+---\s*$", "", b_clean).strip()

        question_blocks.append({
            "num": q_num,
            "topic": topic,
            "block": cleaned_body
        })

    return header_clean, question_blocks


def sort_markdown_by_topic(md_path: str, topics_order: Optional[List[str]] = None, output_path: Optional[str] = None):
    p = Path(md_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    header_clean, blocks = parse_header_and_blocks(content)
    if not blocks:
        print(f"No question blocks found in {md_path}")
        return p

    # Group by topic
    topic_groups = defaultdict(list)
    for item in blocks:
        topic_groups[item["topic"]].append(item)

    # Determine topic ordering
    if topics_order:
        ordered_topics = [t for t in topics_order if t in topic_groups]
        # Append any leftover topics not in topics_order
        for t in topic_groups:
            if t not in ordered_topics:
                ordered_topics.append(t)
    else:
        # Keep existing order of appearance
        ordered_topics = []
        for item in blocks:
            if item["topic"] not in ordered_topics:
                ordered_topics.append(item["topic"])

    # Reconstruct questions section grouped by topic
    questions_sections = []
    for top in ordered_topics:
        # Heading for the topic group
        questions_sections.append(f"# {top}\n")
        q_list = topic_groups[top]
        # Keep question number order inside topic
        q_list.sort(key=lambda x: x["num"])
        for q in q_list:
            questions_sections.append(f"{q['block']}\n\n---\n")

    rearranged_questions = "\n".join(questions_sections).strip()

    # Rebuild Topic Index in header
    topic_to_qs = defaultdict(list)
    for q in blocks:
        topic_to_qs[q["topic"]].append(f"Q{q['num']}")

    index_topics = topics_order if topics_order else ordered_topics
    index_lines = ["## Topic Index\n\n"]
    for top in index_topics:
        index_lines.append(f"### {top}\n\n")
        qs = sorted(topic_to_qs[top], key=lambda x: int(x[1:])) if top in topic_to_qs else []
        if qs:
            for q in qs:
                index_lines.append(f"- {q}\n")
        else:
            index_lines.append("*(No questions)*\n")
        index_lines.append("\n")

    new_index_str = "".join(index_lines).strip()

    # Replace existing Topic Index in header_clean
    if re.search(r"## Topic Index\s+[\s\S]*?(?=\Z)", header_clean):
        header_clean = re.sub(r"## Topic Index\s+[\s\S]*?(?=\Z)", new_index_str + "\n", header_clean)
    else:
        header_clean = header_clean.strip() + "\n\n" + new_index_str + "\n"

    final_content = header_clean.strip() + "\n\n---\n\n" + rearranged_questions + "\n"

    dest = Path(output_path).resolve() if output_path else p
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(final_content)

    return dest


def main():
    parser = argparse.ArgumentParser(description="Rearrange and sort questions in a markdown file by topic.")
    parser.add_argument("md_file", help="Path to the markdown file to sort")
    parser.add_argument("-t", "--topics", default="classify/topics.md", help="Path to topics.md defining topic order (default: classify/topics.md)")
    parser.add_argument("-o", "--output", default=None, help="Output markdown file path (default: overwrite in-place)")
    args = parser.parse_args()

    topics_order = None
    if args.topics and Path(args.topics).exists():
        topics_order = load_topics(args.topics)
        print(f"Loaded topic order ({len(topics_order)} topics) from: {args.topics}")

    print(f"Rearranging questions in {args.md_file} by topic...")
    out_file = sort_markdown_by_topic(args.md_file, topics_order, args.output)
    print(f"File sorted successfully: {out_file}")


if __name__ == "__main__":
    main()
