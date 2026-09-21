import sys
import os
import io
import time
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

from src.models import Question, ConversionReport
from src.pdf_extractor import PDFExtractor
from src.language_detector import LanguageDetector
from src.question_parser import QuestionParser
from src.answer_detector import AnswerDetector
from src.topic_classifier import TopicClassifier
from src.markdown_renderer import MarkdownRenderer
from src.json_renderer import JSONRenderer
from src.review_generator import ReviewGenerator
from src.report_generator import ReportGenerator

# Ensure utf-8 output on standard output across platforms
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def run_conversion(pdf_path: str, topics_path: str, output_dir: str = None, exam: str = None):
    start_time = time.time()
    pdf_file = Path(pdf_path).resolve()
    topics_file = Path(topics_path).resolve()

    if not pdf_file.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    if not topics_file.exists():
        print(f"Error: Topics YAML file not found: {topics_path}", file=sys.stderr)
        sys.exit(1)

    paper_name = pdf_file.stem
    cleaned_exam_name = exam if exam else paper_name.replace('_', ' ').replace('-', ' ').strip()
    if output_dir:
        out_dir = Path(output_dir).resolve()
    else:
        # Output folder in the same folder as the pdf, named the same as the pdf name
        out_dir = pdf_file.parent / paper_name

    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading PDF...")
    extractor = PDFExtractor(str(pdf_file))
    raw_blocks, total_pages = extractor.extract()

    print("Extracting questions...")
    total_blocks_count = len(raw_blocks)
    print(f"Detected {total_blocks_count} question blocks.")

    lang_detector = LanguageDetector()
    english_blocks, telugu_discarded, anomalies = lang_detector.filter_language(raw_blocks)

    print(f"Retaining {len(english_blocks)} English questions.")
    print(f"Discarded {telugu_discarded} Telugu duplicates.")

    print("Detecting answers...")
    print("Classifying topics...")
    topic_classifier = TopicClassifier(str(topics_file))
    question_parser = QuestionParser()
    answer_detector = AnswerDetector()

    structured_questions = []
    answers_detected_count = 0
    topic_distribution = {t: 0 for t in topic_classifier.topics_order}

    for block in english_blocks:
        q_text, parsed_opts, parse_issues = question_parser.parse_block(block)
        detected_answers, ans_issues = answer_detector.detect_answers(parsed_opts)

        if detected_answers:
            answers_detected_count += 1

        opts_dict = {str(opt.number): opt.text for opt in parsed_opts}
        topic, scores = topic_classifier.classify(q_text, opts_dict)
        topic_distribution[topic] = topic_distribution.get(topic, 0) + 1

        all_issues = parse_issues + ans_issues

        q = Question(
            question_number=block.qnum,
            page_number=block.page_number,
            question_text=q_text,
            options=opts_dict,
            answer=detected_answers,
            topic=topic,
            review_issues=all_issues,
            topic_scores=scores,
            exam=cleaned_exam_name,
        )
        structured_questions.append(q)

    # Markdown rendering
    print("Generating Markdown...")
    md_renderer = MarkdownRenderer(
        topics_order=topic_classifier.topics_order,
        paper_title=f"APPSC {paper_name.replace('_', ' ').replace('-', ' ')} Question Bank",
        default_exam=cleaned_exam_name,
    )
    md_content = md_renderer.render(structured_questions)
    md_path = out_dir / f"{paper_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # JSON rendering
    print("Generating JSON...")
    json_renderer = JSONRenderer()
    json_content = json_renderer.render(structured_questions)
    json_path = out_dir / f"{paper_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Review generation
    review_generator = ReviewGenerator()
    review_content = review_generator.generate(structured_questions, general_issues=anomalies)
    review_path = out_dir / f"{paper_name}_review.md"
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(review_content)

    # Report generation
    print("Generating report...")
    review_items_count = sum(1 for q in structured_questions if q.review_issues) + len(anomalies)
    duration = time.time() - start_time

    report = ConversionReport(
        paper_name=paper_name,
        input_file=str(pdf_file),
        processing_timestamp=datetime.now().isoformat(),
        total_pages=total_pages,
        total_question_blocks_detected=total_blocks_count,
        english_questions_retained=len(structured_questions),
        telugu_questions_discarded=telugu_discarded,
        questions_with_detected_answers=answers_detected_count,
        review_items_count=review_items_count,
        topic_distribution=topic_distribution,
        warnings=anomalies,
        duration_seconds=duration,
    )
    report_generator = ReportGenerator()
    report_content = report_generator.generate(report)
    report_path = out_dir / f"{paper_name}_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print()
    print("Completed.")
    print()
    print(f"Questions: {len(structured_questions)}")
    print(f"Answers detected: {answers_detected_count}")
    print(f"Review required: {review_items_count}")
    print()
    print("Output:")
    print(f"{md_path}")
    print(f"{json_path}")
    print(f"{review_path}")
    print(f"{report_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Convert APPSC Examination Question Paper PDF to structured Markdown and JSON."
    )
    parser.add_argument("pdf", help="Path to the APPSC question paper PDF.")
    parser.add_argument(
        "topics",
        nargs="?",
        default=None,
        help="Path to topics.yaml configuration file (e.g. topics.yaml or topics_gsma.yaml)."
    )
    parser.add_argument(
        "--topics",
        "-t",
        dest="topics_flag",
        default=None,
        help="Path to topics.yaml configuration file (flag alternative)."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="Custom directory to save the generated outputs (default: <pdf_folder>/<pdf_name>)."
    )
    parser.add_argument(
        "--exam",
        "-e",
        default=None,
        help="Name of the exam (default: cleaned PDF file name)."
    )
    args = parser.parse_args()

    # Determine topics path from positional arg, flag, or default fallback
    default_topics = "topics.yaml"
    if not Path(default_topics).exists():
        script_dir_topics = Path(__file__).resolve().parent / "topics.yaml"
        if script_dir_topics.exists():
            default_topics = str(script_dir_topics)

    topics_path = args.topics_flag or args.topics or default_topics
    run_conversion(args.pdf, topics_path, args.output_dir, args.exam)

if __name__ == "__main__":
    main()
