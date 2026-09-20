from typing import List
from src.models import Question

class ReviewGenerator:
    def generate(self, questions: List[Question], general_issues: List[str] = None) -> str:
        lines: List[str] = ["# Review Required", ""]

        review_questions = [q for q in questions if q.review_issues]

        if not review_questions and not general_issues:
            lines.append("No issues detected.")
            return "\n".join(lines).strip() + "\n"

        if general_issues:
            lines.append("## General Document Issues")
            lines.append("")
            for gi in general_issues:
                lines.append(f"- {gi}")
            lines.append("")
            if review_questions:
                lines.append("---")
                lines.append("")

        for i, q in enumerate(review_questions):
            lines.append(f"## Question {q.question_number}")
            lines.append("")
            lines.append(f"**Page:** {q.page_number}")
            lines.append("")
            for issue in q.review_issues:
                lines.append(f"**Issue:** {issue}")
                lines.append("")
            if len(q.answer) > 1:
                opts_str = ", ".join(str(a) for a in q.answer)
                lines.append(f"**Detected options:** {opts_str}")
                lines.append("")
            if i < len(review_questions) - 1:
                lines.append("---")
                lines.append("")

        return "\n".join(lines).strip() + "\n"
