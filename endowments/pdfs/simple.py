"""
Extracts questions and answers from APPSC 2019 Final Key style PDF
(e.g., 2019-GSMA-commissioner.pdf) into standard Markdown format.
"""

import sys
import re
from pathlib import Path
import fitz

def clean_text(t: str) -> str:
    # Replace non-breaking spaces and fix unicode replacement chars
    t = t.replace("\xa0", " ").replace("\ufffd", "'")
    # Clean up redundant spaces
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()

def extract_final_key_pdf(pdf_path: str, output_md_path: str, exam_title: str = "2019 GSMA Commissioner"):
    doc = fitz.open(pdf_path)
    full_text = "\n".join([page.get_text() for page in doc])

    # Find all question start positions 1..150 sequentially
    pos = 0
    slices = []
    for q in range(1, 151):
        # Prefer explicit question prefix first ('Q. 1.', 'Q 1.', 'Question Number: 1')
        p_pref = re.compile(rf'(?:^|\n)\s*(?:Q\s*\.?\s*|Question\s+Number\s*:\s*){q}(?:[.\s:]|\Z)', re.IGNORECASE)
        m = p_pref.search(full_text, pos)
        if not m:
            # Fallback to plain number at start of line
            p_plain = re.compile(rf'(?:^|\n)\s*{q}\s*[\.\)]\s*')
            m = p_plain.search(full_text, pos)

        if m:
            slices.append((q, m.start(), m.end()))
            pos = m.end()
        else:
            print(f"Warning: Could not find Question {q} after offset {pos}", file=sys.stderr)

    print(f"Found {len(slices)} question blocks.")

    md_blocks = []
    
    for i, (q, s_start, s_end) in enumerate(slices):
        next_start = slices[i + 1][1] if i + 1 < len(slices) else len(full_text)
        block_text = full_text[s_end:next_start].strip()

        # Split into non-empty lines
        lines = [clean_text(l) for l in block_text.splitlines() if clean_text(l)]
        if not lines:
            continue

        if len(lines) == 1:
            q_text = lines[0]
            ans_text = ""
        else:
            # The last line (or lines) is the final answer
            ans_text = lines[-1]
            q_text = " ".join(lines[:-1])

        # Standard question markdown block
        block_md = f"""## Question {q}

**Topic:** General Studies

### Question

{q_text}

### Options

### Answer

> **Answer: {ans_text}**

### Exam

{exam_title}

---
"""
        md_blocks.append(block_md)

    # Initial header and content
    output_path = Path(output_md_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"# APPSC {exam_title} Question Bank\n\n"
    content = header + "\n".join(md_blocks) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully wrote {len(md_blocks)} questions to: {output_path}")

if __name__ == "__main__":
    pdf_in = r"d:\appsc-loaded\endowments\pdfs\2019-GSMA-commissioner.pdf"
    md_out = r"d:\appsc-loaded\endowments\pdfs\2019-GSMA-commissioner\2019-GSMA-commissioner.md"
    exam_title = "2019 GSMA"
    if len(sys.argv) > 1:
        pdf_in = sys.argv[1]
    if len(sys.argv) > 2:
        md_out = sys.argv[2]
    if len(sys.argv) > 3:
        exam_title = sys.argv[3]
    else:
        # derive from pdf filename
        exam_title = Path(pdf_in).stem.replace("_", " ").replace("-", " ")
    extract_final_key_pdf(pdf_in, md_out, exam_title)
