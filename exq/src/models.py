from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class RawSpan:
    text: str
    color: int
    bbox: Tuple[float, float, float, float]
    font: str = ""
    size: float = 0.0

@dataclass
class RawLine:
    text: str
    spans: List[RawSpan]
    page_number: int

@dataclass
class RawQuestionBlock:
    qnum: int
    page_number: int
    header_text: str
    lines: List[RawLine] = field(default_factory=list)
    pdf_path: str = ""
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    has_images: bool = False
    end_page_number: int = 0
    end_y: float = 0.0
    content_page_number: int = 0
    content_start_y: float = 0.0

@dataclass
class ParsedOption:
    number: int
    text: str
    spans: List[RawSpan] = field(default_factory=list)
    is_green: bool = False
    is_red: bool = False

@dataclass
class Question:
    question_number: int
    page_number: int
    question_text: str
    options: Dict[str, str] = field(default_factory=dict)
    answer: List[int] = field(default_factory=list)
    topic: str = ""
    review_issues: List[str] = field(default_factory=list)
    topic_scores: Dict[str, float] = field(default_factory=dict)
    exam: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_number": self.question_number,
            "question": self.question_text,
            "options": self.options,
            "answer": self.answer,
            "topic": self.topic,
        }

@dataclass
class ConversionReport:
    paper_name: str
    input_file: str
    processing_timestamp: str
    total_pages: int
    total_question_blocks_detected: int
    english_questions_retained: int
    telugu_questions_discarded: int
    questions_with_detected_answers: int
    review_items_count: int
    topic_distribution: Dict[str, int]
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_filename": self.input_file,
            "processing_timestamp": self.processing_timestamp,
            "total_pages": self.total_pages,
            "total_question_blocks_detected": self.total_question_blocks_detected,
            "english_questions_retained": self.english_questions_retained,
            "telugu_questions_discarded": self.telugu_questions_discarded,
            "questions_with_detected_answers": self.questions_with_detected_answers,
            "review_items_count": self.review_items_count,
            "topic_distribution": self.topic_distribution,
            "warnings": self.warnings,
            "duration_seconds": round(self.duration_seconds, 3),
        }
