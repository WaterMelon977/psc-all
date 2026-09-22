import fitz
import cv2
import numpy as np
import re
from typing import List, Dict, Tuple, Optional

from src.models import Question

class BookletExtractor:
    """
    Extractor for offline printed/scanned APPSC Question Booklets.
    - Handles numbered questions (1. to 150.)
    - Extracts English questions & options, filtering Telugu translations
    - Detects official answer key marked by rounded-rectangle border boxes
    """
    def __init__(self, pdf_path: str, exam_name: str = ""):
        self.pdf_path = pdf_path
        self.exam_name = exam_name
        self._ocr = None

    @property
    def ocr(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
        return self._ocr

    @staticmethod
    def is_booklet_format(doc: fitz.Document) -> bool:
        """
        Determines whether the document follows the offline booklet format:
        Does NOT contain 'Question Number :' and contains numbered questions or booklet markers.
        """
        cbt_regex = re.compile(r"Question Number\s*:\s*\d+", re.IGNORECASE)
        # Matches '1. ', '1) ', 'I. ', 'l. ' at start of lines or booklet keywords
        booklet_q_regex = re.compile(r"^\s*[1Il|]\s*[\.\)]\s+", re.MULTILINE)
        booklet_kw_regex = re.compile(r"Question Booklet|Paper\s*-\s*I|OMR|Series\s*:", re.IGNORECASE)
        
        sample_pages = min(8, len(doc))
        has_cbt = False
        has_booklet = False
        for pno in range(sample_pages):
            txt = doc[pno].get_text()
            if cbt_regex.search(txt):
                has_cbt = True
                break
            if booklet_q_regex.search(txt) or booklet_kw_regex.search(txt):
                has_booklet = True

        return (not has_cbt) and has_booklet

    def detect_answer_boxes(self, img_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects rounded rectangle outline boxes drawn around correct options.
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
        cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            # In 150 dpi: w is typically 80 to 650, h is 22 to 55, aspect ratio > 2.0
            if 80 < w < 650 and 22 < h < 55 and (w / h) > 2.0:
                boxes.append((x, y, w, h))
                
        # Merge overlapping / double borders
        merged = []
        for b in sorted(boxes, key=lambda item: (item[1], item[0])):
            x, y, w, h = b
            if not any(abs(x - mx) < 20 and abs(y - my) < 15 for mx, my, mw, mh in merged):
                merged.append(b)
        return merged

    def is_point_in_box(self, px: float, py: float, box: Tuple[int, int, int, int]) -> bool:
        bx, by, bw, bh = box
        return (bx - 12 <= px <= bx + bw + 12) and (by - 10 <= py <= by + bh + 10)

    def extract_questions(self) -> Tuple[List[Question], int]:
        doc = fitz.open(self.pdf_path)
        total_pages = len(doc)
        all_questions: List[Question] = []
        
        # Identify question pages (skip instruction front matter and end rough work pages)
        question_pages = []
        for pno in range(total_pages):
            txt = doc[pno].get_text()
            if re.search(r"SPACE FOR ROUGH", txt, re.IGNORECASE):
                continue
            if "Question Booklet Sl. No." in txt or "Enter the Registered Number" in txt or "Enter &o Registered" in txt:
                continue
            if pno < 3 and ("Invigilator" in txt or "OMR" in txt):
                continue
            question_pages.append(pno)

        current_q: Optional[Dict] = None

        for pno in question_pages:
            page = doc[pno]
            pix = page.get_pixmap(dpi=150)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            boxes = self.detect_answer_boxes(img)
            res, _ = self.ocr(img)
            if not res:
                continue

            # Sort items top-to-bottom
            items = sorted(res, key=lambda x: min(p[1] for p in x[0]))

            for it in items:
                pts = it[0]
                txt = it[1].strip()
                ymin = min(p[1] for p in pts)
                xmin = min(p[0] for p in pts)
                xmax = max(p[0] for p in pts)

                # Normalize OCR characters at start of line
                norm_txt = txt
                norm_txt = re.sub(r"^([0-9]{1,2})[Ll]\b", r"\g<1>1", norm_txt)
                norm_txt = re.sub(r"^[Il|!]{2}\b", "11", norm_txt)
                norm_txt = re.sub(r"^[Il|!]{1}(\d{1,2})\b", r"1\1", norm_txt)

                # Strict question header match:
                # 1. Must be near left margin (xmin < 220) to prevent matching sub-list items in match tables
                # 2. Must start with digits followed by dot, closing parenthesis, quote or space
                m_q = re.match(r"^(\d{1,3})\s*[\.\'\"\)]\s*(.*)", norm_txt)
                if m_q and xmin < 220 and int(m_q.group(1)) <= 150:
                    qnum = int(m_q.group(1))
                    
                    # Finalize previous question
                    if current_q is not None:
                        all_questions.append(self._build_question(current_q, boxes))

                    current_q = {
                        "qnum": qnum,
                        "page": pno + 1,
                        "text": m_q.group(2).strip(),
                        "options": {},
                        "opt_coords": {},
                        "boxes": boxes,
                    }
                    continue

                if current_q is not None:
                    # Match options in line: e.g. "(1) Vitamin A", "(2) Vitamin B12"
                    opt_matches = list(re.finditer(r"\(([1-4])\)\s*([^(\n]+)?", txt))
                    if opt_matches:
                        for om in opt_matches:
                            opt_num = int(om.group(1))
                            opt_txt = (om.group(2) or "").strip()
                            
                            char_offset = om.start()
                            line_len = max(len(txt), 1)
                            approx_opt_x = xmin + (xmax - xmin) * (char_offset / line_len)

                            if str(opt_num) not in current_q["options"]:
                                if not re.search(r"[\u0c00-\u0c7f]", opt_txt):
                                    current_q["options"][str(opt_num)] = opt_txt
                                    current_q["opt_coords"][opt_num] = (approx_opt_x, ymin)
                    else:
                        # Append continuation lines to question text if options not yet started
                        if not current_q["options"] and not re.search(r"[\u0c00-\u0c7f]", txt):
                            if "GS/M" not in txt and "(A)" not in txt and "SPACE FOR" not in txt:
                                current_q["text"] += " " + txt

            if current_q is not None:
                current_q["boxes"] = boxes

        # Finalize last question
        if current_q is not None:
            all_questions.append(self._build_question(current_q, current_q.get("boxes", [])))

        doc.close()

        # Deduplicate if any question number repeated (keep the one with more options or detected answer)
        final_questions_map: Dict[int, Question] = {}
        for q in all_questions:
            qn = q.question_number
            if qn not in final_questions_map:
                final_questions_map[qn] = q
            else:
                existing = final_questions_map[qn]
                if (q.answer and not existing.answer) or len(q.options) > len(existing.options):
                    final_questions_map[qn] = q

        deduped = sorted(final_questions_map.values(), key=lambda q: q.question_number)
        return deduped, total_pages

    def _build_question(self, q_data: Dict, boxes: List[Tuple[int, int, int, int]]) -> Question:
        detected_answer = []
        page_boxes = q_data.get("boxes", boxes)
        for opt_num, (ox, oy) in q_data["opt_coords"].items():
            if any(self.is_point_in_box(ox, oy, b) for b in page_boxes):
                detected_answer = [opt_num]
                break

        issues = []
        if not detected_answer:
            issues.append(f"Question {q_data['qnum']}: No boxed answer detected.")
        if len(q_data["options"]) < 4:
            issues.append(f"Question {q_data['qnum']}: Only {len(q_data['options'])} options detected.")

        return Question(
            question_number=q_data["qnum"],
            page_number=q_data["page"],
            question_text=q_data["text"],
            options=q_data["options"],
            answer=detected_answer,
            topic="",
            review_issues=issues,
            topic_scores={},
            exam=self.exam_name,
        )
