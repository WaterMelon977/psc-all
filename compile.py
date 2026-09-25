"""
Compilation Script for APPSC Question Banks.
Merges questions from multiple markdown files into a single unified markdown file (e.g. gsma/gsma-all.md),
grouped and sorted by topics and subtopics defined in topics.md.
Question numbers are sequentially renumbered (1, 2, 3...) per topic section.
Topic Index is excluded as requested.
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any


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

    hierarchy: Dict[str, List[str]] = {}
    current_topic: Optional[str] = None

    with open(p, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            # Skip main document titles like # Topics ...
            if line.startswith("# ") and not line.startswith("### "):
                continue

            # Check if this is a topic heading (### Topic)
            if line.startswith("### "):
                clean_topic = re.sub(r"^###\s*", "", line).strip().strip("`").strip()
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

            if current_topic is None:
                if flat_item not in hierarchy:
                    hierarchy[flat_item] = []

    if not hierarchy:
        raise ValueError(f"No valid topics could be extracted from {topics_path}")

    return hierarchy


def load_topics(topics_path: str) -> List[str]:
    """Loads flat ordered topics from topics.md."""
    return list(load_topic_hierarchy(topics_path).keys())


def extract_question_blocks(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parses a markdown question bank file into individual question blocks.
    Extracts the topic and subtopic and strips any trailing section headers and horizontal dividers.
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

        # Extract topic & subtopic tags
        top_m = re.search(r"\*\*Topic:\*\*\s*([^\n]+)", b_clean)
        topic = top_m.group(1).strip() if top_m else "Unclassified"

        sub_m = re.search(r"\*\*Subtopic:\*\*\s*([^\n]+)", b_clean)
        subtopic = sub_m.group(1).strip() if sub_m else ""

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
            "subtopic": subtopic,
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
    sorted by topic and subtopic according to topics_file.
    """
    source_path = Path(source_dir).resolve()
    out_path = Path(output_file).resolve()
    hierarchy = load_topic_hierarchy(topics_file)
    topics = list(hierarchy.keys())

    # Collect source files (excluding output_file if in the same directory)
    md_files = sorted([
        f for f in source_path.glob("*.md")
        if f.resolve() != out_path
    ])

    if not md_files:
        raise FileNotFoundError(f"No markdown files found in {source_dir}")

    print(f"Loaded {len(topics)} topics from: {topics_file}")
    print(f"Found {len(md_files)} markdown files in: {source_dir}")

    # Group questions by topic -> subtopic -> list
    grouped_questions = defaultdict(lambda: defaultdict(list))
    total_parsed = 0
    has_subtopics = False

    for f in md_files:
        qs = extract_question_blocks(f)
        total_parsed += len(qs)
        for q in qs:
            grouped_questions[q["topic"]][q["subtopic"]].append(q)
            if q["subtopic"]:
                has_subtopics = True

    print(f"Extracted {total_parsed} questions across {len(md_files)} files.\n")

    # Build compiled markdown content
    output_lines = []

    # Sequence of all topics: defined first, then any extra topics found in questions
    all_topics = list(topics)
    for t in grouped_questions:
        if t not in all_topics:
            all_topics.append(t)

    for topic in all_topics:
        subs_dict = grouped_questions.get(topic, {})
        if not subs_dict:
            continue

        total_topic_qs = sum(len(q_list) for q_list in subs_dict.values())
        print(f"Writing Topic: '{topic}' ({total_topic_qs} questions)...")
        output_lines.append(f"# {topic}\n")

        q_counter = 1

        if has_subtopics:
            # Determine subtopic ordering for this topic
            defined_subs = hierarchy.get(topic, [])
            ordered_subs = [s for s in defined_subs if s in subs_dict]
            for s in subs_dict:
                if s and s not in ordered_subs:
                    ordered_subs.append(s)

            for s in ordered_subs:
                output_lines.append(f"## {s}\n")
                q_list = subs_dict[s]
                for item in q_list:
                    block_text = item["body"]
                    if renumber:
                        block_text = re.sub(
                            r"^## Question\s+\d+",
                            f"## Question {q_counter}",
                            block_text,
                            count=1
                        )
                    output_lines.append(block_text)
                    output_lines.append("\n---\n")
                    q_counter += 1

            # Questions under this topic without a subtopic
            if "" in subs_dict and subs_dict[""]:
                for item in subs_dict[""]:
                    block_text = item["body"]
                    if renumber:
                        block_text = re.sub(
                            r"^## Question\s+\d+",
                            f"## Question {q_counter}",
                            block_text,
                            count=1
                        )
                    output_lines.append(block_text)
                    output_lines.append("\n---\n")
                    q_counter += 1
        else:
            # Flat topic structure (no subtopics)
            flat_qs = []
            for q_list in subs_dict.values():
                flat_qs.extend(q_list)

            for item in flat_qs:
                block_text = item["body"]
                if renumber:
                    block_text = re.sub(
                        r"^## Question\s+\d+",
                        f"## Question {q_counter}",
                        block_text,
                        count=1
                    )
                output_lines.append(block_text)
                output_lines.append("\n---\n")
                q_counter += 1

    final_content = "\n".join(output_lines).strip() + "\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"\nAll questions successfully compiled into: {out_path}")
    print(f"Total compiled questions: {total_parsed}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Compile and merge markdown questions into a unified document sorted by topic and subtopic without topic index."
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
