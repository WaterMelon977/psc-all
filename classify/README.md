# Markdown Question Topic Classifier & Sorter

Automated topic classifier and rearranger for APPSC / State PSC question bank Markdown files using **OpenRouter** (defaults to `google/gemini-2.5-flash-lite` for ultra-low token cost and high accuracy, or any custom model).

---

## What It Does

1. **Interactive CLI with 2 Operation Modes**:
   - When run, it prompts you interactively to choose how you want questions processed:
     - **Option 1: Classify + Fix OCR Spacing in Questions & Options**:
       Sends question text + options in compact JSON batches to clean up OCR concatenation and run-ons (e.g. `RecentlyGovernmentof India` $\rightarrow$ `Recently Government of India`, `September23` $\rightarrow$ `September 23`, `TheWorldEconomicforum` $\rightarrow$ `The World Economic Forum`) while assigning the exact topic.
     - **Option 2: Topic Classification Only (Most Minimal Tokens)**:
       Sends only the concise question stem (and options only when the question text is $< 50$ chars) to classify into the 11 topics. Preserves existing markdown text completely untouched.
   - Non-interactive / scriptable execution via flags (`--fix-spacing` or `--classify-only`).

2. **Ultra-Low Token Cost**:
   - Uses **`google/gemini-2.5-flash-lite`** by default on OpenRouter ($0.10 / 1M prompt tokens, $0.40 / 1M completion tokens), reducing costs by ~70% compared to typical models while maintaining reliable structured output.

3. **Batched Processing**:
   - Groups questions into batches (default: 25 per request) to minimize prompt overhead.

4. **Topic Tagging & Dynamic Index Rebuilding**:
   - Updates each question's `**Topic:** <Topic Name>` tag.
   - Rebuilds the `## Topic Index` table of contents at the top of the file with clickable question numbers.

5. **Automatic Post-Sorting (`postsort.py`)**:
   - Automatically rearranges questions grouped under level-1 topic headers (`# <Topic Name>`) in the exact order specified by `topics.md`.
   - Preserves numerical order of questions within each topic group.

---

## Setup

Ensure your OpenRouter API key is set in `classify/.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
```

*(You can also pass it explicitly via `--api-key <KEY>` or set `OPENROUTER_API_KEY` in environment variables).*

---

## Topics File (`topics.md`)

Define your topics in `classify/topics.md` (or any custom `.md` file). The script accepts numbered lists, bullet points, markdown headings, or plain text:

```markdown
1. Logical Reasoning and Analytical Ability
2. Data Analysis and Tabulation
3. Sustainable Development
4. Environment
5. Disaster Management and GIS
6. Geography of India and AP
7. History of India and AP
8. Indian Polity and Governance
9. Indian Economy and Planning
10. General Science and Technology
11. Current Events and Issues
```

---

## Usage

### 1. Interactive Mode (Default)

Simply pass the markdown file. You will be greeted with an interactive prompt:

```bash
python classify/classify.py path/to/question_bank.md
```

Interactive prompt:
```text
============================================================
APPSC Question Classifier - Select Mode
============================================================
  [1] Classify + Fix OCR Spacing in Questions & Options
      (Sends question text + options, fixes OCR run-ons like 'Governmentof India' -> 'Government of India')
  [2] Topic Classification Only (Most Minimal Tokens)
      (Sends question text only, fastest & lowest token usage)
============================================================
Select mode [1/2] (default: 1): 
```

### 2. Direct Flag Overrides (Non-Interactive)

You can pass flags directly to bypass the prompt:

- **Mode 1: Classify + Spacing Fix**:
  ```bash
  python classify/classify.py path/to/question_bank.md --fix-spacing
  ```

- **Mode 2: Classification Only (Minimal Tokens)**:
  ```bash
  python classify/classify.py path/to/question_bank.md --classify-only
  ```

### 3. Custom Topics File
```bash
python classify/classify.py path/to/question_bank.md -t path/to/custom_topics.md
```

### 4. Save to a New Output File (Preserves Original)
```bash
python classify/classify.py path/to/question_bank.md -o path/to/question_bank_classified.md
```

### 5. Skip Automatic Rearranging/Sorting
If you only want topic tags and the Topic Index updated without changing the question sequence:
```bash
python classify/classify.py path/to/question_bank.md --no-sort
```

### 6. Custom Model or Batch Size
```bash
# Use DeepSeek or another model
python classify/classify.py path/to/question_bank.md -m deepseek/deepseek-chat

# Custom batch size
python classify/classify.py path/to/question_bank.md -b 30
```

---

## Standalone Post-Sorting (`postsort.py`)

To rearrange an already classified markdown file by topic without running any API calls:

```bash
# In-place sort
python classify/postsort.py path/to/question_bank.md -t classify/topics.md

# Output to a separate file
python classify/postsort.py path/to/question_bank.md -t classify/topics.md -o path/to/sorted.md
```

---

## Options Reference

#### `classify.py`
| Argument | Description | Default |
|---|---|---|
| `md_file` | Path to the input Markdown file | *(Required)* |
| `--fix-spacing` | Fix OCR spacing in questions and options + classify | Prompts interactively |
| `--classify-only`| Classify only (most minimal token consumption) | Prompts interactively |
| `-t`, `--topics` | Path to topics `.md` file | `classify/topics.md` |
| `-o`, `--output` | Path to output Markdown file | In-place overwrite |
| `-m`, `--model` | OpenRouter model ID | `google/gemini-2.5-flash-lite` |
| `-k`, `--api-key` | OpenRouter API key | From environment or `classify/.env` |
| `-b`, `--batch-size` | Questions per API call | `25` |
| `--no-sort` | Disable automatic post-sorting | `False` (sorts by default) |

#### `postsort.py`
| Argument | Description | Default |
|---|---|---|
| `md_file` | Path to the input Markdown file | *(Required)* |
| `-t`, `--topics` | Path to topics `.md` file for ordering | `classify/topics.md` |
| `-o`, `--output` | Path to output Markdown file | In-place overwrite |
