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
from typing import List, Dict, Optional, Any, Tuple

# Re-use load_topics and load_topic_hierarchy if available
try:
    from classify.classify import load_topics, load_topic_hierarchy
except ImportError:
    try:
        from classify import load_topics, load_topic_hierarchy
    except ImportError:
        def load_topic_hierarchy(topics_path: str) -> Dict[str, List[str]]:
            p = Path(topics_path).resolve()
            if not p.exists():
                raise FileNotFoundError(f"Topics file not found: {topics_path}")
            hierarchy = {}
            current_topic = None
            with open(p, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or (line.startswith("# ") and not line.startswith("### ")):
                        continue
                    if line.startswith("### "):
                        clean_topic = re.sub(r"^###\s*", "", line).strip().strip("`").strip()
                        if clean_topic:
                            current_topic = clean_topic
                            if current_topic not in hierarchy:
                                hierarchy[current_topic] = []
                        continue
                    if (line.startswith("- ") or line.startswith("* ")) and current_topic:
                        sub = re.sub(r"^(\-|\*)\s*", "", line).strip().strip("`").strip()
                        if sub and not sub.startswith("---") and sub not in hierarchy[current_topic]:
                            hierarchy[current_topic].append(sub)
                        continue
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
            return list(load_topic_hierarchy(topics_path).keys())


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

        # Extract topic & subtopic
        top_match = re.search(r"\*\*Topic:\*\*\s*([^\n]+)", b_clean)
        topic = top_match.group(1).strip() if top_match else "Unclassified"

        sub_match = re.search(r"\*\*Subtopic:\*\*\s*([^\n]+)", b_clean)
        subtopic = sub_match.group(1).strip() if sub_match else ""

        # Normalize trailing separator: strip trailing dashes and trailing # Topic headers
        cleaned_body = b_clean
        while True:
            new_cleaned = re.sub(r'(?:\n+---+\s*|\n+#+ [^\n]+)+\s*$', '', cleaned_body).strip()
            if new_cleaned == cleaned_body:
                break
            cleaned_body = new_cleaned

        question_blocks.append({
            "num": q_num,
            "topic": topic,
            "subtopic": subtopic,
            "block": cleaned_body
        })

    return header_clean, question_blocks


def sort_markdown_by_topic(md_path: str, topics_order: Optional[Any] = None, output_path: Optional[str] = None):
    p = Path(md_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    header_clean, blocks = parse_header_and_blocks(content)
    if not blocks:
        print(f"No question blocks found in {md_path}")
        return p

    # Determine topic list and hierarchy
    if isinstance(topics_order, dict):
        hierarchy = topics_order
        ordered_topics_input = list(topics_order.keys())
    elif isinstance(topics_order, list):
        hierarchy = {t: [] for t in topics_order}
        ordered_topics_input = list(topics_order)
    else:
        hierarchy = {}
        ordered_topics_input = []

    # Check if any question actually has a subtopic assigned
    has_any_subtopics = any(bool(item["subtopic"]) for item in blocks) or any(bool(subs) for subs in hierarchy.values())

    # Group by topic, then subtopic
    topic_groups = defaultdict(lambda: defaultdict(list))
    for item in blocks:
        top = item["topic"]
        sub = item["subtopic"]
        topic_groups[top][sub].append(item)

    # Determine topic ordering
    if ordered_topics_input:
        ordered_topics = [t for t in ordered_topics_input if t in topic_groups]
        for t in topic_groups:
            if t not in ordered_topics:
                ordered_topics.append(t)
    else:
        ordered_topics = []
        for item in blocks:
            if item["topic"] not in ordered_topics:
                ordered_topics.append(item["topic"])

    # Reconstruct questions section grouped by topic (and subtopic if present)
    questions_sections = []
    for top in ordered_topics:
        questions_sections.append(f"# {top}\n")
        subs_dict = topic_groups[top]

        # Determine subtopics ordering for this topic
        defined_subs = hierarchy.get(top, [])
        if has_any_subtopics and (defined_subs or any(s for s in subs_dict.keys() if s)):
            ordered_subs = [s for s in defined_subs if s in subs_dict]
            for s in subs_dict:
                if s and s not in ordered_subs:
                    ordered_subs.append(s)

            for s in ordered_subs:
                questions_sections.append(f"## {s}\n")
                q_list = subs_dict[s]
                q_list.sort(key=lambda x: x["num"])
                for q in q_list:
                    questions_sections.append(f"{q['block']}\n\n---\n")

            # Any questions in this topic without a subtopic
            if "" in subs_dict and subs_dict[""]:
                q_list = subs_dict[""]
                q_list.sort(key=lambda x: x["num"])
                for q in q_list:
                    questions_sections.append(f"{q['block']}\n\n---\n")
        else:
            # Backward compatibility: flatten all questions under # Topic
            all_qs = []
            for s, q_list in subs_dict.items():
                all_qs.extend(q_list)
            all_qs.sort(key=lambda x: x["num"])
            for q in all_qs:
                questions_sections.append(f"{q['block']}\n\n---\n")

    rearranged_questions = "\n".join(questions_sections).strip()

    # Rebuild Topic Index in header
    topic_sub_to_qs = defaultdict(lambda: defaultdict(list))
    topic_to_qs = defaultdict(list)
    for q in blocks:
        top = q["topic"]
        sub = q["subtopic"]
        topic_to_qs[top].append(f"Q{q['num']}")
        if sub:
            topic_sub_to_qs[top][sub].append(f"Q{q['num']}")

    index_topics = ordered_topics_input if ordered_topics_input else ordered_topics
    for t in ordered_topics:
        if t not in index_topics:
            index_topics.append(t)

    index_lines = ["## Topic Index\n\n"]
    for top in index_topics:
        index_lines.append(f"### {top}\n\n")
        defined_subs = hierarchy.get(top, [])
        if has_any_subtopics and (defined_subs or topic_sub_to_qs[top]):
            all_subs = list(defined_subs)
            for s in topic_sub_to_qs[top]:
                if s not in all_subs:
                    all_subs.append(s)

            for s in all_subs:
                index_lines.append(f"#### {s}\n\n")
                qs = sorted(topic_sub_to_qs[top].get(s, []), key=lambda x: int(x[1:]))
                if qs:
                    for q in qs:
                        index_lines.append(f"- {q}\n")
                else:
                    index_lines.append("*(No questions)*\n")
                index_lines.append("\n")
        else:
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
    parser = argparse.ArgumentParser(description="Rearrange and sort questions in a markdown file by topic and subtopic.")
    parser.add_argument("md_file", help="Path to the markdown file to sort")
    parser.add_argument("-t", "--topics", default="classify/topics.md", help="Path to topics.md defining topic order (default: classify/topics.md)")
    parser.add_argument("-o", "--output", default=None, help="Output markdown file path (default: overwrite in-place)")
    args = parser.parse_args()

    topics_hierarchy = None
    if args.topics and Path(args.topics).exists():
        topics_hierarchy = load_topic_hierarchy(args.topics)
        print(f"Loaded topic order ({len(topics_hierarchy)} topics) from: {args.topics}")

    print(f"Rearranging questions in {args.md_file} by topic and subtopic...")
    out_file = sort_markdown_by_topic(args.md_file, topics_hierarchy, args.output)
    print(f"File sorted successfully: {out_file}")


if __name__ == "__main__":
    main()

