#!/usr/bin/env python3
"""
Exam Sorter for APPSC Question Banks (exam_sort.py)

Sorts question blocks in markdown question bank files by their `### Exam` tag.
Supports:
1. Section-wise sorting (default): Keeps topics (# H1) and subtopics (## H2),
   and sorts questions within each subtopic/section by `### Exam` according to a specified
   or custom exam priority (e.g. Phil-temple-2025 first), then renumbers sequentially.
2. Global exam grouping (--global-group): Groups the entire document by `### Exam`.
3. Extraction mode (--extract): Extracts only questions matching a specific exam.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple


QUESTION_HEADER_PATTERN = re.compile(r"^##\s+Question\s+\d+\b", re.MULTILINE)
EXAM_PATTERN = re.compile(r"###\s+Exam\s*\n+([^\n\r]+)")


def extract_exam_tag(question_block: str) -> str:
    """Extracts the Exam string from a question block."""
    m = EXAM_PATTERN.search(question_block)
    if m:
        return m.group(1).strip()
    return "UNKNOWN"


def renumber_question_block(question_block: str, new_number: int) -> str:
    """Replaces the ## Question <num> line with the new number."""
    return re.sub(r"^##\s+Question\s+\d+\b", f"## Question {new_number}", question_block, count=1)


def parse_into_subtopic_blocks(content: str) -> List[Tuple[str, str, List[str]]]:
    """
    Parses content preserving # Topic and ## Subtopic structure.
    Returns a list of tuples: (topic_header, subtopic_header, [question_blocks])
    """
    # Regex to split on H1 or H2 (that is not ## Question)
    sections = []
    
    # We can split by H1 (# Topic) and H2 (## Subtopic)
    # Let's inspect tokens sequentially
    pattern = re.compile(r"(?m)^(?:(#\s+[^\n]+)|(##\s+(?!Question\b)[^\n]+)|(##\s+Question\s+\d+\b))")
    
    current_h1 = ""
    current_h2 = ""
    preamble = ""
    
    # Let's find all headers and question boundaries
    matches = list(pattern.finditer(content))
    if not matches:
        return []
    
    preamble = content[:matches[0].start()]
    
    blocks_data = [] # (h1, h2, question_text)
    
    # We will accumulate items
    items = [] # either ('H1', text), ('H2', text), or ('Q', q_text)
    
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chunk = content[start:end]
        
        m = matches[i]
        if m.group(1): # H1
            items.append(('H1', m.group(1).strip()))
        elif m.group(2): # H2
            items.append(('H2', m.group(2).strip()))
        elif m.group(3): # Question
            # Clean trailing dividers / newlines
            items.append(('Q', chunk.strip()))
            
    return preamble, items


def sort_by_exam_sectionwise(
    content: str,
    priority_exams: Optional[List[str]] = None,
    renumber: bool = True
) -> str:
    """
    Sorts questions within each section/subtopic by Exam tag.
    Exams listed in priority_exams will appear first (in that order),
    followed by any other exams alphabetically / naturally.
    Optionally renumbers questions sequentially (1..N) within each section.
    """
    if priority_exams is None:
        priority_exams = ["Phil-temple-2025"]

    # Normalize priority exams for matching
    priority_lower = [e.lower() for e in priority_exams]

    def get_sort_key(exam_tag: str):
        tag_lower = exam_tag.lower()
        if tag_lower in priority_lower:
            return (0, priority_lower.index(tag_lower), exam_tag)
        return (1, 0, exam_tag)

    # Let's parse with an H1-aware, H2-aware scanner
    # Match headers
    split_pattern = re.compile(r"(?m)^(?=#\s+|##\s+(?!Question\b)|##\s+Question\s+\d+\b)")
    chunks = split_pattern.split(content)
    
    output_parts = []
    current_questions: List[Tuple[str, str]] = [] # (exam_tag, question_block)
    
    def flush_questions():
        nonlocal current_questions
        if not current_questions:
            return
        
        # Sort questions by exam tag sort key, maintaining stable original order within same exam
        current_questions.sort(key=lambda x: get_sort_key(x[0]))
        
        for q_idx, (_, q_text) in enumerate(current_questions, start=1):
            formatted_q = q_text.strip()
            if renumber:
                formatted_q = renumber_question_block(formatted_q, q_idx)
            # Ensure it ends with ---
            if not formatted_q.endswith("---"):
                formatted_q += "\n\n---"
            output_parts.append(formatted_q + "\n\n")
        
        current_questions = []

    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        
        if stripped.startswith("## Question"):
            exam = extract_exam_tag(stripped)
            current_questions.append((exam, stripped))
        else:
            # Header or text preceding questions
            flush_questions()
            output_parts.append(stripped + "\n\n")
            
    flush_questions()
    
    return "".join(output_parts).rstrip() + "\n"


def sort_by_exam_global(
    content: str,
    priority_exams: Optional[List[str]] = None,
    renumber: bool = True
) -> str:
    """
    Groups and sorts the entire file by Exam tag.
    Creates # <ExamName> sections.
    """
    if priority_exams is None:
        priority_exams = ["Phil-temple-2025"]

    priority_lower = [e.lower() for e in priority_exams]

    def get_sort_key(exam_tag: str):
        tag_lower = exam_tag.lower()
        if tag_lower in priority_lower:
            return (0, priority_lower.index(tag_lower), exam_tag)
        return (1, 0, exam_tag)

    # Extract all question blocks
    matches = list(QUESTION_HEADER_PATTERN.finditer(content))
    if not matches:
        return content

    preamble = content[:matches[0].start()].strip()
    questions_by_exam: Dict[str, List[str]] = {}

    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        raw_block = content[start:end].strip()
        # Clean trailing dividers and headers
        cleaned = re.sub(r'(?:\n+---+\s*|\n+#+ [^\n]+)+\s*$', '', raw_block).strip()
        exam = extract_exam_tag(cleaned)
        
        if exam not in questions_by_exam:
            questions_by_exam[exam] = []
        questions_by_exam[exam].append(cleaned)

    # Sort exam groups
    sorted_exams = sorted(questions_by_exam.keys(), key=get_sort_key)
    
    output_parts = []
    if preamble:
        output_parts.append(preamble + "\n\n---\n\n")

    global_counter = 1
    for exam in sorted_exams:
        output_parts.append(f"# Exam: {exam}\n\n")
        q_list = questions_by_exam[exam]
        for q_text in q_list:
            formatted_q = q_text
            if renumber:
                formatted_q = renumber_question_block(formatted_q, global_counter)
                global_counter += 1
            if not formatted_q.endswith("---"):
                formatted_q += "\n\n---"
            output_parts.append(formatted_q + "\n\n")

    return "".join(output_parts).rstrip() + "\n"


def process_exam_sort(
    input_file: str,
    output_file: Optional[str] = None,
    priority: Optional[List[str]] = None,
    mode: str = "sectionwise",
    no_renumber: bool = False,
    backup: bool = True
) -> str:
    """Main processing function."""
    p = Path(input_file).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    renumber = not no_renumber

    if mode == "global":
        sorted_content = sort_by_exam_global(content, priority_exams=priority, renumber=renumber)
    else:
        sorted_content = sort_by_exam_sectionwise(content, priority_exams=priority, renumber=renumber)

    dest = Path(output_file).resolve() if output_file else p
    if not output_file and backup:
        bak_path = p.with_suffix(p.suffix + ".bak")
        shutil.copy2(p, bak_path)
        print(f"[Backup] Created backup file at: {bak_path}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(sorted_content)

    print(f"[Success] Sorted markdown file written to: {dest}")
    return str(dest)


def main():
    parser = argparse.ArgumentParser(
        description="Sort questions in APPSC/State PSC markdown question banks by ### Exam."
    )
    parser.add_argument("file", help="Path to markdown question bank file to sort")
    parser.add_argument(
        "-p", "--priority",
        nargs="+",
        default=["Phil-temple-2025"],
        help="Exam tag(s) to prioritize at the beginning (default: Phil-temple-2025)"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["sectionwise", "global"],
        default="sectionwise",
        help="Sorting mode: 'sectionwise' (within each subtopic/topic) or 'global' (group whole document by exam)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Optional custom output path (default: in-place overwrite)"
    )
    parser.add_argument(
        "--no-renumber",
        action="store_true",
        help="Do not renumber questions sequentially (keep original question numbers)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a .bak file when modifying in-place"
    )

    args = parser.parse_args()

    try:
        process_exam_sort(
            input_file=args.file,
            output_file=args.output,
            priority=args.priority,
            mode=args.mode,
            no_renumber=args.no_renumber,
            backup=not args.no_backup
        )
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
