Below is the complete **implementation specification / prompt** you can give directly to Antigravity. It intentionally contains **no implementation code**; it tells the coding agent what to build, why, the expected architecture, schemas, behavior, and acceptance criteria.

```md
# APPSC PDF → Structured Markdown Question Bank Converter

## Project Status

This document is the complete functional and technical specification for building a Python utility that converts standardized APPSC examination question-paper PDFs into a clean, structured Markdown question bank.

IMPORTANT:

- Do NOT implement an AI/LLM-based solution.
- Do NOT over-engineer unusual PDF/OCR edge cases.
- The input PDFs are proper, standardized APPSC examination documents.
- The primary extraction mechanism should use PyMuPDF and the actual PDF text/span/color information.
- The system must preserve the information present in the PDF accurately.
- Markdown is an output format; `questions.json` is the canonical structured representation.
- Topic classification is deterministic and configuration-driven.
- Do not generate explanations for answers.

---

# 1. Objective

Build a Python command-line utility that accepts an APPSC question-paper PDF and produces a structured output directory containing:

```text
output/
├── <paper_name>.md
├── <paper_name>.json
├── <paper_name>_review.md
└── <paper_name>_report.json
```

The converter should:

1. Read the APPSC PDF.
2. Extract the English questions.
3. Discard the Telugu duplicate of each question.
4. Preserve the original question numbers exactly as they appear in the PDF.
5. Extract all options.
6. Determine the correct answer from the option text colors.
7. Identify the topic for every question.
8. Assign exactly one topic to every question.
9. Generate a study-friendly Markdown file.
10. Generate clean structured JSON containing the questions.
11. Generate a small review file only when something requires attention.
12. Generate a technical report containing processing metadata and diagnostics.

---

# 2. Important Characteristics of the Input PDF

The APPSC PDFs being processed are proper standardized documents.

The expected structure is approximately:

```text
Question Number: 147

[Telugu question]

1. [Telugu option]
2. [Telugu option]
3. [Telugu option]
4. [Telugu option]

Question Number: 147

[English question]

1. [English option]
2. [English option]
3. [English option]
4. [English option]
```

The English question is the canonical question.

The Telugu version is not required in the output.

The English and Telugu versions have the same question number.

The Telugu question is normally immediately associated with the English version.

The input documents are standardized enough that the implementation should prioritize the normal structure rather than attempting to solve every imaginable malformed-PDF problem.

---

# 3. Language Handling

## 3.1 English Only

The generated question bank must contain only English.

Do NOT include:

- Telugu questions
- Telugu options
- Telugu duplicate questions
- Telugu text in the Markdown output

The canonical question is the English version.

---

# 4. Telugu Duplicate Handling

Every normal question has an English/Telugu pair.

The Telugu version must be removed.

Example input:

```text
Q147 Telugu
Q147 English
```

Output:

```text
Q147 English
```

The implementation should recognize the language using Unicode/text characteristics rather than relying exclusively on physical positioning.

The intended strategy is:

1. Identify question blocks.
2. Determine whether the block is Telugu or English.
3. Group by question number.
4. Retain the English version.
5. Discard the Telugu version.

The user has stated that there is no realistic scenario where the English and Telugu versions with the same question number are widely separated or arbitrarily reordered.

Do not build an elaborate fuzzy-matching system for this.

---

# 5. Question Number Handling

Question numbers are authoritative.

If the PDF says:

```text
Question 147
Question 148
Question 149
```

the output must use:

```text
147
148
149
```

Do NOT renumber questions sequentially.

Do NOT infer a new question number from position.

Do NOT change the PDF's numbering.

The question number should be preserved exactly as the logical question identifier.

---

# 6. English-Only Questions

Although the standard document normally contains English/Telugu pairs, the implementation must not assume that an English question always has a Telugu counterpart.

If an English question exists without a Telugu counterpart:

- retain it
- process it normally
- do not skip it

The converter should not depend on every question having a duplicate.

---

# 7. Answer Detection

## 7.1 Source of Truth

The PDF visually identifies answers using colors:

- Green = correct answer
- Red = incorrect answer

The correct answer must be determined from the actual PDF text/span color information whenever possible.

PyMuPDF should be the primary PDF-processing library.

The implementation should inspect text spans and their properties rather than merely extracting plain text.

Relevant PDF span information may include:

- text
- color
- bounding box
- font
- size
- flags
- block/line/span structure

---

# 8. Color Detection

Do NOT rely on exact RGB equality.

For example, do not assume that only one exact RGB tuple can represent green.

Use a configurable color tolerance/range.

The system should be able to recognize the intended green and red colors even if the PDF contains minor color variations.

The design should have centralized/configurable answer-color detection rather than scattering RGB assumptions throughout the implementation.

Conceptually:

```text
GREEN → correct
RED   → incorrect
```

The exact implementation should use the PDF's actual color representation discovered during development/testing.

---

# 9. Multiple Green Options

If multiple options are green:

```text
1. red
2. green
3. green
4. red
```

then all green options must be treated as correct.

Do NOT arbitrarily choose:

- first green
- last green
- lowest-numbered green

The structured answer should support multiple option numbers.

Example:

```json
"answer": [2, 3]
```

For the normal case:

```json
"answer": [4]
```

Even if APPSC normally has one correct option, the data model must support multiple green options because the user's explicit requirement is to pick all green options.

---

# 10. Missing/Undetectable Answer

If no usable green option can be detected:

1. Do not guess.
2. Do not invent an answer.
3. Continue processing the rest of the PDF.
4. Record the question in `review.md`.
5. Record the relevant technical information in `report.json`.

The question should still exist in `questions.json` and Markdown.

For example:

```json
"answer": []
```

or another clean representation indicating that no answer was detected.

The implementation must establish one consistent representation and use it everywhere.

---

# 11. No Artificial Error Stopping

A single problematic question must not cause the entire PDF conversion to fail.

Example:

```text
Q1 → successful
Q2 → successful
Q3 → answer color unavailable
Q4 → successful
Q5 → successful
```

The converter should still produce all outputs.

`Q3` should appear in `review.md`.

The script should finish processing the document.

---

# 12. Topic Classification

There are exactly 10 topics.

The user will provide the topics.

The user will also provide:

- keywords
- weighted keywords
- regular expressions
- subtopics where useful

Topic configuration will be stored externally in:

```text
topics.yaml
```

The converter must NOT hard-code the 10 topics into Python source code.

---

# 13. Topic Assignment

Every question must receive exactly one topic.

There is no multi-topic assignment.

Each question must ultimately have:

```text
topic = exactly one topic
```

Even if a question touches multiple areas, the deterministic classifier must select one topic.

---

# 14. Topic Ordering

The topics must appear in exactly the order specified by the user in `topics.yaml`.

Do NOT alphabetically sort them.

Do NOT reorder them according to question frequency.

Do NOT reorder them according to first appearance in the PDF.

The configuration order is authoritative.

Example:

```yaml
topics:
  - Strength of Materials
  - Fluid Mechanics
  - Material Science
  - Theory of Machines
  - Machine Design
  - Thermodynamics
  - Heat Transfer
  - Refrigeration and Air Conditioning
  - IC Engines
  - Production Technology
```

If this is the order supplied by the user, it should remain the order used in the generated topic index.

---

# 15. Topic Classification Method

Classification must be deterministic.

No AI.

No API.

No LLM.

No external model.

The classifier should use:

1. weighted keywords
2. regular expressions
3. configurable scoring

Each topic has classification rules.

Conceptually:

```text
Question
    ↓
Check against Topic 1
    ↓
Check against Topic 2
    ↓
...
    ↓
Check against Topic 10
    ↓
Calculate scores
    ↓
Highest score
    ↓
Assign exactly one topic
```

---

# 16. Weighted Keywords

Keywords should support weights.

Example concept:

```yaml
centrifugal pump: 10
reciprocating pump: 10
pump: 3
head: 1
efficiency: 1
```

A highly specific phrase should contribute more to the topic score than a generic word.

The implementation should normalize text appropriately before matching where useful.

Potential normalization includes:

- case normalization
- whitespace normalization
- punctuation normalization

Do not aggressively rewrite the question because the original text needs to remain untouched.

---

# 17. Regular Expressions

The topic configuration must support regular expressions in addition to simple keywords.

This allows rules such as:

```text
centrifugal\s+pump
```

or other useful domain-specific patterns.

The configuration should clearly distinguish:

- normal keyword
- regex pattern
- weight

The exact YAML schema can be designed during implementation, but it should remain easy for a human to edit.

The user should not need to modify Python code when changing topic classification rules.

---

# 18. Topic Configuration

The user wants:

```text
topics.yaml
```

to be a separate configuration file.

The CLI should support passing it explicitly.

Conceptually:

```text
python app.py <paper.pdf> <topics.yaml>
```

This is preferred over hard-coding a fixed topics file.

The reason is that the same converter may eventually be used for different APPSC examinations or different syllabi.

---

# 19. Topic Classification Ambiguity

The final output must still contain exactly one topic.

Do not leave:

```text
topic: null
```

for ordinary classification ambiguity.

The classifier should calculate scores and select the highest scoring topic.

The implementation can record useful technical information about scores in `report.json`.

However, do not overcomplicate the normal output with confidence systems unless genuinely useful.

---

# 20. Markdown Design Goals

The Markdown must be designed for:

- studying
- searching
- navigation
- future conversion
- readability
- use in Markdown editors
- possible future use in Obsidian or similar tools

Do not make it visually decorative.

Do not duplicate the full questions under every topic.

The actual questions should appear only once.

---

# 21. Markdown Ordering

The actual questions must remain in the original PDF/question order.

For example:

```text
Q1
Q2
Q3
Q4
...
Q147
```

The Markdown must not rearrange the actual question sequence by topic.

---

# 22. Markdown Topic Index

At the top of the Markdown file, include a topic index.

The topic index should contain question numbers grouped under each topic.

Example:

```md
# APPSC Question Bank

## Topic Index

### Strength of Materials

- Q3
- Q17
- Q41

### Fluid Mechanics

- Q2
- Q8
- Q22

### Thermodynamics

- Q14
- Q37
- Q147
```

The topics must appear in the exact order from `topics.yaml`.

The topic index is only an index.

Do NOT duplicate the complete question text here.

---

# 23. Question Markdown Format

The required question format is:

```md
## Question 147

**Topic:** Thermodynamics

### Question

Which of the following statements is correct?

### Options

1. First option
2. Second option
3. Third option
4. Fourth option

### Answer

> **Answer: 4**
```

Use this structure consistently.

---

# 24. Question Heading

The heading must be:

```md
## Question 147
```

NOT:

```md
## Q147 — Thermodynamics
```

The topic must be a separate line:

```md
**Topic:** Thermodynamics
```

This is the user's explicit preferred format.

---

# 25. Question Text

The question text should contain the English question only.

Preserve the meaning and wording from the PDF.

Do not:

- translate
- summarize
- paraphrase
- rewrite
- explain

Basic whitespace cleanup is acceptable and expected.

---

# 26. Options

Options must be represented as a Markdown numbered list:

```md
### Options

1. Option one
2. Option two
3. Option three
4. Option four
```

The original option numbering should be retained.

Do not renumber based on extraction order if the PDF provides explicit option numbers.

---

# 27. Answer Format

The answer must contain ONLY the option number(s).

Example:

```md
### Answer

> **Answer: 4**
```

Do NOT output:

```md
> **Answer: 4 — First Law of Thermodynamics**
```

Do NOT include answer text.

The user's explicit requirement is the option number.

---

# 28. Multiple Answers in Markdown

If multiple options are detected as green, represent all of them clearly.

For example:

```md
### Answer

> **Answer: 2, 4**
```

The exact separator can be standardized as comma + space.

---

# 29. Explanations

STRICT REQUIREMENT:

Do not generate explanations.

Do not infer explanations.

Do not add:

- why the answer is correct
- why other options are wrong
- textbook explanations
- external knowledge
- AI-generated explanations

The output is a question bank, not a solution manual.

---

# 30. Questions JSON

`questions.json` is the canonical structured master data.

It is NOT simply a Markdown dump converted to JSON.

It should represent the questions as structured objects.

Conceptual structure:

```json
{
  "question_number": 147,
  "question": "Which of the following statements is correct?",
  "options": {
    "1": "First option",
    "2": "Second option",
    "3": "Third option",
    "4": "Fourth option"
  },
  "answer": [4],
  "topic": "Thermodynamics"
}
```

---

# 31. JSON Requirements

Every successfully extracted question should contain:

- question number
- English question text
- options
- answer option number(s)
- exactly one topic

Technical extraction metadata should NOT clutter `questions.json`.

Keep it clean enough that another application can consume it directly.

Potential future consumers include:

- quiz application
- React frontend
- Anki generator
- MCQ test generator
- topic-wise practice system
- random-question generator
- database import

---

# 32. Report JSON

Technical metadata belongs in:

```text
<name>_report.json
```

rather than `questions.json`.

The report may contain:

- input filename
- processing timestamp
- number of pages
- number of detected question blocks
- number of English questions
- number of Telugu questions discarded
- number of questions retained
- number of questions with detected answers
- number of questions requiring review
- topic distribution
- answer detection statistics
- classification statistics
- processing duration
- warnings/errors
- color-detection information
- other useful implementation diagnostics

The report should be machine-readable.

---

# 33. Review Markdown

The review file is:

```text
<name>_review.md
```

It should contain ONLY items requiring human attention.

Do not dump every successful operation.

Example:

```md
# Review Required

## Question 183

**Page:** 47

**Issue:** Could not determine the correct answer from option colors.

---

## Question 194

**Page:** 51

**Issue:** Multiple green options detected.

**Detected options:** 2, 4
```

If there are no issues:

```md
# Review Required

No issues detected.
```

The file should remain concise.

---

# 34. Output Naming

If the input is:

```text
APPSC_ME_2026.pdf
```

the output should be:

```text
output/
├── APPSC_ME_2026.md
├── APPSC_ME_2026.json
├── APPSC_ME_2026_review.md
└── APPSC_ME_2026_report.json
```

The JSON file without `_report` is the question database:

```text
APPSC_ME_2026.json
```

The `_report.json` file is technical metadata.

Do not use generic names such as:

```text
paper.md
questions.json
review.md
report.json
```

because multiple papers may be processed.

---

# 35. CLI

The intended usage is:

```text
python app.py <paper.pdf> <topics.yaml>
```

Example:

```text
python app.py APPSC_ME_2026.pdf topics.yaml
```

The script should automatically create:

```text
output/
```

if it does not exist.

---

# 36. Suggested CLI Behavior

The CLI should provide concise progress information.

For example:

```text
Loading PDF...
Extracting questions...
Detected 200 question blocks.
Retaining 200 English questions.
Discarded 200 Telugu duplicates.
Detecting answers...
Classifying topics...
Generating Markdown...
Generating JSON...
Generating report...

Completed.

Questions: 200
Answers detected: 199
Review required: 1

Output:
output/APPSC_ME_2026.md
output/APPSC_ME_2026.json
output/APPSC_ME_2026_review.md
output/APPSC_ME_2026_report.json
```

The CLI should not be excessively verbose.

---

# 37. Recommended Architecture

Separate the application into logical stages.

Do not make one giant function that:

- reads PDF
- detects colors
- classifies topics
- writes Markdown

in one block.

Use a clean pipeline.

Conceptually:

```text
PDF
 │
 ▼
PDF Extraction
 │
 ▼
Raw Question Blocks
 │
 ▼
Language / Duplicate Filtering
 │
 ▼
English Question Objects
 │
 ├───────────────┐
 ▼               ▼
Answer Detection Topic Classification
 │               │
 └───────┬───────┘
         ▼
Structured Question Model
         │
         ├───────────────┐
         ▼               ▼
    questions.json    Markdown
         │
         └───────┐
                 ▼
          Report / Review
```

---

# 38. Separation of Concerns

The implementation should conceptually have separate responsibilities for:

## PDF extraction

Responsible for:

- opening PDF
- reading pages
- extracting blocks/lines/spans
- preserving text and color information
- identifying question blocks

## Language detection

Responsible for:

- determining English vs Telugu
- filtering Telugu blocks

## Question parser

Responsible for:

- question number
- question text
- options
- block boundaries

## Answer detector

Responsible for:

- identifying green options
- identifying red options where useful
- handling color tolerance
- returning all green option numbers
- reporting missing/ambiguous answer information

## Topic classifier

Responsible for:

- loading `topics.yaml`
- keyword matching
- weighted matching
- regex matching
- calculating scores
- selecting exactly one topic

## Markdown renderer

Responsible for:

- topic index
- question formatting
- answer formatting
- preserving question order

## JSON renderer

Responsible for:

- clean structured question data

## Report generator

Responsible for:

- diagnostics
- processing statistics
- warnings

## Review generator

Responsible for:

- human-review items only

---

# 39. Do Not Over-Engineer PDF Recovery

The user explicitly stated that these are proper APPSC documents.

Therefore, do not spend excessive complexity on:

- arbitrary OCR recovery
- heavily malformed PDFs
- image-only scanned documents
- wildly reordered text
- complex diagrams
- questions split unpredictably across pages
- arbitrary multi-column reconstruction
- unusual font encodings
- generalized PDF forensic recovery

The implementation should be robust for the actual standardized APPSC PDF format.

If a genuinely unexpected extraction failure occurs, record it in the review/report instead of building a huge recovery subsystem.

---

# 40. PyMuPDF

PyMuPDF should be the primary PDF library.

The implementation should investigate the actual PDF representation of:

- question text
- option text
- text spans
- text color
- block/line ordering
- page numbers

The development process should verify how the APPSC PDF encodes the green and red option colors.

Do not assume visual colors necessarily map to the same representation without inspecting a real sample PDF.

---

# 41. Color Detection Design

The answer detector should work at the option level.

Conceptually:

```text
Option 1 → inspect spans → determine color
Option 2 → inspect spans → determine color
Option 3 → inspect spans → determine color
Option 4 → inspect spans → determine color
```

If an option consists of multiple text spans, the implementation should aggregate their color information sensibly rather than depending on one arbitrary character/span.

The normal expected case is that the entire option is consistently colored.

---

# 42. Red Detection

Red is not strictly necessary to identify the answer if green is reliable.

Green is the primary positive signal.

Red can be used as supporting validation.

Expected normal state:

```text
three/four options → red
one option → green
```

If an option is neither clearly red nor green, this should not automatically be treated as correct or incorrect.

The system should rely primarily on the explicit green signal.

---

# 43. Answer Validation

The converter should perform basic sanity checks.

For example:

```text
Question has 4 options
Answer contains option 4
```

is valid.

But:

```text
Question has 4 options
Answer contains option 7
```

is invalid and should be reviewed.

Similarly:

```text
Question has no options
```

should be recorded as an extraction issue.

These validations should be lightweight and appropriate for the standardized document.

---

# 44. Question Parsing

The parser should identify:

- question number
- question text
- option boundaries
- option numbers
- option text
- language

Expected option numbering is likely:

```text
1.
2.
3.
4.
```

or an equivalent APPSC representation.

The implementation should use the PDF's actual structure rather than assuming every option is a single line.

Normal multi-line option text should remain part of the same option.

---

# 45. Text Cleanup

Perform conservative cleanup.

Allowed:

- normalize excessive whitespace
- remove accidental extraction artifacts
- normalize line breaks where clearly appropriate
- clean duplicated whitespace
- remove irrelevant PDF layout artifacts when clearly identifiable

Do NOT:

- paraphrase
- rewrite questions
- correct factual content
- "improve" English
- alter mathematical notation unnecessarily
- alter option wording

The PDF content is authoritative.

---

# 46. Header/Footer Handling

Standard repeated page headers/footers should not become part of questions.

However, do not build an elaborate generic header/footer AI.

Use the predictable structure of the APPSC document.

If a repeated page-level element is clearly not part of the question content, exclude it.

---

# 47. Topic Index Generation

The topic index must be generated from the final structured question objects.

Example:

```md
## Topic Index

### Strength of Materials

- Q1
- Q7
- Q23

### Fluid Mechanics

- Q2
- Q11
- Q31
```

Only question numbers should be listed.

The actual question content appears later once.

---

# 48. Topic Index Order

Use the exact order from `topics.yaml`.

If:

```yaml
topics:
  - Topic A
  - Topic B
  - Topic C
```

then Markdown must use:

```text
Topic A
Topic B
Topic C
```

even if Topic C appears first in the PDF.

---

# 49. Question Order

The actual questions section follows PDF/question order.

Example:

```md
# Questions

## Question 1
...

## Question 2
...

## Question 3
...
```

Do not reorder by topic.

---

# 50. Full Markdown Example

The final Markdown should look approximately like:

```md
# APPSC Question Bank

## Topic Index

### Strength of Materials

- Q3
- Q12
- Q41

### Fluid Mechanics

- Q2
- Q18
- Q37

### Material Science

- Q4
- Q21

### Theory of Machines

- Q7
- Q25

### Machine Design

- Q9
- Q31

### Thermodynamics

- Q14
- Q28
- Q147

### Heat Transfer

- Q11
- Q36

### Refrigeration and Air Conditioning

- Q16
- Q43

### IC Engines

- Q19
- Q44

### Production Technology

- Q5
- Q30

---

# Questions

## Question 1

**Topic:** Strength of Materials

### Question

Which of the following statements is correct?

### Options

1. First option
2. Second option
3. Third option
4. Fourth option

### Answer

> **Answer: 2**

---

## Question 2

**Topic:** Fluid Mechanics

### Question

Which of the following is true regarding fluid flow?

### Options

1. First option
2. Second option
3. Third option
4. Fourth option

### Answer

> **Answer: 4**

---

## Question 3

**Topic:** Strength of Materials

### Question

Another question...

### Options

1. ...
2. ...
3. ...
4. ...

### Answer

> **Answer: 1**
```

This is the target style.

---

# 51. JSON Example

Conceptually:

```json
{
  "questions": [
    {
      "question_number": 1,
      "question": "Which of the following statements is correct?",
      "options": {
        "1": "First option",
        "2": "Second option",
        "3": "Third option",
        "4": "Fourth option"
      },
      "answer": [2],
      "topic": "Strength of Materials"
    },
    {
      "question_number": 2,
      "question": "Which of the following is true regarding fluid flow?",
      "options": {
        "1": "First option",
        "2": "Second option",
        "3": "Third option",
        "4": "Fourth option"
      },
      "answer": [4],
      "topic": "Fluid Mechanics"
    }
  ]
}
```

The JSON should remain clean.

---

# 52. Topic YAML Design

The topic configuration should be human-editable.

The implementation should define a clean YAML structure supporting:

- ordered topics
- weighted keywords
- regular expressions

A reasonable conceptual structure is:

```yaml
topics:

  - name: Strength of Materials
    keywords:
      stress: 3
      strain: 3
      bending moment: 8
      torsion: 8
    regex:
      - pattern: "\\bSFD\\b"
        weight: 8

  - name: Fluid Mechanics
    keywords:
      viscosity: 5
      bernoulli: 10
      reynolds number: 8
      pipe flow: 7
    regex:
      - pattern: "centrifugal\\s+pump"
        weight: 10
```

The exact schema may be refined during implementation, but it should preserve these capabilities.

---

# 53. Topic Matching

Matching should be deterministic.

For each question:

```text
score(topic) =
    sum(weight of matched keywords)
    +
    sum(weight of matched regex patterns)
```

The topic with the highest score is selected.

The implementation should avoid double-counting the same exact match excessively unless intentionally designed.

The classifier should be simple enough to debug.

---

# 54. Topic Distribution

`report.json` should provide topic counts.

Example:

```json
{
  "topic_distribution": {
    "Strength of Materials": 23,
    "Fluid Mechanics": 19,
    "Material Science": 17,
    "Theory of Machines": 21,
    "Machine Design": 20,
    "Thermodynamics": 25,
    "Heat Transfer": 16,
    "Refrigeration and Air Conditioning": 12,
    "IC Engines": 18,
    "Production Technology": 29
  }
}
```

This makes it easy to verify the classification.

---

# 55. Validation

Before writing the final outputs, perform basic validation.

Check:

1. Every retained question has a question number.
2. Every retained question has English text.
3. Every retained question has options.
4. Every question has exactly one topic.
5. Every detected answer number corresponds to an existing option.
6. No Telugu text is present in the final English question bank.
7. The number of structured questions is internally consistent.
8. Topic index references only questions that actually exist.
9. Question order in Markdown matches structured data.
10. JSON and Markdown represent the same question set.

---

# 56. Duplicate Validation

The normal Telugu/English duplication must not result in duplicate questions in the final data.

For example:

```text
Telugu Q147
English Q147
```

must result in:

```text
one Q147
```

The Telugu block must not appear in:

- Markdown
- questions JSON
- topic index

---

# 57. Question Number Validation

Do not silently modify question numbers.

If duplicate English question numbers somehow occur:

```text
English Q147
English Q147
```

do not arbitrarily delete one.

Record the anomaly in `review.md` / `report.json`.

However, do not create elaborate duplicate-resolution logic because the source document is expected to be standardized.

---

# 58. Review Philosophy

`review.md` is for things that genuinely deserve human inspection.

Examples:

- no green answer detected
- invalid answer option number
- duplicate English question number
- question could not be parsed
- options could not be reliably extracted
- unexpected language/extraction state

Do NOT include:

- every successful question
- every successful color match
- every normal topic classification
- excessive debug information

---

# 59. Report vs Review

Keep these separate.

## review.md

Human-readable action list.

Example:

```md
# Review Required

## Question 183

**Issue:** No green answer option detected.

**Page:** 47
```

## report.json

Machine-readable processing statistics and diagnostics.

Example:

```json
{
  "total_pages": 60,
  "questions_detected": 200,
  "english_questions": 200,
  "telugu_questions_removed": 200,
  "answers_detected": 199,
  "review_items": 1
}
```

---

# 60. No AI Dependency

The converter must run without:

- OpenAI
- Gemini
- Claude
- DeepSeek
- local LLM
- external API
- internet connection

The entire conversion should be deterministic and local.

The only semantic classification is based on user-provided:

- keywords
- weights
- regex rules

---

# 61. Reproducibility

Running:

```text
python app.py paper.pdf topics.yaml
```

multiple times on the same inputs should produce logically identical outputs.

There should be no random behavior.

No random topic assignment.

No AI variability.

No network dependency.

---

# 62. Future Extensibility

Do not over-engineer now, but keep the architecture clean enough that future output formats can be added.

Potential future formats:

```text
CSV
Anki
HTML
quiz JSON
database import
React quiz application
```

This is another reason `questions.json` should be the structured master representation.

The Markdown renderer should consume the structured questions rather than directly consuming raw PDF extraction.

---

# 63. Important Non-Goals

Do NOT implement the following unless required by the actual document:

- AI question answering
- generated explanations
- automatic factual correction
- translation
- OCR-heavy processing
- generalized PDF forensic parsing
- diagram interpretation
- image question solving
- answer inference from semantic knowledge
- web search
- external API calls
- question difficulty prediction
- duplicate semantic similarity engines
- question quality scoring

The goal is a reliable document converter, not an AI exam platform.

---

# 64. Development Strategy

Before implementing the full converter, inspect one representative APPSC PDF carefully.

Specifically determine:

1. How PyMuPDF represents the question text.
2. How PyMuPDF represents option text.
3. How green is represented.
4. How red is represented.
5. How blocks and lines are ordered.
6. How English/Telugu versions are represented.
7. How question numbers appear.
8. How option numbers appear.

Then design the parser around the actual document structure.

Do not blindly assume PDF extraction behavior.

---

# 65. Testing Strategy

Create tests around the actual expected structure.

At minimum test:

### Test 1 — Normal question

```text
English question
4 options
one green option
```

Expected:

```text
one structured question
one answer
one topic
```

### Test 2 — Telugu + English

Expected:

```text
Telugu removed
English retained
```

### Test 3 — Multiple green options

Expected:

```text
answer = [2, 4]
```

### Test 4 — No green option

Expected:

```text
question retained
answer empty/unknown
review item generated
```

### Test 5 — English-only question

Expected:

```text
question retained
```

### Test 6 — Topic keyword match

Expected correct topic.

### Test 7 — Weighted topic conflict

A highly specific keyword should beat several generic keywords where configured accordingly.

### Test 8 — Regex topic match

Regex rule should contribute its configured weight.

### Test 9 — Output consistency

Verify:

```text
questions.json
        ↕
paper.md
```

contain the same questions, options, answers, and topics.

---

# 66. Acceptance Criteria

The project is considered complete when the following are true.

## Input

Running:

```text
python app.py <paper.pdf> <topics.yaml>
```

successfully processes a normal APPSC question paper.

## Questions

- English questions are retained.
- Telugu duplicates are removed.
- English-only questions are retained.
- Original question numbers are preserved.
- Options are correctly extracted.

## Answers

- Green options are detected.
- Red options are treated as incorrect/supporting information.
- All green options are included.
- Missing answer detection does not crash the whole process.
- No answer is guessed.

## Topics

- Topics come from `topics.yaml`.
- Topic order comes from `topics.yaml`.
- Weighted keywords work.
- Regex rules work.
- Every question receives exactly one topic.
- No AI/API is required.

## Markdown

Generated Markdown:

- contains a topic index
- contains questions in PDF order
- does not duplicate questions
- uses `## Question N`
- uses `**Topic:** Topic`
- uses `### Question`
- uses `### Options`
- uses numbered options
- uses `### Answer`
- uses a blockquote answer
- contains only answer option number(s)
- contains no explanations
- contains English only

## JSON

The main JSON:

- contains clean structured questions
- contains question number
- contains question
- contains options
- contains answer number(s)
- contains topic
- does not contain excessive technical metadata

## Report

The report:

- records processing statistics
- records topic distribution
- records review count
- records useful technical diagnostics

## Review

The review file:

- contains only exceptional items
- is human-readable
- does not stop the conversion process

---

# 67. Final Desired Project Structure

The implementation may use a structure similar in concept to:

```text
project/
│
├── app.py
├── topics.yaml
├── requirements.txt
│
├── src/
│   ├── pdf_extractor
│   ├── question_parser
│   ├── language_detector
│   ├── answer_detector
│   ├── topic_classifier
│   ├── markdown_renderer
│   ├── json_renderer
│   ├── report_generator
│   └── review_generator
│
├── tests/
│
├── input/
│
└── output/
```

The exact Python module structure is up to the implementation agent.

Do not unnecessarily fragment the project into dozens of modules.

The important requirement is separation of responsibilities.

---

# 68. Core Design Principle

The most important architectural principle is:

```text
PDF
 ↓
Structured Question Data
 ↓
 ├── Markdown
 ├── Questions JSON
 ├── Review
 └── Report
```

NOT:

```text
PDF
 ↓
Markdown directly
```

`questions.json` is the canonical structured representation.

Markdown is a presentation/output layer.

---

# 69. Final Example of Desired User Workflow

The user should eventually be able to do:

```text
python app.py APPSC_ME_2026.pdf topics.yaml
```

and receive:

```text
output/
├── APPSC_ME_2026.md
├── APPSC_ME_2026.json
├── APPSC_ME_2026_review.md
└── APPSC_ME_2026_report.json
```

The main Markdown should be immediately usable as a clean study document.

The JSON should be immediately usable as structured question-bank data.

The review file should tell the user exactly what, if anything, needs manual inspection.

The report should provide enough metadata to understand what the converter processed.

---

# 70. Priority Order

When making implementation decisions, prioritize requirements in this order:

1. Correct extraction of English questions.
2. Correct removal of Telugu duplicates.
3. Correct preservation of question numbers.
4. Correct option extraction.
5. Correct green-option answer detection.
6. No fabricated answers.
7. Correct deterministic topic assignment.
8. Clean structured JSON.
9. Clean study-friendly Markdown.
10. Useful review/report output.
11. Simplicity and maintainability.
12. Edge-case handling only where it is relevant to the actual APPSC PDFs.

Do not sacrifice reliability and simplicity in the normal APPSC document format merely to support hypothetical malformed PDFs.

---

# 71. What the Implementation Agent Should Do First

Before writing the complete implementation:

1. Inspect the actual sample APPSC PDF.
2. Determine the exact PyMuPDF extraction structure.
3. Verify how the green/red colors appear in PDF spans.
4. Verify the English/Telugu block pattern.
5. Verify question-number and option-number extraction.
6. Propose the final internal data model.
7. Implement the parser and answer detector.
8. Test against representative questions.
9. Implement topic classification.
10. Implement Markdown/JSON/report/review generation.
11. Run an end-to-end conversion.
12. Inspect the generated Markdown for readability and correctness.

Do not immediately build a complicated generalized PDF parser.

The implementation should be driven by the actual APPSC document structure.

---

# END OF SPECIFICATION
```