import re
from typing import List, Tuple, Dict
from collections import OrderedDict
from src.models import RawQuestionBlock

TELUGU_PATTERN = re.compile(r"[\u0c00-\u0c7f]")

def contains_telugu(text: str) -> bool:
    return bool(TELUGU_PATTERN.search(text))

def line_is_mostly_telugu(text: str) -> bool:
    """Returns True if the line is predominantly Telugu or garbled non-Latin text.

    Handles two cases:
    1. Properly encoded Telugu Unicode (U+0C00..U+0C7F)
    2. Garbled PDF font extractions that appear as scattered non-ASCII codepoints
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False

    # Case 1: proper Telugu Unicode
    tel_count = sum(1 for c in chars if TELUGU_PATTERN.match(c))
    if tel_count / len(chars) > 0.4:
        return True

    # Case 2: high ratio of non-ASCII non-Latin characters (garbled PDF text)
    # "Normal" English chars: ASCII printable + common punctuation
    ascii_printable = sum(1 for c in chars if ord(c) < 128)
    non_latin_non_ascii = len(chars) - ascii_printable
    if len(chars) >= 6 and non_latin_non_ascii / len(chars) > 0.4:
        return True

    return False

def block_has_telugu(block: RawQuestionBlock) -> bool:
    """Returns True if the block's content lines are predominantly Telugu."""
    # Skip metadata/header lines (first ~3 lines)
    content_lines = block.lines[3:] if len(block.lines) > 3 else block.lines
    if not content_lines:
        return False
    tel_lines = sum(1 for l in content_lines if line_is_mostly_telugu(l.text))
    return tel_lines / len(content_lines) > 0.5

def block_content_has_telugu(block: RawQuestionBlock) -> bool:
    """Returns True if the block contains any Telugu characters in its content lines."""
    content_lines = block.lines[3:] if len(block.lines) > 3 else block.lines
    return any(contains_telugu(l.text) for l in content_lines)

class LanguageDetector:
    def filter_language(self, raw_blocks: List[RawQuestionBlock]) -> Tuple[List[RawQuestionBlock], int, List[str]]:
        """
        Groups raw question blocks by question number, retaining the English version
        and discarding the Telugu counterpart.
        Preserves original question order.
        """
        grouped: Dict[int, List[RawQuestionBlock]] = OrderedDict()
        for b in raw_blocks:
            grouped.setdefault(b.qnum, []).append(b)

        english_blocks: List[RawQuestionBlock] = []
        telugu_discarded_count = 0
        anomalies: List[str] = []

        for qnum, blocks in grouped.items():
            if len(blocks) == 1:
                block = blocks[0]
                # Single-block: could be bilingual (EN+TEL interleaved) or English-only.
                # Always keep it — QuestionParser will skip Telugu lines.
                if block_has_telugu(block):
                    # Majority Telugu with no English content — pure Telugu block
                    telugu_discarded_count += 1
                    anomalies.append(f"Question {qnum}: Only Telugu version found; no English version available.")
                else:
                    english_blocks.append(block)

            elif len(blocks) == 2:
                b1, b2 = blocks[0], blocks[1]
                b1_tel = block_content_has_telugu(b1)
                b2_tel = block_content_has_telugu(b2)

                if not b1_tel and b2_tel:
                    english_blocks.append(b1)
                    telugu_discarded_count += 1
                elif b1_tel and not b2_tel:
                    english_blocks.append(b2)
                    telugu_discarded_count += 1
                elif not b1_tel and not b2_tel:
                    # Pure numerical/diagram questions in bilingual exams: occurrence 1 is English, occurrence 2 is Telugu
                    english_blocks.append(b1)
                    telugu_discarded_count += 1
                else:
                    # Both contain Telugu (anomaly)
                    english_blocks.append(b1)
                    telugu_discarded_count += 1
                    anomalies.append(f"Question {qnum}: Both question occurrences contained Telugu characters.")

            else:
                # More than 2 occurrences (anomaly)
                # Find the first one without Telugu
                chosen = None
                for b in blocks:
                    if not block_content_has_telugu(b):
                        chosen = b
                        break
                if chosen is None:
                    chosen = blocks[0]
                english_blocks.append(chosen)
                telugu_discarded_count += (len(blocks) - 1)
                anomalies.append(f"Question {qnum}: Found {len(blocks)} duplicate blocks in PDF.")

        # Sort by question number to ensure sequential order matches source
        english_blocks.sort(key=lambda b: b.qnum)
        return english_blocks, telugu_discarded_count, anomalies
