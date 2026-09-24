from typing import List, Dict
from src.models import Question
from src.question_formatter import format_question_text

class MarkdownRenderer:
    def __init__(self, topics_order: List[str], paper_title: str = "APPSC Question Bank", default_exam: str = ""):
        self.topics_order = topics_order
        self.paper_title = paper_title
        self.default_exam = default_exam

    def render(self, questions: List[Question]) -> str:
        lines: List[str] = []

        # Filter out questions where neither text nor options were extracted
        valid_questions = [q for q in questions if (q.question_text and q.question_text.strip()) or q.options]

        # 1. Main Title
        lines.append(f"# {self.paper_title}")
        lines.append("")

        # 2. Topic Index
        lines.append("## Topic Index")
        lines.append("")

        # Group question numbers by topic (only for valid questions with text)
        topic_to_qnums: Dict[str, List[int]] = {t: [] for t in self.topics_order}
        for q in valid_questions:
            if q.topic in topic_to_qnums:
                topic_to_qnums[q.topic].append(q.question_number)
            else:
                topic_to_qnums.setdefault(q.topic, []).append(q.question_number)

        # Output topics in exact topics_order
        for topic in self.topics_order:
            qnums = topic_to_qnums.get(topic, [])
            lines.append(f"### {topic}")
            lines.append("")
            if qnums:
                for qn in sorted(qnums):
                    lines.append(f"- Q{qn}")
            else:
                lines.append("*(No questions)*")
            lines.append("")

        # Also include any topics that might have been dynamically classified but not in topics_order
        for topic, qnums in topic_to_qnums.items():
            if topic not in self.topics_order and qnums:
                lines.append(f"### {topic}")
                lines.append("")
                for qn in sorted(qnums):
                    lines.append(f"- Q{qn}")
                lines.append("")

        lines.append("---")
        lines.append("")

        # 3. Questions in original sequence
        lines.append("# Questions")
        lines.append("")

        for i, q in enumerate(valid_questions):
            lines.append(f"## Question {q.question_number}")
            lines.append("")
            lines.append(f"**Topic:** {q.topic}")
            lines.append("")
            lines.append("### Question")
            lines.append("")
            formatted = format_question_text(q.question_text) if q.question_text else "*(No text)*"
            lines.append(formatted)
            lines.append("")

            # Insert figure image links for Graphic-Heavy CBT mode.
            # Backward compatible: q.figures defaults to [], so standard papers are unaffected.
            for fig_idx, fig_path in enumerate(q.figures or [], start=1):
                lines.append(f"![Figure {fig_idx} for Q{q.question_number}]({fig_path})")
                lines.append("")

            lines.append("### Options")
            lines.append("")

            # Sort options numerically
            sorted_opt_keys = sorted(q.options.keys(), key=lambda k: int(k) if k.isdigit() else 999)
            if sorted_opt_keys:
                for opt_k in sorted_opt_keys:
                    opt_text = q.options[opt_k]
                    lines.append(f"{opt_k}. {opt_text}")
            else:
                lines.append("*(No options)*")

            lines.append("")
            lines.append("### Answer")
            lines.append("")

            if getattr(q, "answer_text", ""):
                # Final Key mode: direct textual answer (no options list)
                lines.append(f"> **Answer: {q.answer_text}**")
            elif q.answer:
                ans_str = ", ".join(str(a) for a in q.answer)
                lines.append(f"> **Answer: {ans_str}**")
            else:
                lines.append("> **Answer: None**")


            exam_val = q.exam or self.default_exam
            if exam_val:
                lines.append("")
                lines.append("### Exam")
                lines.append("")
                lines.append(exam_val)

            lines.append("")
            if i < len(questions) - 1:
                lines.append("---")
                lines.append("")

        return "\n".join(lines).strip() + "\n"
