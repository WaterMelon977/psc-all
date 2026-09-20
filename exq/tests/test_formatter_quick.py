"""Quick sanity tests for question_formatter.py"""
import sys
import os

# Add exq to path
exq_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "appsc-loaded", "exq")
if not os.path.exists(exq_path):
    exq_path = r"d:\appsc-loaded\exq"
sys.path.insert(0, exq_path)

from src.question_formatter import format_question_text

# ── Test 1: Column/matching table ─────────────────────────────────────────────
col_q = (
    "B, D, E, F, P, Q and R are sitting around a circular table, facing the centre of the table. "
    "Only one person sits between P and D when counted from the left of D. "
    "R sits third to the right of F. B sits third to the left of E. "
    "R sits to the immediate right of B. Q is not an immediate neighbour of B. "
    "Column I (Person) Column II (Neighbour to the immediate left) "
    "(i)Q (W)B (ii)P (X)E (iii)D (Y)R (iv)R (Z)F "
    "Which is the correct match of Column I with Column II?"
)
result1 = format_question_text(col_q)
print("=== Test 1: Column Table ===")
print(result1)
print()
assert "|" in result1, f"FAIL: No table found\n{result1}"
print("PASS")

# ── Test 2: Assertion/Reason ──────────────────────────────────────────────────
ar_q = (
    "Select the option that is true regarding the following two statements labelled Assertion (A) and Reason (R). "
    "Assertion (A): Weighted arithmetic mean is preferred over simple arithmetic mean when dealing with datasets, "
    "where different data points carry varying degrees of importance. "
    "Reason (R): Weighted arithmetic mean takes into account the significance of each data point by assigning "
    "appropriate weights, resulting in a more accurate representation of the average."
)
result2 = format_question_text(ar_q)
print("=== Test 2: Assertion/Reason ===")
print(result2)
print()
assert "**Assertion (A):**" in result2, f"FAIL: Assertion not found\n{result2}"
assert "**Reason (R):**" in result2, f"FAIL: Reason not found\n{result2}"
print("PASS")

# ── Test 3: Numbered inline statements ────────────────────────────────────────
stmt_q = (
    "Which of the following statements regarding Andhra Pradesh's inclusion in the SDG India Index 2023-24 "
    "methodology are correct? "
    "1. Andhra Pradesh's SDG score has improved compared to the 2020-21 edition. "
    "2. The normalisation of raw data plays a crucial role. "
    "3. Andhra Pradesh's performance in SDGs directly contributes to Viksit Bharat @ 2047. "
    "4. The composite SDG Index score is derived by averaging its individual Goal scores."
)
result3 = format_question_text(stmt_q)
print("=== Test 3: Numbered Statements ===")
print(result3)
print()
lines3 = result3.split("\n")
assert any(l.startswith("1. ") for l in lines3), f"FAIL: Statement 1 not on own line\n{result3}"
assert any(l.startswith("2. ") for l in lines3), f"FAIL: Statement 2 not on own line\n{result3}"
assert any(l.startswith("3. ") for l in lines3), f"FAIL: Statement 3 not on own line\n{result3}"
assert any(l.startswith("4. ") for l in lines3), f"FAIL: Statement 4 not on own line\n{result3}"
print("PASS")

# ── Test 4: Plain question — no change ────────────────────────────────────────
plain_q = "What is the capital of Andhra Pradesh?"
result4 = format_question_text(plain_q)
print("=== Test 4: Plain question (no change) ===")
assert result4 == plain_q, f"FAIL: Plain question changed\n{result4}"
print("PASS")

print("\nAll tests passed!")
