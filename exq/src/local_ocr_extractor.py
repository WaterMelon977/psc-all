import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import fitz
import numpy as np
from PIL import Image

from src.models import RawQuestionBlock

# Patterns to strip metadata lines from question prompt
METADATA_CLEANUP_PATTERNS = [
    re.compile(r"^Question\s+Number\s*:\s*\d+.*$", re.IGNORECASE),
    re.compile(r"^Question\s+(?:Id|Type|Mandatory)\s*:\s*.*$", re.IGNORECASE),
    re.compile(r"^(?:None\s+)?(?:Response|Think|Minimum|Instruction|Correct|Wrong|Calculator|Option|Display|Single|Negative).*$", re.IGNORECASE),
    re.compile(r"^Correct\s*Marks\s*:\s*\d+.*$", re.IGNORECASE),
]

def is_meta_line(text: str) -> bool:
    clean = text.strip()
    return any(p.match(clean) for p in METADATA_CLEANUP_PATTERNS)

class LocalOcrExtractor:
    """
    100% local, offline OCR extractor using RapidOCR (ONNX runtime) + PyMuPDF.
    Zero external API calls, zero token consumption.
    """
    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    def crop_block_pixmap(self, block: RawQuestionBlock) -> fitz.Pixmap:
        """
        Crops the question bounding box from the PDF page(s) at 150 DPI and returns a fitz.Pixmap.
        Stitches slices if the question spans across two pages.
        """
        if not block.pdf_path or not Path(block.pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {block.pdf_path}")

        doc = fitz.open(block.pdf_path)
        try:
            start_pno = block.page_number - 1
            end_pno = (block.end_page_number - 1) if (block.end_page_number and block.end_page_number >= block.page_number) else start_pno

            # Determine starting page and y (right below "Correct Marks : 1 Wrong Marks : 0.33")
            content_pno = (block.content_page_number - 1) if block.content_page_number > 0 else start_pno
            start_y = block.content_start_y if block.content_start_y > 0 else block.bbox[1]

            # Single page case
            if content_pno == end_pno:
                page = doc[content_pno]
                rect = fitz.Rect(
                    0,
                    start_y + 1, # Start right below Correct Marks line
                    page.rect.width,
                    min(page.rect.height, block.end_y - 2) # End right before next question header
                )
                return page.get_pixmap(clip=rect, dpi=200)

            # Multi-page case:
            # Slices from content_pno down to bottom of page, then from top of end_pno down to end_y (next question header)
            page1 = doc[content_pno]
            rect1 = fitz.Rect(
                0,
                start_y + 1,
                page1.rect.width,
                page1.rect.height - 15
            )
            pix1 = page1.get_pixmap(clip=rect1, dpi=200)

            page2 = doc[end_pno]
            end_y = block.end_y if block.end_y > 30 else page2.rect.height - 15.0
            rect2 = fitz.Rect(
                0,
                20,
                page2.rect.width,
                end_y - 2 # End right before next question header
            )
            pix2 = page2.get_pixmap(clip=rect2, dpi=200)

            total_w = max(pix1.width, pix2.width)
            total_h = pix1.height + pix2.height
            stitched = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, total_w, total_h), 0)
            stitched.set_rect(stitched.irect, (255, 255, 255))
            stitched.copy(pix1, fitz.IRect(0, 0, pix1.width, pix1.height))
            stitched.copy(pix2, fitz.IRect(0, pix1.height, pix2.width, total_h))
            return stitched
        finally:
            doc.close()

    def detect_answers_from_image(self, arr: np.ndarray, option_y_ranges: List[Tuple[int, float, float]]) -> List[int]:
        """
        Detects green checkmarks near each option number by sampling pixel colors in the left margin.
        """
        detected = []
        for opt_num, y_top, y_bottom in option_y_ranges:
            y0 = max(0, int(y_top - 15))
            y1 = min(arr.shape[0], int(y_bottom + 15))
            # Left margin search area where the check/cross icon is placed
            sub = arr[y0:y1, 0:min(arr.shape[1], 100)]
            if sub.size == 0:
                continue

            # Check for green pixels: G > 90 and G significantly larger than R and B
            g_mask = (sub[:, :, 1].astype(int) - np.maximum(sub[:, :, 0], sub[:, :, 2]) > 25) & (sub[:, :, 1] > 90)
            green_count = np.sum(g_mask)
            if green_count >= 15:
                detected.append(opt_num)

        return detected

    def extract(self, block: RawQuestionBlock) -> Tuple[str, Dict[str, str], List[int]]:
        """
        Runs RapidOCR on the cropped block, separates question stem and options,
        formats side-by-side columns into clean text, and detects answer keys locally.
        """
        try:
            pix = self.crop_block_pixmap(block)
            img_bytes = pix.tobytes("png")
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            arr = np.array(img)
        except Exception as e:
            print(f"  [LocalOcr Error] Failed to crop Question {block.qnum}: {e}")
            return "", {}, []

        try:
            ocr_result, _ = self.engine(img_bytes)
        except Exception as e:
            print(f"  [LocalOcr Error] RapidOCR failed for Question {block.qnum}: {e}")
            return "", {}, []

        if not ocr_result:
            return "", {}, []

        items = []
        for bbox, text, score in ocr_result:
            t = text.strip()
            if not t:
                continue
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            items.append({
                "text": t,
                "x0": min_x,
                "x1": max_x,
                "y0": min_y,
                "y1": max_y,
                "score": score
            })

        items.sort(key=lambda it: it["y0"])

        # 1. Locate the 'Options :' boundary
        options_idx = None
        for i, it in enumerate(items):
            if re.match(r"^Options\s*:", it["text"], re.IGNORECASE):
                options_idx = i
                break

        if options_idx is None:
            for i, it in enumerate(items):
                if re.match(r"^1[\.\)]\s*", it["text"]):
                    options_idx = i
                    break

        if options_idx is not None:
            prompt_items = items[:options_idx]
            option_items = items[options_idx:]
        else:
            prompt_items = items
            option_items = []

        # 2. Extract and format question prompt (handling 2-column tables)
        clean_prompt_items = []
        for it in prompt_items:
            t = it["text"]
            if is_meta_line(t):
                continue
            clean_prompt_items.append(it)

        prompt_lines = []
        if clean_prompt_items:
            row_buckets: List[List[Dict]] = []
            for it in clean_prompt_items:
                placed = False
                for row in row_buckets:
                    avg_y = sum(r["y0"] for r in row) / len(row)
                    if abs(it["y0"] - avg_y) < 16:
                        row.append(it)
                        placed = True
                        break
                if not placed:
                    row_buckets.append([it])

            for row in row_buckets:
                row.sort(key=lambda r: r["x0"])
                line_text = "\t\t".join(r["text"] for r in row)
                prompt_lines.append(line_text)

        question_text = "\n".join(prompt_lines).strip()

        # 3. Parse options (handling cases where option numbers/icons are detected separately)
        options: Dict[str, str] = {}
        option_y_ranges: List[Tuple[int, float, float]] = []

        opt_lead_re = re.compile(r"^([1-4])[\.\)]\s*(?:[~*xX\u2713\u2714\u2715\u2716\ufffd\s]*)(.*)$")

        clean_opt_items = []
        for it in option_items:
            t = it["text"].strip()
            if re.match(r"^Options\s*:", t, re.IGNORECASE) or is_meta_line(t):
                continue
            clean_opt_items.append(it)

        # Cluster option items into horizontal rows so '3.' and '1-c, 2-d...' merge properly
        opt_rows: List[List[Dict]] = []
        for it in clean_opt_items:
            placed = False
            for row in opt_rows:
                avg_y = sum(r["y0"] for r in row) / len(row)
                if abs(it["y0"] - avg_y) < 22:
                    row.append(it)
                    placed = True
                    break
            if not placed:
                opt_rows.append([it])

        # Sort rows vertically
        opt_rows.sort(key=lambda r: sum(item["y0"] for item in r) / len(r))

        cur_num = None
        cur_text_parts = []
        cur_y_top = 0.0
        cur_y_bottom = 0.0

        for row in opt_rows:
            # Sort items in row left-to-right
            row.sort(key=lambda it: it["x0"])
            row_text = " ".join(it["text"] for it in row).strip()
            row_y0 = min(it["y0"] for it in row)
            row_y1 = max(it["y1"] for it in row)

            m = opt_lead_re.match(row_text)
            is_new = False

            if m:
                is_new = True
                new_num = int(m.group(1))
                new_rest = m.group(2).strip()
            elif cur_num is not None and cur_num < 4:
                is_new = True
                new_num = cur_num + 1
                new_rest = row_text
            elif cur_num is None:
                is_new = True
                new_num = 1
                new_rest = row_text

            if is_new:
                if cur_num is not None:
                    options[str(cur_num)] = " ".join(cur_text_parts).strip()
                    option_y_ranges.append((cur_num, cur_y_top, cur_y_bottom))

                cur_num = new_num
                cur_text_parts = [new_rest] if new_rest else []
                cur_y_top = row_y0
                cur_y_bottom = row_y1
            else:
                if cur_num is not None:
                    if row_text:
                        cur_text_parts.append(row_text)
                    cur_y_bottom = max(cur_y_bottom, row_y1)

        if cur_num is not None:
            options[str(cur_num)] = " ".join(cur_text_parts).strip()
            option_y_ranges.append((cur_num, cur_y_top, cur_y_bottom))

        # Clean noise/artifacts from option text
        cleaned_options = {}
        for k, v in options.items():
            clean_v = re.sub(r"^[~*xX\u2713\u2714\u2715\u2716\ufffd\s\.,%]+", "", v).strip()
            cleaned_options[k] = clean_v

        # 4. Detect answer from green pixel markers
        detected_answers = self.detect_answers_from_image(arr, option_y_ranges)

        return question_text, cleaned_options, detected_answers
