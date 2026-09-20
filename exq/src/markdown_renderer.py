from typing import List, Dict
from src.models import Question
from src.question_formatter import format_question_text

class MarkdownRenderer:
    def __init__(self, topics_order: List[str], paper_title: str = "APPSC Question Bank"):
        self.topics_order = topics_order
        self.paper_title = paper_title

    def render(self, questions: List[Question]) -> str:
        lines: List[str] = []

        # 1. Main Title
        lines.append(f"# {self.paper_title}")
        lines.append("")

        # 2. Topic Index
        lines.append("## Topic Index")
        lines.append("")

        # Group question numbers by topic
        topic_to_qnums: Dict[str, List[int]] = {t: [] for t in self.topics_order}
        for q in questions:
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

        for i, q in enumerate(questions):
            lines.append(f"## Question {q.question_number}")
            lines.append("")
            lines.append(f"**Topic:** {q.topic}")
            lines.append("")
            lines.append("### Question")
            lines.append("")
            formatted = format_question_text(q.question_text) if q.question_text else "*(No text)*"
            lines.append(formatted)
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

            if q.answer:
                ans_str = ", ".join(str(a) for a in q.answer)
                lines.append(f"> **Answer: {ans_str}**")
            else:
                lines.append("> **Answer: None**")

            lines.append("")
            if i < len(questions) - 1:
                lines.append("---")
                lines.append("")

        return "\n".join(lines).strip() + "\n"
