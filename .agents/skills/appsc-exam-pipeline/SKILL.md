---
name: appsc-exam-pipeline
description: End-to-end question bank processing pipeline for APPSC and State PSC exams. Covers PDF extraction (exq), OCR spacing cleanup and topic classification (classify), and publication-quality 2-column A4 question paper PDF generation (md2qp).
---

# APPSC Exam Processing Pipeline (appsc-exam-pipeline)

This skill guides the agent through the complete end-to-end pipeline for converting raw APPSC/State PSC question paper PDFs into cleanly classified markdown question banks and publication-ready 2-column A4 PDFs.

---

## Architecture Overview

```
 [Raw PDF]
    │
    ▼
[Step 1: exq/app.py] ────────► Extracted Markdown (Question Bank) & JSON
    │
    ▼
[Step 2: classify/classify.py] ──► OCR Spacing Fix, Topic Classification, Sorted Sections
    │
    ▼
[Step 3: md2qp/generate_pdf.py] ─► 2-Column A4 Printable Question Paper (Bookman Typography)
```

---

## 1. Step 1: Question Extraction (`exq/app.py`)

Extracts questions, options, and boxed answers from CBT or Offline booklet PDFs into standard structured Markdown and JSON.

### Command Syntax

```bash
python exq/app.py <pdf_path> [topics_yaml_path] -e <ExamTag> -f <format_mode> -o <output_dir>
```

### Parameters
- `<pdf_path>`: Absolute or relative path to the exam PDF.
- `[topics_yaml_path]`: Optional path to topic keyword definitions (default: `topics_gsma.yaml` or `topics.yaml`).
- `-e, --exam <ExamTag>`: The exam label to stamp on questions (e.g. `Endowments-2026`, `Inspector-2026`, `PCB-2025`).
- `-f, --format <format_mode>`:
  - `offline` or `booklet`: For scanned/printed question booklets with boxed answer keys.
  - `cbt`: For online Computer-Based Test response sheets.
- `-o, --output-dir <dir>`: Optional destination folder. Defaults to `<pdf_folder>/<pdf_name>/`.

### Example
```bash
python exq/app.py d:\appsc-loaded\endowments\pdfs\2025-GSMA.pdf d:\appsc-loaded\topics_gsma.yaml -e Endowments-2026 -f offline
```

### Outputs
- `<paper>.md` - Standard question bank markdown with Topic Index and questions.
- `<paper>.json` - Structured JSON representation.
- `<paper>_review.md` - Questions flagged for human review (missing options/unclear answers).

---

## 2. Step 2: OCR Spacing Fix & Topic Classification (`classify/classify.py`)

Fixes concatenated OCR text (e.g. `RecentlyGovernmentof India` $\rightarrow$ `Recently Government of India`, `September23` $\rightarrow$ `September 23`) and classifies questions into official syllabus topics using OpenRouter (`qwen/qwen-2.5-72b-instruct` by default for high-accuracy reasoning on State PSC syllabi).

### Command Syntax

```bash
python classify/classify.py <md_file> [options]
```

### Modes

#### Mode 1: Classify + Fix OCR Spacing (`--fix-spacing`)
Sends question text and options to the LLM to fix spacing issues while assigning the topic.
```bash
python classify/classify.py path/to/question_bank.md --fix-spacing
```

#### Mode 2: Topic Classification Only (`--classify-only`)
Sends only the concise question stem (and options only when question length is $< 50$ chars). Consumes minimal tokens; existing question and options text remain untouched.
```bash
python classify/classify.py path/to/question_bank.md --classify-only
```

#### Interactive Terminal Mode
If run without `--fix-spacing` or `--classify-only`, it presents an interactive selection prompt:
```text
============================================================
APPSC Question Classifier - Select Mode
============================================================
  [1] Classify + Fix OCR Spacing in Questions & Options
  [2] Topic Classification Only (Most Minimal Tokens)
============================================================
```

### Additional Flags
- `-t, --topics <path>`: Path to topics markdown file (default: `classify/topics.md`).
- `-m, --model <model_id>`: OpenRouter model (default: `google/gemini-2.5-flash-lite`).
- `-b, --batch-size <N>`: Questions per batch request (default: `25`).
- `-o, --output <path>`: Custom output markdown path (default: overwrites in-place).
- `--no-sort`: Skip automatic question block rearranging by topic.

### Standalone Post-Sorting
To re-sort an already classified markdown file without making LLM calls:
```bash
python classify/postsort.py path/to/question_bank.md -t classify/topics.md
```

---

## 3. Step 3: Markdown to Question Paper PDF (`md2qp/generate_pdf.py`)

Compiles the categorized question bank markdown into a publication-ready 2-column A4 PDF styled in Bookman Old Style.

### Command Syntax

```bash
python md2qp/generate_pdf.py <md_file> [pdf_output_path] [-h "Header Title"]
```

### Layout Specifications
- **Page Size**: A4 (595.28 pt $\times$ 841.89 pt).
- **Columns**: 2 columns per page (256 pt width each, 14 pt central gutter) with a central dividing vertical line.
- **Font**: Bookman Old Style (`BOOKOS.TTF`, `BOOKOSB.TTF`, `BOOKOSI.TTF`). Falls back to Times-Roman if unavailable.
- **Option Layout**: 2x2 grid for short choices; 1-column stack for longer choices. Options are labeled in bold: `1. `, `2. `, `3. `, `4. `.
- **Answers**: Unboxed clean display: `Ans : (3)` with the exam tag right-aligned (e.g. `[Endowments 2026]`).
- **Dividers**: Light hairline rule between questions; questions grouped cohesively across columns.

### Example
```bash
python md2qp/generate_pdf.py d:\appsc-loaded\endowments\pdfs\2025-GSMA\2025-GSMA.md
```
Output PDF is saved as: `<md_folder>/<md_name>_TopicWise.pdf`.

---

## Quick Reference / Full Recipe

To process a new PDF from start to finish:

```bash
# 1. Extract from PDF
python exq/app.py path/to/paper.pdf topics_gsma.yaml -e "Exam-Tag-2026" -f offline

# 2. Fix Spacing and Classify Topics
python classify/classify.py path/to/paper/paper.md --fix-spacing

# 3. Generate Publication Question Paper PDF
python md2qp/generate_pdf.py path/to/paper/paper.md
```
