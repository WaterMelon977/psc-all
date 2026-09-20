import re
from typing import List, Tuple, Dict
from collections import OrderedDict
from src.models import RawQuestionBlock

TELUGU_PATTERN = re.compile(r"[\u0c00-\u0c7f]")

def contains_telugu(text: str) -> bool:
    return bool(TELUGU_PATTERN.search(text))

def block_has_telugu(block: RawQuestionBlock) -> bool:
    full_text = " ".join(line.text for line in block.lines)
    return contains_telugu(full_text)

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
                if block_has_telugu(block):
                    # Only a Telugu block found for this question
                    telugu_discarded_count += 1
                    anomalies.append(f"Question {qnum}: Only Telugu version found; no English version available.")
                else:
                    english_blocks.append(block)

            elif len(blocks) == 2:
                b1, b2 = blocks[0], blocks[1]
                b1_tel = block_has_telugu(b1)
                b2_tel = block_has_telugu(b2)

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
                    if not block_has_telugu(b):
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
