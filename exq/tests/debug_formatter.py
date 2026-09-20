"""Debug actual text from the PDF"""
import sys
sys.path.insert(0, r"d:\appsc-loaded\exq")

import re
from src.question_formatter import _COL_HEADER_RE, _try_parse_column_table

col_q = (
    "B, D, E, F, P, Q and R are sitting around a circular table. "
    "Column I (Person) Column II (Neighbour to the immediate left) "
    "(i)Q (W)B (ii)P (X)E (iii)D (Y)R (iv)R (Z)F "
    "Which is the correct match?"
)

m = _COL_HEADER_RE.search(col_q)
print("Header match:", m.group(0) if m else None)

after_start = m.end()
label_after = re.match(r"\s*\([^)]+\)", col_q[after_start:])
if label_after:
    after_start += label_after.end()
    print("Skipped label:", label_after.group(0))

entries_text = col_q[after_start:].strip()
print("entries_text:", repr(entries_text))

# New TOKEN_RE
TOKEN_RE = re.compile(r"\(([^)]+)\)\s*([^\(\)]+?)(?=\s*\(|$)")
print("\nAll tokens:")
for m2 in TOKEN_RE.finditer(entries_text):
    print(f"  label={m2.group(1)!r}, value={m2.group(2).strip()!r}")
