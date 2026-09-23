# md2qp (Markdown to Question Paper PDF Generator)

A specialized Python utility to convert extracted exam MCQ markdown question banks into publication-quality, print-ready 2-column A4 question papers using **Bookman Old Style** font and ReportLab.

---

## What It Does

- **Topic & Subtopic Grouping**: Reads questions and automatically groups them under categorized topic banners (`**Topic:**`) and pronounced yet elegant subtopic headers (`**Subtopic:**`), strictly preserving the syllabus hierarchy.
- **Bookman Old Style Typography**: Registers Windows native Bookman Old Style (`BOOKOS.TTF`, `BOOKOSB.TTF`, `BOOKOSI.TTF`) with full bold and italic font-family support.
- **Publication Layout**:
  - Standard A4 2-column layout with 14 pt central gutter.
  - Running top header with divider line.
  - Central vertical dividing line between columns.
  - Footer with total page count (`Page X of Y`).
- **Clean MCQ Question Formatting**:
  - Numbering preserved directly as `Q.<original_num>` (e.g., `Q.1`, `Q.114`).
  - Question paragraph breaks and clause spacing (statements, assertions, reasons) preserved with distinct 2-line gaps for visual clarity.
  - Bold option labels: **(A)**, **(B)**, **(C)**, **(D)** in Bookman Bold, with regular option text.
  - Compact 2x2 grid for short options; 1-column stack for long options.
  - Embedded Markdown match tables converted to neat ReportLab tables.
- **Unboxed Answer & Exam Tag Display**:
  - Answers presented as clean, plain unboxed text: `Ans : (A)` (or multiple options e.g. `Ans : (C), (D)`).
  - Displays the exam origin in **bold** on the same line as the answer, aligned to the right end (e.g. `[PCB 2025]`), automatically cleaned from `PCB-2025`.
  - Handles official exam discrepancy / ambiguity notes in subtle italics.
- **Optimal Column Space Utilization**:
  - Allows question text and options to break and continue across columns naturally down to the bottom margin to eliminate bottom gaps.
  - Keeps answer and separator lines grouped together so questions remain cohesive.

---

## Requirements

- Python 3.8+
- `reportlab`

Install dependency:
```bash
pip install reportlab
```

*Note: The script automatically accesses the Windows system fonts directory (`C:\Windows\Fonts`) for `BOOKOS.TTF` (Bookman Old Style). If running on a non-Windows OS, it cleanly falls back to Times-Roman.*

---

## How to Use

### 1. Basic Command-Line Usage

Run `generate_pdf.py` passing the path to any exam `.md` file:

```bash
python md2qp\generate_pdf.py <path-to-markdown-file>
```

**Example:**
```bash
python md2qp\generate_pdf.py d:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA.md
```

The output PDF is automatically created in the same directory as the `.md` file with the suffix `_TopicWise.pdf` (e.g. `2025-GSMA_TopicWise.pdf`).

---

### 2. Custom Output PDF Path

You can also specify a custom output PDF file name or destination path as the second argument:

```bash
python md2qp\generate_pdf.py <input.md> <output.pdf>
```

**Example:**
```bash
python md2qp\generate_pdf.py d:\appsc-loaded\pcb-ae\pdfs\2022-ae-various-gsma\2022-ae-various-gsma.md d:\appsc-loaded\pcb-ae\pdfs\2022-ae-various-gsma\custom_output.pdf
```

---

### 3. Default Run (Without Arguments)

Running the script with no arguments runs on the default 2025 GSMA question paper:
```bash
python md2qp\generate_pdf.py
```

---

## Python API Usage

You can also import and invoke the generator function directly in your own Python scripts:

```python
from md2qp.generate_pdf import generate_topicwise_pdf

generate_topicwise_pdf(
    md_input_path=r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA.md',
    pdf_output_path=r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA_TopicWise.pdf'
)
```

---

## Supported Markdown Structure

The input markdown supports both flat topic question banks and hierarchical subtopics:

```markdown
## Topic Index
### 1. Ramayanam
#### Characters
- Q1
#### Kandaas (Parts)
- Q2

---

## Question 1

**Topic:** 1. Ramayanam
**Subtopic:** Characters

### Question
Question text here...

### Options
1. Option 1
2. Option 2
3. Option 3
4. Option 4

### Answer
> **Answer: 1**
```

*(When `**Subtopic:**` is absent, questions are grouped cleanly under the topic banner directly).*

