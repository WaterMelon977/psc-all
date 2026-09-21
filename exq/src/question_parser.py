import re
from typing import List, Tuple, Dict
from src.models import RawQuestionBlock, ParsedOption, RawLine, RawSpan

METADATA_PATTERNS = [
    re.compile(r"^(?:None\s+)?(?:Response\s+Time|Think\s+Time|Minimum\s+Instruction\s+Time|Maximum\s+Instruction\s+Time|Instruction\s+Time|Calculator|Correct\s+Marks|Wrong\s+Marks|Question\s+Number|Question\s+Id|Question\s+Type|Is\s+Question\s+Mandatory)\s*:", re.IGNORECASE),
    re.compile(r"^None\s+(?:Response|Think|Minimum|Instruction|Correct|Wrong|Calculator)", re.IGNORECASE),
    re.compile(r"^Instruction\s+Time\s*:\s*\d+", re.IGNORECASE),
    re.compile(r"^(?:N\.A\.?\s+)?(?:Minimum\s+)?Instruction\s+Time\s*:\s*\d+", re.IGNORECASE),
    re.compile(r"^(?:N\.A\.?\s+)?Think\s+Time\s*:", re.IGNORECASE),
    re.compile(r"^(?:N\.A\.?|None|Yes|No)\s*$", re.IGNORECASE),
]

METADATA_INLINE_PREFIX = re.compile(
    r"^(?:(?:None\s+|N\.A\.?\s+)*(?:Response\s+Time|Think\s+Time|Minimum\s+Instruction\s+Time|Maximum\s+Instruction\s+Time|Instruction\s+Time|Calculator|Correct\s+Marks|Wrong\s+Marks|Question\s+Number|Question\s+Id|Question\s+Type|Is\s+Question\s+Mandatory)\s*:\s*(?:N\.A\.?|\S+)\s*)+",
    re.IGNORECASE
)

def is_metadata_line(text: str) -> bool:
    clean = text.strip()
    return any(p.search(clean) for p in METADATA_PATTERNS)

def strip_metadata_prefix(text: str) -> str:
    clean = text.strip()
    m = METADATA_INLINE_PREFIX.match(clean)
    if m:
        return clean[m.end():].strip()
    return clean

class QuestionParser:
    def parse_block(self, block: RawQuestionBlock) -> Tuple[str, List[ParsedOption], List[str]]:
        """
        Parses a RawQuestionBlock into:
        - question_text (clean English text)
        - list of ParsedOption objects
        - review_issues (if options or text are missing/anomalous)
        """
        lines = block.lines
        review_issues: List[str] = []

        # 1. Skip metadata lines at start
        content_start_idx = 0
        while content_start_idx < len(lines):
            line_text = lines[content_start_idx].text.strip()
            # If line has metadata markers, skip it
            if is_metadata_line(line_text):
                content_start_idx += 1
            else:
                break

        # 2. Find "Options :" marker
        options_idx = None
        for i in range(content_start_idx, len(lines)):
            if re.match(r"^Options\s*:", lines[i].text.strip(), re.IGNORECASE):
                options_idx = i
                break

        if options_idx is None:
            # Maybe Options : is on a line that contains more text
            for i in range(content_start_idx, len(lines)):
                if "Options :" in lines[i].text:
                    options_idx = i
                    break

        if options_idx is None:
            # Fallback: cannot find Options marker
            q_text_lines = []
            for l in lines[content_start_idx:]:
                txt = strip_metadata_prefix(l.text)
                if txt and not is_metadata_line(txt):
                    q_text_lines.append(txt)
            q_text = " ".join(q_text_lines)
            review_issues.append("Could not find 'Options :' marker in question block.")
            return q_text, [], review_issues

        # Question text is everything from content_start_idx to options_idx
        q_text_parts = []
        for line in lines[content_start_idx:options_idx]:
            txt = strip_metadata_prefix(line.text)
            if txt and not is_metadata_line(txt):
                q_text_parts.append(txt)
        question_text = " ".join(q_text_parts)

        # 3. Parse options after options_idx
        # Stop if Hints : is reached
        parsed_options: List[ParsedOption] = []
        cur_opt_num: int = None
        cur_opt_text_parts: List[str] = []
        cur_opt_spans: List[RawSpan] = []

        option_regex = re.compile(r"^([1-9]\d*)\.\s*(.*)$")

        for line in lines[options_idx + 1:]:
            line_txt = line.text.strip()
            if not line_txt:
                continue

            # Stop at Hints :
            if re.match(r"^Hints\s*:", line_txt, re.IGNORECASE):
                break

            # Check if this line starts a new option
            m = option_regex.match(line_txt)
            is_new_option = False

            if m:
                opt_val = int(m.group(1))
                # Validate option sequence: expect 1 initially, then next expected number
                next_expected = 1 if cur_opt_num is None else (cur_opt_num + 1)
                # Allow next expected or reasonable option index (1..10)
                if opt_val == next_expected or (cur_opt_num is None and opt_val == 1) or (cur_opt_num is not None and opt_val > cur_opt_num and opt_val <= cur_opt_num + 2):
                    is_new_option = True

            if is_new_option:
                # Save previous option if exists
                if cur_opt_num is not None:
                    opt_str = " ".join(cur_opt_text_parts).strip()
                    parsed_options.append(ParsedOption(
                        number=cur_opt_num,
                        text=opt_str,
                        spans=cur_opt_spans
                    ))

                cur_opt_num = int(m.group(1))
                rest = m.group(2).strip()
                cur_opt_text_parts = [rest] if rest else []
                cur_opt_spans = list(line.spans)
            else:
                if cur_opt_num is not None:
                    cur_opt_text_parts.append(line_txt)
                    cur_opt_spans.extend(line.spans)

        # Save last option
        if cur_opt_num is not None:
            opt_str = " ".join(cur_opt_text_parts).strip()
            parsed_options.append(ParsedOption(
                number=cur_opt_num,
                text=opt_str,
                spans=cur_opt_spans
            ))

        if len(parsed_options) == 0:
            review_issues.append("No options could be extracted.")
        elif len(parsed_options) < 2:
            review_issues.append(f"Only {len(parsed_options)} option extracted.")

        return question_text, parsed_options, review_issues
