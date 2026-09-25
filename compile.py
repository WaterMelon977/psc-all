"""
Compilation Script for APPSC Question Banks.
Merges questions from multiple markdown files into a single unified markdown file (e.g. gsma/gsma-all.md),
grouped and sorted by topics defined in classify/topics.md.
Question numbers are sequentially renumbered (1, 2, 3...) per topic section.
Topic Index is excluded as requested.
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


def load_topics(topics_path: str) -> List[str]:
    """Loads ordered topics from topics.md."""
    p = Path(topics_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Topics file not found: {topics_path}")

    topics = []
    with open(p, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or (line.startswith("# ") and not line.startswith("### ")):
                continue
            if line.startswith("### "):
                clean_topic = re.sub(r"^###\s*", "", line).strip().strip("`").strip()
                if clean_topic and clean_topic not in topics:
                    topics.append(clean_topic)
                continue
            flat_item = re.sub(r"^#+\s*", "", line).strip()
            flat_item = re.sub(r"^(\d+\.|\-|\*)\s*", "", flat_item).strip().strip("`").strip()
            if flat_item and flat_item not in topics:
                topics.append(flat_item)

    if not topics:
        raise ValueError(f"No topics extracted from {topics_path}")
    return topics


def extract_question_blocks(file_path: Path) -> List[Dict[str, str]]:
    """
    Parses a markdown question bank file into individual question blocks.
    Extracts the topic and strips any trailing section headers and horizontal dividers.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    raw_blocks = re.split(r"(?m)(?=^## Question\s+\d+)", content)
    questions = []

    for b in raw_blocks:
        b_clean = b.strip()
        if not b_clean:
            continue
        m = re.match(r"^## Question\s+(\d+)", b_clean)
        if not m:
            continue
        orig_q_num = int(m.group(1))

        # Extract topic tag
        top_m = re.search(r"\*\*Topic:\*\*\s*([^\n]+)", b_clean)
        topic = top_m.group(1).strip() if top_m else "Unclassified"

        # Clean trailing separators and topic headings
        cleaned = b_clean
        while True:
            new_cleaned = re.sub(r'(?:\n+---+\s*|\n+#+ [^\n]+)+\s*$', '', cleaned).strip()
            if new_cleaned == cleaned:
                break
            cleaned = new_cleaned

        questions.append({
            "source_file": file_path.name,
            "orig_num": orig_q_num,
            "topic": topic,
            "body": cleaned
        })

    return questions


def compile_questions(
    source_dir: str,
    output_file: str,
    topics_file: str = "classify/topics.md",
    renumber: bool = True
) -> Path:
    """
    Compiles all markdown question files in source_dir into output_file,
    sorted by topic according to topics_file.
    """
    source_path = Path(source_dir).resolve()
    out_path = Path(output_file).resolve()
    topics = load_topics(topics_file)

    # Collect source files (excluding output_file if in the same directory)
    md_files = sorted([
        f for f in source_path.glob("*.md")
        if f.resolve() != out_path
    ])

    if not md_files:
        raise FileNotFoundError(f"No markdown files found in {source_dir}")

    print(f"Loaded {len(topics)} topics from: {topics_file}")
    print(f"Found {len(md_files)} markdown files in: {source_dir}")

    # Group questions by topic
    grouped_questions = defaultdict(list)
    total_parsed = 0

    for f in md_files:
        qs = extract_question_blocks(f)
        total_parsed += len(qs)
        for q in qs:
            grouped_questions[q["topic"]].append(q)

    print(f"Extracted {total_parsed} questions across {len(md_files)} files.\n")

    # Build compiled markdown content
    output_lines = []

    for topic in topics:
        q_list = grouped_questions.get(topic, [])
        if not q_list:
            continue

        print(f"Writing Topic: '{topic}' ({len(q_list)} questions)...")
        output_lines.append(f"# {topic}\n")

        for idx, item in enumerate(q_list, 1):
            block_text = item["body"]

            if renumber:
                # Renumber ## Question <old> -> ## Question <idx>
                block_text = re.sub(
                    r"^## Question\s+\d+",
                    f"## Question {idx}",
                    block_text,
                    count=1
                )

            output_lines.append(block_text)
            output_lines.append("\n---\n")

    # Handle any unclassified / other topics not explicitly in topics.md
    extra_topics = [t for t in grouped_questions if t not in topics]
    for topic in extra_topics:
        q_list = grouped_questions[topic]
        if not q_list:
            continue
        print(f"Writing Extra Topic: '{topic}' ({len(q_list)} questions)...")
        output_lines.append(f"# {topic}\n")
        for idx, item in enumerate(q_list, 1):
            block_text = item["body"]
            if renumber:
                block_text = re.sub(
                    r"^## Question\s+\d+",
                    f"## Question {idx}",
                    block_text,
                    count=1
                )
            output_lines.append(block_text)
            output_lines.append("\n---\n")

    final_content = "\n".join(output_lines).strip() + "\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"\nAll questions successfully compiled into: {out_path}")
    print(f"Total compiled questions: {total_parsed}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Compile and merge markdown questions into a unified document sorted by topic without topic index."
    )
    parser.add_argument(
        "-i", "--input-dir",
        default="gsma",
        help="Directory containing source markdown files (default: gsma)"
    )
    parser.add_argument(
        "-o", "--output",
        default="gsma/gsma-all.md",
        help="Output markdown file path (default: gsma/gsma-all.md)"
    )
    parser.add_argument(
        "-t", "--topics",
        default="classify/topics.md",
        help="Path to topics.md file (default: classify/topics.md)"
    )
    parser.add_argument(
        "--no-renumber",
        action="store_true",
        help="Do not sequentially renumber questions per topic section"
    )

    args = parser.parse_args()
    compile_questions(
        source_dir=args.input_dir,
        output_file=args.output,
        topics_file=args.topics,
        renumber=not args.no_renumber
    )


if __name__ == "__main__":
    main()
