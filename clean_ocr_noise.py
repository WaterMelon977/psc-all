#!/usr/bin/env python3
"""
Clean non-English OCR noise characters from endowments/endow-all.md (and optionally other files).

Preserves:
- All ASCII characters (32-126, newlines, tabs)
- Smart/curly quotes (‘, ’, “, ”)
- En/em dashes (–, —)
- Ellipsis (…)
- Rupee symbol (₹)
- Standard transliteration diacritics (e.g. Ā, ā, ō, ḥ, Ṛ, ṣ, ̥)
- Vulgar fraction (¼)

Removes:
- Unwanted non-English script noise (Arabic, Syriac, Thaana, NKo, Samaritan, Mandaic, Devanagari, Telugu junk characters)
- Extraneous symbols like ¥
- Cleans trailing punctuation artifacts left after noise removal (e.g. trailing colon after removal)
- Strips any accidental OCR text spillover (e.g. " 3. Surplus Funds 4. Employees Welfare Fund" appended to an option)
"""

import sys
import re
import shutil
from pathlib import Path

# Characters to remove: Arabic, Syriac, Thaana, NKo, Samaritan, Mandaic, Devanagari, Telugu, Yen symbol
OCR_JUNK_REGEX = re.compile(r'[\u0600-\u08FF\u0900-\u0D7F\u00A5]+')

def clean_content(text: str) -> str:
    lines = text.splitlines(keepends=True)
    cleaned_lines = []

    for line in lines:
        cleaned = line
        
        # Specific fix for known OCR spillover in Q27
        if "Souptika Parva 3. Surplus Funds 4. Employees Welfare Fund" in cleaned:
            cleaned = cleaned.replace("Souptika Parva 3. Surplus Funds 4. Employees Welfare Fund", "Souptika Parva")

        # Specific fix for question 4009 trailing colon after OCR artifact
        if "called: అంܼࡏ:" in cleaned:
            cleaned = cleaned.replace("called: అంܼࡏ:", "called:")

        # Specific fix for ¥ sign before Nambudri Law
        cleaned = cleaned.replace("¥ ", "").replace("¥", "")

        # If line contains OCR junk, strip it
        if OCR_JUNK_REGEX.search(cleaned):
            # For option lines or standard text lines, strip the junk
            cleaned = OCR_JUNK_REGEX.sub('', cleaned)

            # Clean any trailing whitespace before the line ending
            newline_match = re.search(r'[\r\n]+$', cleaned)
            newline = newline_match.group(0) if newline_match else ''
            core = cleaned[:len(cleaned) - len(newline)].rstrip()

            # Clean trailing orphaned colons or artifacts if left dangling
            if core.endswith(" :"):
                core = core[:-2] + ":"

            cleaned = core + newline

        cleaned_lines.append(cleaned)

    return "".join(cleaned_lines)

def clean_file(file_path: Path, create_backup: bool = True) -> int:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    original = file_path.read_text(encoding='utf-8')
    cleaned = clean_content(original)

    if cleaned == original:
        print(f"No non-English OCR noise found in: {file_path}")
        return 0

    if create_backup:
        bak_file = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, bak_file)
        print(f"Backup created: {bak_file}")

    file_path.write_text(cleaned, encoding='utf-8')
    print(f"Successfully cleaned: {file_path}")
    return 1

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "endowments" / "endow-all.md"
    clean_file(target)
