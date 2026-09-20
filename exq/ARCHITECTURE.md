# Technical Architecture & Pipeline Specification

This document details the internal design, component specifications, and algorithmic invariants of the **EXQ** engine.

---

## 1. Architectural Philosophy

1. **Deterministic by Design**:
   - Zero reliance on external network calls, remote API services, or probabilistic language models.
   - Guaranteed identical output on identical inputs across operating systems and execution environments.

2. **Strict Single-Source-of-Truth**:
   - Extraction results feed a single internal domain model (`Question`), which is rendered consistently to Markdown, JSON, and quality metrics reports.

3. **Defensive Processing**:
   - Handles corrupted spans, irregular spacing, browser print margins, and inconsistent question boundaries without raising fatal uncaught exceptions.

---

## 2. Component Breakdown

### 2.1. PDF Extraction (`src/pdf_extractor.py`)
- Uses `fitz` (`PyMuPDF`) dictionary extraction (`page.get_text("dict")`).
- Extracts spans with text, font size, bounding box coordinates (`bbox`), and RGB color integers.
- Filters out browser-print metadata:
  - Top headers (timestamps, URLs, file paths).
  - Bottom footers (page counters like `1/45`, timestamps like `5/16/22, 10:23 AM`).

### 2.2. Language Detection & Deduplication (`src/language_detector.py`)
- Analyzes Unicode codepoints across blocks.
- Telugu block detection uses range: `\u0C00` to `\u0C7F`.
- If a question exists in both English and Telugu in bilingual papers, the Telugu version is systematically identified and excluded, preserving the pure English text and correct question index sequence.

### 2.3. Answer Detection (`src/answer_detector.py`)
- Answer keys in official PDFs are color-coded (typically green color for the correct option text or number span).
- Converts PyMuPDF integer colors to sRGB channels:
  - Validates `green > 120`, `red < 100`, and `blue < 100` (or appropriate green hue ratios).
- Supports single-key answers, multi-key answers (e.g., questions with multiple valid answers awarded by commission), and flags questions where no green span was found.

### 2.4. Topic Classification (`src/topic_classifier.py`)
- Multi-tier scoring system driven by `topics.yaml`:
  - **Keyword matching**: Case-insensitive substring and word-boundary matching with configurable weights.
  - **Regex matching**: Advanced contextual pattern matching for complex topics (e.g., legal acts, economic terms, spatial concepts).
- The highest scoring topic is selected; tie-breakers default to the topic defined earlier in the YAML configuration.

### 2.5. Smart Markdown Formatter (`src/question_formatter.py`)
- Pre-processes question stems to convert unstructured flat text into clean markdown structures:
  - **Matching Column Tables**: Emits standard GFM markdown tables with aligned columns.
  - **Assertion / Reason**: Separates assertions and reasons with bold identifiers for visual scanning.
  - **Numbered Statements**: Formats sub-statements onto distinct lines.

---

## 3. JSON Output Schema

The primary output format produced by `src/json_renderer.py` follows this schema:

```json
{
  "paper_title": "2025-GSMA",
  "total_questions": 150,
  "questions": [
    {
      "question_number": 1,
      "topic": "Mental Ability and Reasoning",
      "question_text": "...",
      "options": {
        "1": "Option A text",
        "2": "Option B text",
        "3": "Option C text",
        "4": "Option D text"
      },
      "answer": ["1"],
      "needs_review": false,
      "review_reasons": []
    }
  ]
}
```

---

## 4. Verification & Testing

Unit and integration tests are maintained under `tests/`:
- Run with:
  ```bash
  python -m unittest tests.test_converter -v
  ```
- Coverage encompasses:
  - Bilingual deduplication logic.
  - Color span answer identification (single, multi, none).
  - Hints block exclusion.
  - Topic ordering and regex priority weighting.
  - JSON and Markdown output parity.
