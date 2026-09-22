# APPSC Exam Question Bank & Paper Generation Skills

This document details the agentic workflows, command recipes, and tool specifications for the 3 core subsystems in this workspace:

1. **Extraction Subsystem**: [`exq/app.py`](file:///d:/appsc-loaded/exq/app.py)
2. **Classification & Spacing Subsystem**: [`classify/classify.py`](file:///d:/appsc-loaded/classify/classify.py)
3. **Publication PDF Subsystem**: [`md2qp/generate_pdf.py`](file:///d:/appsc-loaded/md2qp/generate_pdf.py)

---

## 1. Pipeline Architecture

```
                       [Raw Exam PDF]
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Step 1: exq/app.py                                     │
 │ - Parses CBT (online) or Booklet (offline) format      │
 │ - Detects questions, numbered options & marked answers │
 │ - Generates initial .md, .json & _review.md            │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Step 2: classify/classify.py                           │
 │ - Mode 1: Classify + Fix OCR Spacing (--fix-spacing)   │
 │ - Mode 2: Classify Only (--classify-only)              │
 │ - Uses low-cost google/gemini-2.5-flash-lite via API   │
 │ - Rebuilds Topic Index & auto-sorts sections by topic  │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Step 3: md2qp/generate_pdf.py                          │
 │ - Reads categorized Question Bank markdown             │
 │ - Formats into standard A4 2-Column layout             │
 │ - Uses Bookman Old Style typography                    │
 │ - Generates print-ready publication PDF                │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Skill 1: PDF Question Extraction (`exq/app.py`)

Extracts raw question papers into machine-readable Markdown and JSON.

### Execution

```bash
python exq/app.py <pdf_path> [topics_yaml] -e <ExamTag> -f <format_mode> -o <output_dir>
```

### Key Flags
- `pdf_path`: Path to source PDF (e.g. `d:\appsc-loaded\endowments\pdfs\2025-GSMA.pdf`).
- `topics_yaml`: YAML keyword taxonomy file (`topics_gsma.yaml`).
- `-e, --exam <Tag>`: Identifier stamped on each question (e.g. `Endowments-2026`, `Inspector-2026`).
- `-f, --format <mode>`:
  - `offline` or `booklet`: For scanned question booklets with boxed answer keys.
  - `cbt`: For online CBT response sheets.
- `-o, --output-dir <dir>`: Target output folder.

### Generated Artifacts
- `<name>.md`: Question bank markdown.
- `<name>.json`: Structured JSON for programmatic access.
- `<name>_review.md`: Questions requiring manual verification.

---

## 3. Skill 2: OCR Spacing Fix & Topic Classification (`classify/classify.py`)

Cleans up OCR errors and organizes questions by syllabus topics.

### Execution

#### Mode A: Classification + OCR Spacing Fix
Fixes joined words in question prompts and option lines (e.g. `RecentlyGovernmentof India` $\rightarrow$ `Recently Government of India`, `September23` $\rightarrow$ `September 23`):
```bash
python classify/classify.py <path_to_md> --fix-spacing
```

#### Mode B: Classification Only (Minimal Token Usage)
Only sends question stems without modifying text (preserves original markdown strings):
```bash
python classify/classify.py <path_to_md> --classify-only
```

#### Interactive Terminal Prompt
Running without mode flags in a terminal presents the choice interactively:
```bash
python classify/classify.py <path_to_md>
```

### Additional Flags
- `-t, --topics <path>`: Topics markdown path (default: `classify/topics.md`).
- `-m, --model <model>`: OpenRouter model (default: `google/gemini-2.5-flash-lite`).
- `-b, --batch-size <N>`: Questions per request (default: `25`).
- `-o, --output <path>`: Custom destination path (default: overwrites in-place).
- `--no-sort`: Skip rearranging questions by topic.

### Standalone Re-sorting (No LLM Calls)
```bash
python classify/postsort.py <path_to_md> -t classify/topics.md
```

---

## 4. Skill 3: Publication PDF Generation (`md2qp/generate_pdf.py`)

Converts the classified markdown into a publication-quality 2-column A4 question paper.

### Execution

```bash
python md2qp/generate_pdf.py <path_to_md> [output_pdf_path] [-h "Header Title"]
```

### Typography & Layout Specifications
- **Format**: Standard A4 2-Column layout (256 pt column width, 14 pt central gutter).
- **Dividers**: Running vertical line separating columns, thin hairline rule after each question.
- **Font**: Bookman Old Style (bold question numbers, bold option markers `1. `, `2. `, `3. `, `4. `).
- **Options**: Compact 2x2 grid for short options; stacked 1-column layout for long options.
- **Answers**: Unboxed clean display `Ans : (3)` with right-aligned exam source tag `[Endowments 2026]`.

---

## 5. Complete End-to-End Recipe

```bash
# 1. Extract from PDF
python exq/app.py d:\appsc-loaded\exam\pdfs\paper.pdf topics_gsma.yaml -e "Exam-2026" -f offline

# 2. Fix OCR Spacing & Classify Topics
python classify/classify.py d:\appsc-loaded\exam\pdfs\paper\paper.md --fix-spacing

# 3. Generate Publication PDF
python md2qp/generate_pdf.py d:\appsc-loaded\exam\pdfs\paper\paper.md
```
