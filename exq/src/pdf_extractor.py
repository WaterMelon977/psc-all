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

    @staticmethod
    def is_booklet_format(pdf_path: str) -> bool:
        from src.booklet_extractor import BookletExtractor
        doc = fitz.open(pdf_path)
        is_booklet = BookletExtractor.is_booklet_format(doc)
        doc.close()
        return is_booklet

    def extract(self) -> Tuple[List[RawQuestionBlock], int]:
        doc = fitz.open(self.pdf_path)
        total_pages = doc.page_count
        raw_blocks: List[RawQuestionBlock] = []
        current_block: RawQuestionBlock = None

        qnum_regex = re.compile(r"Question Number\s*:\s*(\d+)", re.IGNORECASE)
        page_images_by_pno = {}

        # Track block positions and images per page
        for pno in range(total_pages):
            page = doc[pno]
            text_dict = page.get_text("dict")
            page_rect = page.rect

            # Collect image blocks on this page (ignore tiny icons like 16x16)
            page_images = []
            for b in text_dict.get("blocks", []):
                if b.get("type") == 1:
                    w = b.get("width", 0)
                    h = b.get("height", 0)
                    # Question content image is usually > 24px (excluding 16x16 checkmark/cross icons)
                    if w > 24 or h > 24:
                        page_images.append(b.get("bbox", (0, 0, 0, 0)))

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
                        line_bbox = line.get("bbox", (0.0, 0.0, 0.0, 0.0))
                        
                        if current_block is not None:
                            current_block.end_page_number = pno + 1
                            current_block.end_y = line_bbox[1]
                            # Finalize previous block's bbox bottom
                            if current_block.page_number == pno + 1:
                                current_block.bbox = (
                                    0.0,
                                    current_block.bbox[1],
                                    page_rect.width,
                                    line_bbox[1]
                                )
                            else:
                                current_block.bbox = (
                                    0.0,
                                    current_block.bbox[1],
                                    page_rect.width,
                                    page_rect.height - 15.0
                                )
                            raw_blocks.append(current_block)

                        current_block = RawQuestionBlock(
                            qnum=qnum,
                            page_number=pno + 1,
                            header_text=line_text,
                            lines=[raw_line],
                            pdf_path=self.pdf_path,
                            bbox=(0.0, line_bbox[1], page_rect.width, page_rect.height - 15.0),
                            end_page_number=pno + 1,
                            end_y=page_rect.height - 15.0,
                            content_page_number=pno + 1,
                            content_start_y=line_bbox[3]
                        )
                    else:
                        if current_block is not None:
                            current_block.lines.append(raw_line)
                            # Identify "Correct Marks : ... Wrong Marks :" boundary line
                            if re.search(r"Correct\s*Marks\s*:\s*\d+", line_text, re.IGNORECASE):
                                current_block.content_page_number = pno + 1
                                current_block.content_start_y = line.get("bbox", (0, 0, 0, 0))[3]

            # Check images for questions on this page
            # If current_block is active and on this page, or recently finalized
            # Store per-page image bboxes for quick lookup
            page_images_by_pno[pno + 1] = page_images

        if current_block is not None:
            current_block.end_page_number = total_pages
            current_block.end_y = page_rect.height - 35.0
            raw_blocks.append(current_block)

        # Fast image association using page_images_by_pno
        for b in raw_blocks:
            start_p = b.content_page_number if b.content_page_number > 0 else b.page_number
            end_p = b.end_page_number if (b.end_page_number and b.end_page_number >= start_p) else start_p
            has_img = False

            for pno in range(start_p, end_p + 1):
                imgs = page_images_by_pno.get(pno, [])
                top_limit = (b.content_start_y - 5.0) if pno == start_p else 0.0
                bottom_limit = (b.end_y + 5.0) if pno == end_p else 9999.0

                for img_bbox in imgs:
                    if img_bbox[3] >= top_limit and img_bbox[1] <= bottom_limit:
                        has_img = True
                        break
                if has_img:
                    break

            b.has_images = has_img

        doc.close()
        return raw_blocks, total_pages
