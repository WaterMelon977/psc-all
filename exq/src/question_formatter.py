"""
Smart question text formatter for Markdown output.

Detects and reformats three patterns:
1. Column I / Column II matching tables  → Markdown table
2. Inline numbered statements            → Numbered list (separate lines)
3. Assertion (A) / Reason (R) blocks     → Labelled block lines
"""

import re
from typing import List, Optional, Tuple


# ─── Column/Matching Table ───────────────────────────────────────────────────

# Matches "Column I" optionally followed by a label in parens, then "Column II"
_COL_HEADER_RE = re.compile(
    r"Column\s+I\b[^C]*?Column\s+II\b",
    re.IGNORECASE
)

def _try_parse_column_table(text: str) -> Optional[str]:
    """
    Detect Column I / Column II pattern and return a Markdown table, or None.

    PDF text looks like:
      "...question... Column I (Person) Column II (Neighbour to the immediate left)
       (i)Q (W)B (ii)P (X)E (iii)D (Y)R (iv)R (Z)F Which is the correct match?"
    
    Strategy:
    - Find header span and extract col labels.
    - Skip optional trailing col2 descriptor (e.g. "(Neighbour to the immediate left)").
    - Tokenise the rest: every "(label)value" chunk.
    - Classify: roman/lower → Left, UPPER/digit → Right.
    - Pair tokens strictly L, R, L, R, …
    - Strip trailing question sentence from the last Right value (it's a short identifier).
    """
    header_match = _COL_HEADER_RE.search(text)
    if not header_match:
        return None

    header_full = text[header_match.start():header_match.end()]
    header_labels = re.findall(r"\(([^)]+)\)", header_full)
    col1_label = header_labels[0].strip() if len(header_labels) >= 1 else "Column I"
    col2_label = header_labels[1].strip() if len(header_labels) >= 2 else "Column II"

    preamble = text[:header_match.start()].strip()

    # After the header regex match, skip any additional col-2 descriptor: "(Neighbour…)"
    after_start = header_match.end()
    label_after = re.match(r"\s*\([^)]+\)", text[after_start:])
    if label_after:
        after_start += label_after.end()

    entries_text = text[after_start:].strip()

    # Tokenise: match every "(label)value" pair where value is up to the next "(" or end
    TOKEN_RE = re.compile(r"\(([^)]+)\)\s*([^\(\)]+?)(?=\s*\(|$)")

    # Classification regexes
    # Left  column labels: lowercase roman numerals (i, ii, iii, iv, v, …) or lowercase alpha
    # Right column labels: uppercase alpha (A-Z) or digits — but MUST be uppercase
    LEFT_LABEL_RE  = re.compile(r"^(?:[ivxl]+|[a-z]{1,3})$")   # lowercase only
    RIGHT_LABEL_RE = re.compile(r"^(?:[A-Z]{1,3}|[0-9]+)$")     # UPPERCASE or digit

    all_tokens: list[tuple[str, str]] = []
    for m in TOKEN_RE.finditer(entries_text):
        label = m.group(1).strip()
        value = m.group(2).strip().rstrip("., ")
        if label and value:
            all_tokens.append((label, value))

    # Classify
    typed: list[tuple[str, str, str]] = []  # (side, label, value)
    for label, value in all_tokens:
        if LEFT_LABEL_RE.match(label):
            typed.append(("L", label, value))
        elif RIGHT_LABEL_RE.match(label):
            typed.append(("R", label, value))

    # Pair L, R, L, R …
    # Right-column values are typically short identifiers (single letters/names).
    # If the last Right value has trailing sentence text after the identifier, strip it.
    left_items:  list[tuple[str, str]] = []
    right_items: list[tuple[str, str]] = []
    expecting = "L"
    for side, label, value in typed:
        if side == expecting == "L":
            left_items.append((label, value))
            expecting = "R"
        elif side == expecting == "R":
            # Right values are short identifiers; strip any trailing prose
            # (e.g. "F Which is the correct match?" → "F")
            first_word = value.split()[0] if " " in value else value
            right_items.append((label, first_word))
            expecting = "L"

    if not left_items or not right_items:
        return None

    # Trailing sentence: everything after the last token in entries_text
    all_matches = list(TOKEN_RE.finditer(entries_text))
    suffix = ""
    if all_matches:
        last_end = all_matches[-1].end()
        candidate = entries_text[last_end:].strip()
        # Also recover the part stripped from the last right value
        last_full_value = all_tokens[-1][1] if all_tokens else ""
        stripped_part = last_full_value[len(right_items[-1][1]):].strip(" .,") if right_items else ""
        if stripped_part:
            suffix = (stripped_part + " " + candidate).strip()
        else:
            suffix = candidate

    # Build Markdown table
    md_lines = []
    if preamble:
        md_lines.append(preamble)
        md_lines.append("")

    md_lines.append(f"| {col1_label} | {col2_label} |")
    md_lines.append("|---|---|")

    n = min(len(left_items), len(right_items))
    for i in range(n):
        l_lbl, l_val = left_items[i]
        r_lbl, r_val = right_items[i]
        md_lines.append(f"| ({l_lbl}) {l_val} | ({r_lbl}) {r_val} |")

    if suffix:
        md_lines.append("")
        md_lines.append(suffix)

    return "\n".join(md_lines)


# ─── Assertion / Reason ──────────────────────────────────────────────────────

# The tricky part: some questions say "labelled Assertion (A) and Reason (R)" in the preamble,
# followed by the actual "Assertion (A): ..." statement.
# We anchor the match to "Assertion (A):" (with a colon or dash), not just "Assertion (A)".
_ASSERT_REASON_RE = re.compile(
    r"Assertion\s*\(A\)\s*[:–\-]\s*(.+?)\s+Reason\s*\(R\)\s*[:–\-]\s*(.+?)$",
    re.IGNORECASE | re.DOTALL
)

def _try_parse_assertion_reason(text: str) -> Optional[str]:
    m = _ASSERT_REASON_RE.search(text)
    if not m:
        return None

    preamble = text[:m.start()].strip()
    assertion = m.group(1).strip()
    reason    = m.group(2).strip()

    # Sanity check: assertion and reason should have some meaningful content
    if len(assertion) < 5 or len(reason) < 5:
        return None

    parts = []
    if preamble:
        parts.append(preamble)
        parts.append("")
    parts.append(f"**Assertion (A):** {assertion}")
    parts.append("")
    parts.append(f"**Reason (R):** {reason}")

    return "\n".join(parts)


# ─── Inline Numbered Statements ──────────────────────────────────────────────

# Splits on " N. " where N is a digit NOT preceded by another digit.
# The lookbehind prevents matching things like "@ 2047. 4." where "2047" ends with a digit.
_STMT_SPLIT_RE = re.compile(r"(?<![0-9@])\s+(\d+)\.\s+")

def _try_parse_numbered_statements(text: str) -> Optional[str]:
    """
    If the question contains inline numbered statements (2+ items starting with 1.),
    split them onto separate lines.
    """
    # Must have at least " 1. " and " 2. " (not preceded by digits/@ to avoid years)
    if not re.search(r"(?<![0-9@])\s1\.\s.+(?<![0-9@])\s2\.\s", text, re.DOTALL):
        return None

    first_m = re.search(r"(?<![0-9@])\s(1)\.\s", text)
    if not first_m:
        return None

    preamble = text[:first_m.start()].strip()
    stmts_raw = text[first_m.start():]

    parts = _STMT_SPLIT_RE.split(stmts_raw)
    # parts layout: ['', '1', 'stmt1', '2', 'stmt2', ...]
    if parts and not parts[0].strip():
        parts = parts[1:]

    statements = []
    i = 0
    while i < len(parts) - 1:
        num = parts[i].strip()
        content = parts[i + 1].strip() if (i + 1) < len(parts) else ""
        if num.isdigit() and content:
            statements.append((num, content))
            i += 2
        else:
            i += 1

    if len(statements) < 2:
        return None

    result_parts = []
    if preamble:
        result_parts.append(preamble)
        result_parts.append("")
    for num, stmt in statements:
        result_parts.append(f"{num}. {stmt}")

    return "\n".join(result_parts)


# ─── Public entry point ───────────────────────────────────────────────────────

def format_question_text(text: str) -> str:
    """
    Apply smart formatting to question text for Markdown output.
    Tries patterns in priority order:
      1. Column I / Column II table
      2. Assertion / Reason
      3. Inline numbered statements
    Falls back to original text if no pattern matches.
    """
    if not text:
        return text

    result = _try_parse_column_table(text)
    if result is not None:
        return result

    result = _try_parse_assertion_reason(text)
    if result is not None:
        return result

    result = _try_parse_numbered_statements(text)
    if result is not None:
        return result

    return text
