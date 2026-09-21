# Markdown Question Topic Classifier & Sorter

Automated topic classifier and rearranger for APPSC / State PSC question bank Markdown files using **OpenRouter** (`deepseek/deepseek-chat` or any preferred model).

---

## What It Does

1. **Intelligent Question Extraction**:
   - Parses the Markdown file locally without sending full document noise, answers, metadata, or exam tags.
   - For regular questions, only the question stem is sent to minimize token usage.
   - Options are included only conditionally when the question stem is very short (< 50 chars) or missing (e.g., image-based charts/diagrams).

2. **Batched LLM Classification**:
   - Groups questions into batches (default: 25 per request) to minimize repeated token overhead.
   - Enforces strict classification into only the allowed topics defined in `topics.md`.

3. **Topic Tagging & Dynamic Index Rebuilding**:
   - Updates each question's `**Topic:** <Topic Name>` tag.
   - Rebuilds the `## Topic Index` table of contents at the top of the file with clickable question numbers.

4. **Automatic Post-Sorting (`postsort.py`)**:
   - Automatically rearranges all questions grouped under level-1 topic headers (`# <Topic Name>`) in the exact order specified by `topics.md`.
   - Preserves numerical order of questions within each topic group.

---

## Setup

Create a `.env` file in the `classify/` folder (or workspace root) with your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
```

*(You can also pass it explicitly via `--api-key <KEY>` or set it in your system environment variables).*

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

### 1. Classify & Auto-Sort (Standard Flow)
Classifies questions and automatically sorts the file in-place by topic:
```bash
python classify/classify.py path/to/question_bank.md
```

### 2. With Custom Topics File
```bash
python classify/classify.py path/to/question_bank.md -t path/to/custom_topics.md
```

### 3. Save to a New Output File (Preserves Original)
```bash
python classify/classify.py path/to/question_bank.md -o path/to/question_bank_classified.md
```

### 4. Skip Automatic Rearranging/Sorting
If you only want topic tags and the Topic Index updated without changing the question sequence:
```bash
python classify/classify.py path/to/question_bank.md --no-sort
```

### 5. Custom Model or Batch Size
```bash
# Use a specific OpenRouter model
python classify/classify.py path/to/question_bank.md -m deepseek/deepseek-chat

# Custom batch size
python classify/classify.py path/to/question_bank.md -b 30
```

---

## Standalone Post-Sorting (`postsort.py`)

If you have an already-classified markdown file and want to rearrange question blocks grouped by topic at any time without re-running API calls:

```bash
# In-place sort
python classify/postsort.py path/to/question_bank.md -t classify/topics.md

# Output to a separate file
python classify/postsort.py path/to/question_bank.md -t classify/topics.md -o path/to/sorted.md
```

### Options Reference

#### `classify.py`
| Argument | Description | Default |
|---|---|---|
| `md_file` | Path to the input Markdown file | *(Required)* |
| `-t`, `--topics` | Path to topics `.md` file | `classify/topics.md` |
| `-o`, `--output` | Path to output Markdown file | In-place overwrite |
| `-m`, `--model` | OpenRouter model ID | `deepseek/deepseek-chat` |
| `-k`, `--api-key` | OpenRouter API key | From environment or `.env` |
| `-b`, `--batch-size` | Questions per API call | `25` |
| `--no-sort` | Disable automatic post-sorting | `False` (sorts by default) |

#### `postsort.py`
| Argument | Description | Default |
|---|---|---|
| `md_file` | Path to the input Markdown file | *(Required)* |
| `-t`, `--topics` | Path to topics `.md` file for ordering | `classify/topics.md` |
| `-o`, `--output` | Path to output Markdown file | In-place overwrite |
