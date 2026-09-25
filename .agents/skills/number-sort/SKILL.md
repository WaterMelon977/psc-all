---
name: number-sort
description: Sort APPSC and State PSC markdown question banks numerically by question number (## Question <num>) directly in-place across the whole document.
---

# Number Sort Skill (`number-sort`)

This skill sorts markdown question banks numerically by question header (`## Question 1`, `## Question 2`, ... `## Question 150`) **directly in the markdown file itself**.

---

## When to Use

Activate this skill when:
- Question bank markdown files have questions out of numerical order or split by topic sections.
- You need the document sorted globally and sequentially from Question 1 to N directly in the `.md` file itself without generating separate files.

---

## Script Locations

- Workspace root: [`d:/appsc-loaded/number_sort.py`](file:///d:/appsc-loaded/number_sort.py)
- Skill copy: [`d:/appsc-loaded/.agents/skills/number-sort/number_sort.py`](file:///d:/appsc-loaded/.agents/skills/number-sort/number_sort.py)

---

## Command

To sort any markdown question bank directly in-place:

```bash
python number_sort.py <path_to_markdown_file>
```

### Examples:

```bash
# Sort directly in-place (creates a .bak backup)
python number_sort.py d:\appsc-loaded\endowments\pdfs\2019-GSMA-commissioner\2019-GSMA-commissioner.md

# Sort directly in-place without creating a backup
python number_sort.py d:\appsc-loaded\endowments\pdfs\2019-GSMA-commissioner\2019-GSMA-commissioner.md --no-backup
```
