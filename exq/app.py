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
from src.local_ocr_extractor import LocalOcrExtractor
from src.booklet_extractor import BookletExtractor

# Ensure utf-8 output on standard output across platforms
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def run_conversion(pdf_path: str, topics_path: str, output_dir: str = None, exam: str = None, format_mode: str = None):
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
    default_exam_tag = exam if exam else paper_name.replace('_', ' ').replace('-', ' ').strip()
    cleaned_exam_name = default_exam_tag

    if output_dir:
        out_dir = Path(output_dir).resolve()
    else:
        # Output folder in the same folder as the pdf, named the same as the pdf name
        out_dir = pdf_file.parent / paper_name

    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading PDF...")
    auto_is_booklet = PDFExtractor.is_booklet_format(str(pdf_file))
    
    if format_mode:
        is_booklet = (format_mode.lower() in ["offline", "booklet", "2"])
    else:
        # If running interactively in terminal, confirm with user
        detected_label = "Offline Booklet" if auto_is_booklet else "Online CBT"
        default_choice = "2" if auto_is_booklet else "1"
        try:
            if sys.stdin.isatty():
                prompt = (
                    f"\nSelect Format (detected: {detected_label}):\n"
                    f"  [1] Online CBT\n"
                    f"  [2] Offline Booklet\n"
                    f"Choice [{default_choice}]: "
                )
                user_choice = input(prompt).strip()
                if not user_choice:
                    user_choice = default_choice
                is_booklet = (user_choice in ["2", "offline", "booklet"])
            else:
                is_booklet = auto_is_booklet
        except Exception:
            is_booklet = auto_is_booklet
    topic_classifier = TopicClassifier(str(topics_file))
    topic_distribution = {t: 0 for t in topic_classifier.topics_order}
    structured_questions = []
    answers_detected_count = 0
    anomalies = []

    if is_booklet:
        print("Detected Offline Question Booklet format.")
        print("Extracting questions & boxed answers via BookletExtractor...")
        booklet_extractor = BookletExtractor(str(pdf_file), exam_name=cleaned_exam_name)
        extracted_questions, total_pages = booklet_extractor.extract_questions()
        total_blocks_count = len(extracted_questions)
        telugu_discarded = 0
        print(f"Extracted {len(extracted_questions)} questions.")

        print("Classifying topics...")
        for q in extracted_questions:
            if q.answer:
                answers_detected_count += 1
            topic, scores = topic_classifier.classify(q.question_text, q.options)
            q.topic = topic
            q.topic_scores = scores
            topic_distribution[topic] = topic_distribution.get(topic, 0) + 1
            structured_questions.append(q)
    else:
        print("Detected Online CBT format.")
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
        question_parser = QuestionParser()
        answer_detector = AnswerDetector()
        ocr_extractor = LocalOcrExtractor()

        for block in english_blocks:
            q_text, parsed_opts, parse_issues = question_parser.parse_block(block)

            # Fallback to local RapidOCR strictly when question text or options could not be extracted (or options are blank image options)
            has_empty_options = len(parsed_opts) == 0 or all(not opt.text.strip() for opt in parsed_opts)
            if (not q_text.strip() or has_empty_options):
                print(f"  [Local OCR Fallback] Question {block.qnum} has missing text/options. Extracting via RapidOCR...")
                vis_text, vis_opts, vis_ans = ocr_extractor.extract(block)
                if vis_text or vis_opts:
                    if vis_text:
                        q_text = vis_text
                    # Prefer text options if parsed_opts already had text
                    if any(opt.text.strip() for opt in parsed_opts):
                        opts_dict = {str(opt.number): opt.text for opt in parsed_opts}
                        detected_answers, ans_issues = answer_detector.detect_answers(parsed_opts)
                    else:
                        opts_dict = vis_opts
                        detected_answers = vis_ans
                        ans_issues = []
                    # Clear option/marker failure warnings from parse_issues since content was extracted
                    parse_issues = [
                        i for i in parse_issues
                        if "No options" not in i and "marker in question block" not in i and "Only " not in i
                    ]
                else:
                    detected_answers, ans_issues = answer_detector.detect_answers(parsed_opts)
                    opts_dict = {str(opt.number): opt.text for opt in parsed_opts}
            else:
                detected_answers, ans_issues = answer_detector.detect_answers(parsed_opts)
                opts_dict = {str(opt.number): opt.text for opt in parsed_opts}

            if detected_answers:
                answers_detected_count += 1

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
    parser.add_argument(
        "--format",
        "-f",
        dest="format_mode",
        choices=["cbt", "offline", "booklet"],
        default=None,
        help="Force format mode: 'cbt' or 'offline' / 'booklet'."
    )
    args = parser.parse_args()

    # Determine topics path from positional arg, flag, or default fallback
    default_topics = "topics.yaml"
    if not Path(default_topics).exists():
        script_dir_topics = Path(__file__).resolve().parent / "topics.yaml"
        if script_dir_topics.exists():
            default_topics = str(script_dir_topics)

    topics_path = args.topics_flag or args.topics or default_topics

    # Interactive prompt for Exam tag if not provided
    exam_tag = args.exam
    if not exam_tag and sys.stdin.isatty():
        default_tag = Path(args.pdf).stem.replace('_', ' ').replace('-', ' ').strip()
        try:
            user_tag = input(f"Exam tag [-e] (press Enter for '{default_tag}'): ").strip()
            if user_tag:
                exam_tag = user_tag
        except Exception:
            pass

    run_conversion(args.pdf, topics_path, args.output_dir, exam_tag, args.format_mode)

if __name__ == "__main__":
    main()
