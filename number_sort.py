#!/usr/bin/env python3
"""
Question Markdown Sorter (number_sort.py)

Sorts question blocks in State PSC / APPSC question bank markdown files
numerically by question number (## Question 1, ## Question 2, ... ## Question 150)
directly in the markdown file itself (in-place by default).
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Tuple, Optional


QUESTION_HEADER_PATTERN = re.compile(r"^##\s+Question\s+(\d+)\b", re.MULTILINE)


def parse_questions_global(content: str) -> Tuple[str, List[Tuple[int, str]], str]:
    """
    Parses all question blocks from markdown content for global numerical sorting.
    Strips topic section headers (# Topic) that were originally between questions.

    Each question block is cleanly formatted and guaranteed to end with '---' and newlines.
    """
    matches = list(QUESTION_HEADER_PATTERN.finditer(content))
    if not matches:
        return content, [], ""

    raw_preamble = content[:matches[0].start()]
    
    # Clean preamble if it only contains an H1 topic header
    lines = [line.strip() for line in raw_preamble.splitlines() if line.strip()]
    if len(lines) == 1 and lines[0].startswith("# "):
        preamble = ""
    else:
        preamble = raw_preamble

    questions: List[Tuple[int, str]] = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        q_num = int(matches[i].group(1))
        raw_block = content[start:end]

        # Strip any trailing H1 topic headers that were separating questions
        trailing_h1 = re.search(r"\n+(#\s+[^\n]+)\s*\Z", raw_block)
        if trailing_h1:
            pure_block = raw_block[:trailing_h1.start()]
        else:
            pure_block = raw_block

        pure_block = pure_block.rstrip()
        if not pure_block.endswith("---"):
            pure_block += "\n\n---"
        pure_block += "\n\n"

        questions.append((q_num, pure_block))

    return preamble, questions, ""


def sort_markdown_content(content: str) -> str:
    """
    Sorts all questions in the markdown content by question number ascending (1 to N).
    """
    preamble, questions, postamble = parse_questions_global(content)
    if not questions:
        return content

    questions.sort(key=lambda item: item[0])
    body = "".join(q[1] for q in questions)
    return preamble + body + postamble


def sort_markdown_file(
    file_path: str,
    output_path: Optional[str] = None,
    backup: bool = True
) -> str:
    """
    Sorts a markdown file numerically. By default updates the markdown file directly in-place.
    """
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    sorted_content = sort_markdown_content(content)

    if output_path:
        target_path = Path(output_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Default: modify the file itself
        target_path = p
        if backup:
            bak_path = p.with_suffix(p.suffix + ".bak")
            shutil.copy2(p, bak_path)
            print(f"[Backup] Created backup: {bak_path}")

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(sorted_content)

    print(f"[Success] Sorted markdown directly in: {target_path}")
    return str(target_path)


def main():
    parser = argparse.ArgumentParser(
        description="Sort questions in APPSC/State PSC markdown question banks numerically (## Question <num>) directly in the file."
    )
    parser.add_argument("file", help="Path to markdown question bank file to sort in-place")
    parser.add_argument(
        "-o", "--output",
        help="Optional custom output file path (if you do not want in-place)",
        default=None
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a .bak file when sorting in-place"
    )

    args = parser.parse_args()

    try:
        sort_markdown_file(
            file_path=args.file,
            output_path=args.output,
            backup=not args.no_backup
        )
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
