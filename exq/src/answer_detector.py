from typing import List, Tuple
from src.models import ParsedOption

class AnswerDetector:
    def __init__(
        self,
        min_green_val: int = 80,
        max_green_other: int = 90,
        min_red_val: int = 140,
        max_red_other: int = 90
    ):
        self.min_green_val = min_green_val
        self.max_green_other = max_green_other
        self.min_red_val = min_red_val
        self.max_red_other = max_red_other

    def is_green_color(self, color_int: int) -> bool:
        if color_int == 0x008000:  # Common exact green
            return True
        r = (color_int >> 16) & 0xff
        g = (color_int >> 8) & 0xff
        b = color_int & 0xff

        # Strict green dominance
        if g >= self.min_green_val and r <= self.max_green_other and b <= self.max_green_other:
            return True
        if g >= 80 and g > (r * 1.4) and g > (b * 1.4):
            return True
        return False

    def is_red_color(self, color_int: int) -> bool:
        if color_int == 0xff0000:  # Common exact red
            return True
        r = (color_int >> 16) & 0xff
        g = (color_int >> 8) & 0xff
        b = color_int & 0xff

        # Strict red dominance
        if r >= self.min_red_val and g <= self.max_red_other and b <= self.max_red_other:
            return True
        if r >= 120 and r > (g * 1.8) and r > (b * 1.8):
            return True
        return False

    def detect_answers(self, options: List[ParsedOption]) -> Tuple[List[int], List[str]]:
        """
        Determines the correct answer option numbers based on span colors.
        Returns:
        - List of green option numbers (e.g. [1], [2, 4], or [])
        - List of review issues if missing or multiple answers detected
        """
        green_options: List[int] = []
        review_issues: List[str] = []

        valid_numbers = {opt.number for opt in options}

        for opt in options:
            has_green = False
            has_red = False

            for span in opt.spans:
                if not span.text.strip():
                    continue
                c = span.color
                if self.is_green_color(c):
                    has_green = True
                elif self.is_red_color(c):
                    has_red = True

            opt.is_green = has_green
            opt.is_red = has_red

            if has_green:
                green_options.append(opt.number)

        # Sort green options
        green_options.sort()

        if len(green_options) == 0:
            review_issues.append("Could not determine the correct answer from option colors.")
        elif len(green_options) > 1:
            opts_str = ", ".join(str(n) for n in green_options)
            review_issues.append(f"Multiple green options detected: {opts_str}")

        # Validate that detected answers match existing options
        for ans in green_options:
            if ans not in valid_numbers:
                review_issues.append(f"Detected answer option {ans} not in extracted options {list(valid_numbers)}.")

        return green_options, review_issues
