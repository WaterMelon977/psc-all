import fitz
import re
from typing import List, Tuple
from src.models import RawSpan, RawLine, RawQuestionBlock

# Patterns to filter out browser/printer header & footer artifacts
HEADER_PATTERNS = [
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*(?:AM|PM)$", re.IGNORECASE),
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^TCSiON\s+CAE$", re.IGNORECASE),
]

def is_header_or_footer(text: str) -> bool:
    clean = text.strip()
    return any(pattern.match(clean) for pattern in HEADER_PATTERNS)

class PDFExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract(self) -> Tuple[List[RawQuestionBlock], int]:
        doc = fitz.open(self.pdf_path)
        total_pages = doc.page_count
        raw_blocks: List[RawQuestionBlock] = []
        current_block: RawQuestionBlock = None

        qnum_regex = re.compile(r"Question Number\s*:\s*(\d+)", re.IGNORECASE)

        for pno in range(total_pages):
            page = doc[pno]
            text_dict = page.get_text("dict")
            for b in text_dict.get("blocks", []):
                # type == 0 is text block
                if b.get("type") != 0:
                    continue

                for line in b.get("lines", []):
                    spans_data = line.get("spans", [])
                    line_text = "".join(s.get("text", "") for s in spans_data).strip()
                    if not line_text:
                        continue

                    # Filter out browser print header/footer lines
                    if is_header_or_footer(line_text):
                        continue

                    # Build RawLine
                    raw_spans = [
                        RawSpan(
                            text=s.get("text", ""),
                            color=s.get("color", 0),
                            bbox=tuple(s.get("bbox", (0.0, 0.0, 0.0, 0.0))),
                            font=s.get("font", ""),
                            size=s.get("size", 0.0),
                        )
                        for s in spans_data
                    ]
                    raw_line = RawLine(text=line_text, spans=raw_spans, page_number=pno + 1)

                    # Check for new Question Number
                    m = qnum_regex.search(line_text)
                    if m:
                        qnum = int(m.group(1))
                        if current_block is not None:
                            raw_blocks.append(current_block)
                        current_block = RawQuestionBlock(
                            qnum=qnum,
                            page_number=pno + 1,
                            header_text=line_text,
                            lines=[raw_line]
                        )
                    else:
                        if current_block is not None:
                            current_block.lines.append(raw_line)

        if current_block is not None:
            raw_blocks.append(current_block)

        doc.close()
        return raw_blocks, total_pages
