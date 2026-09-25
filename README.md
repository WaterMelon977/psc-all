# Question Markdown Number Sorter (`number_sort.py`)

A fast, lightweight CLI utility and Python script to sort question blocks in State PSC and APPSC markdown question bank files numerically (`## Question 1`, `## Question 2`, ... `## Question 150`) **directly in the markdown file itself**.

---

## Features

- **Direct In-Place Sorting**: Overwrites and sorts the `.md` file directly in place without creating new files.
- **Global Numerical Order**: Questions are sorted strictly in ascending order from Question 1 to Question N across the entire paper.
- **Removes Displaced Section Dividers**: Strips topic headers that were separating questions, giving a pure, sequential exam question bank.
- **Automatic Safety Backup**: Automatically creates a `.bak` copy prior to writing (can be disabled with `--no-backup`).
- **Clean Structure**: Guarantees each question block is properly terminated with `---` dividers and uniform spacing.

---

## Usage

### Sort a file directly in-place:
```bash
python number_sort.py path/to/question_bank.md
```

### Example on 2019-GSMA-commissioner.md:
```bash
python number_sort.py d:\appsc-loaded\endowments\pdfs\2019-GSMA-commissioner\2019-GSMA-commissioner.md
```

### Sort without creating a `.bak` backup file:
```bash
python number_sort.py path/to/question_bank.md --no-backup
```

---

## CLI Options

| Argument | Description |
| :--- | :--- |
| `file` | Path to the markdown question bank file to sort in-place. |
| `-o, --output` | (Optional) Destination file path if you prefer writing to an alternate file instead of in-place. |
| `--no-backup` | Do not create a `.bak` file during in-place sorting. |

---

## Python API Usage

```python
from number_sort import sort_markdown_file

# Sorts in-place directly in the markdown file:
sort_markdown_file("d:/appsc-loaded/endowments/pdfs/2019-GSMA-commissioner/2019-GSMA-commissioner.md")
```
