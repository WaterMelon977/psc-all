import os
import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether,
    BaseDocTemplate, PageTemplate, Frame, Image as RLImage, PageBreak, CondPageBreak
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Font Registration
# ---------------------------------------------------------------------------
FONTS_DIR = r'C:\Windows\Fonts'
font_regular   = os.path.join(FONTS_DIR, 'BOOKOS.TTF')
font_bold      = os.path.join(FONTS_DIR, 'BOOKOSB.TTF')
font_italic    = os.path.join(FONTS_DIR, 'BOOKOSI.TTF')
font_bolditalic= os.path.join(FONTS_DIR, 'BOOKOSBI.TTF')

if os.path.exists(font_regular) and os.path.exists(font_bold):
    pdfmetrics.registerFont(TTFont('Bookman',          font_regular))
    pdfmetrics.registerFont(TTFont('Bookman-Bold',     font_bold))
    FONT_REGULAR = 'Bookman'
    FONT_BOLD    = 'Bookman-Bold'
    if os.path.exists(font_italic):
        pdfmetrics.registerFont(TTFont('Bookman-Italic', font_italic))
        FONT_ITALIC = 'Bookman-Italic'
    else:
        FONT_ITALIC = 'Bookman'
    if os.path.exists(font_bolditalic):
        pdfmetrics.registerFont(TTFont('Bookman-BoldItalic', font_bolditalic))
        FONT_BOLDITALIC = 'Bookman-BoldItalic'
    else:
        FONT_BOLDITALIC = 'Bookman-Bold'
    pdfmetrics.registerFontFamily(
        'Bookman',
        normal='Bookman', bold='Bookman-Bold',
        italic=FONT_ITALIC, boldItalic=FONT_BOLDITALIC
    )
else:
    FONT_REGULAR    = 'Times-Roman'
    FONT_BOLD       = 'Times-Bold'
    FONT_ITALIC     = 'Times-Italic'
    FONT_BOLDITALIC = 'Times-BoldItalic'
    pdfmetrics.registerFontFamily(
        'Times-Roman',
        normal='Times-Roman', bold='Times-Bold',
        italic='Times-Italic', boldItalic='Times-BoldItalic'
    )

# ---------------------------------------------------------------------------
# Colour palette  (charcoal ink, no blue)
# ---------------------------------------------------------------------------
C_INK       = '#111827'   # near-black for all body text
C_Q_NUM     = '#111827'   # question number (same ink, weight does the work)
C_META      = '#9CA3AF'   # light gray for exam tag, footer
C_DIVIDER   = '#D1D5DB'   # single light-gray rule after each question
C_ANS_BG    = '#F3F4F6'   # subtle gray strip behind answer
C_ANS_TEXT  = '#111827'   # answer text: dark charcoal, bold
C_HDR_BG    = '#1E293B'   # topic header background (dark charcoal)
C_HDR_ACC   = '#6B7280'   # topic header left-accent stripe (slate, not blue)
C_TOPIC_TXT = '#FFFFFF'   # topic header white text
C_SUBTOPIC_BG  = '#F1F5F9' # subtopic header soft tinted background (slate-50)
C_SUBTOPIC_ACC = '#64748B' # subtopic left-accent stripe (slate-500)
C_SUBTOPIC_TXT = '#1E293B' # subtopic header dark charcoal text
C_TBL_HDR   = '#1E293B'   # match-table header row bg
C_TBL_Z1    = '#FFFFFF'   # table zebra row 1
C_TBL_Z2    = '#F9FAFB'   # table zebra row 2


# ---------------------------------------------------------------------------
# Utility: derive header title from filename
# ---------------------------------------------------------------------------
def _derive_header_title(md_path, header_override=None):
    if header_override:
        return header_override

    base = os.path.splitext(os.path.basename(md_path))[0]
    parts = base.replace('_', '-').split('-')
    title_core = ' '.join(p.upper() for p in parts if p)
    return f" {title_core}  \u2013  "


# ---------------------------------------------------------------------------
# Numbered canvas: header, column divider, quiet footer
# ---------------------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas: header, column divider, 'Page X · Y' footer."""

    def __init__(self, *args, header_title="APPSC \u2013 Topic-wise Question Bank",
                 outer_margin=42.0, show_column_divider=True, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._header_title = header_title
        self._outer_margin  = outer_margin
        self._show_column_divider = show_column_divider

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page(n)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_page(self, total):
        self.saveState()
        pw, ph = A4
        m = self._outer_margin

        # --- Header text (small, charcoal) ---
        self.setFont(FONT_REGULAR, 8.0)
        self.setFillColor(colors.HexColor('#374151'))
        self.drawString(m, ph - 24, self._header_title)

        # --- Thin gray rule under header ---
        self.setLineWidth(0.4)
        self.setStrokeColor(colors.HexColor(C_DIVIDER))
        self.line(m, ph - 28, pw - m, ph - 28)

        # --- Central column divider (light gray) - only in multi-column mode ---
        if self._show_column_divider:
            self.setLineWidth(0.3)
            self.setStrokeColor(colors.HexColor(C_DIVIDER))
            self.line(pw / 2.0, 34, pw / 2.0, ph - 34)

        # --- Footer: thin rule + "Page X · Y" ---
        self.setLineWidth(0.3)
        self.setStrokeColor(colors.HexColor(C_DIVIDER))
        self.line(m, 30, pw - m, 30)

        self.setFont(FONT_REGULAR, 7.5)
        self.setFillColor(colors.HexColor(C_META))
        self.drawCentredString(
            pw / 2.0, 17,
            f"{self._pageNumber}/{total}"
        )
        self.restoreState()


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Inline image link extractor (Graphic-Heavy CBT support)
# ---------------------------------------------------------------------------
_IMG_LINK_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def _extract_image_links(text: str, md_dir: str):
    """
    Strip all  ![alt](path)  links from *text*, resolve their paths relative to
    *md_dir*, and return (clean_text, [absolute_path_str, ...]).

    Backward compatible: if no image links are present the original text is
    returned unchanged and the paths list is empty.
    """
    paths = []
    def _repl(m):
        rel = m.group(2).strip()
        abs_p = str(Path(md_dir) / rel)
        paths.append(abs_p)
        return ''
    clean = _IMG_LINK_RE.sub(_repl, text).strip()
    return clean, paths


# ---------------------------------------------------------------------------
# Parse markdown question bank
# ---------------------------------------------------------------------------
def parse_markdown_questions(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    topic_order = []
    subtopic_order = {}  # topic -> [subtopic1, subtopic2, ...]
    current_topic_idx = None

    idx_match = re.search(r'## Topic Index\s*\n(.*?)\n---', text, re.DOTALL)
    if idx_match:
        for line in idx_match.group(1).split('\n'):
            line = line.strip()
            if line.startswith('### '):
                t = line.replace('### ', '').strip()
                if t:
                    current_topic_idx = t
                    if t not in topic_order:
                        topic_order.append(t)
                    if t not in subtopic_order:
                        subtopic_order[t] = []
            elif line.startswith('#### ') and current_topic_idx:
                s = line.replace('#### ', '').strip()
                if s and s not in subtopic_order[current_topic_idx]:
                    subtopic_order[current_topic_idx].append(s)

    q_blocks = re.split(r'## Question (\d+)', text)
    questions = []
    ans_map = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}

    for i in range(1, len(q_blocks), 2):
        q_num  = int(q_blocks[i])
        q_body = q_blocks[i + 1]

        t_m   = re.search(r'\*\*Topic:\*\*\s*(.+)', q_body)
        topic = t_m.group(1).strip() if t_m else 'General'

        s_m      = re.search(r'\*\*Subtopic:\*\*\s*(.+)', q_body)
        subtopic = s_m.group(1).strip() if s_m else ''

        q_m       = re.search(r'### Question\s*\n\s*(.*?)\s*### Options',  q_body, re.DOTALL)
        raw_q     = q_m.group(1).strip() if q_m else ''

        # Strip inline image links from question text; collect their paths for rendering.
        # Backward compatible: if no ![...]() syntax, raw_q is unchanged and fig_paths is [].
        md_dir    = str(Path(md_path).parent)
        raw_q, fig_paths = _extract_image_links(raw_q, md_dir)

        o_m       = re.search(r'### Options\s*\n\s*(.*?)\s*### Answer',    q_body, re.DOTALL)
        raw_o     = o_m.group(1).strip() if o_m else ''

        a_m       = re.search(r'### Answer\s*\n\s*>\s*\*\*Answer:\s*(.*?)\*\*', q_body, re.DOTALL)
        raw_ans   = a_m.group(1).strip() if a_m else ''

        e_m       = re.search(r'### Exam\s*\n\s*(.*?)(?=\n---|\n##|\Z)',   q_body, re.DOTALL)
        raw_exam  = e_m.group(1).strip() if e_m else ''
        clean_exam = re.sub(r'\s+', ' ', raw_exam.replace('-', ' ')).strip()

        note = ''
        if 'Note:' in raw_o:
            parts = raw_o.split('Note:')
            raw_o = parts[0].strip()
            if parts[1].strip():
                note = f'Note: {parts[1].strip()}'

        opts = {}
        if q_num == 24:
            opts = {'A': '', 'B': '78%', 'C': '8.89%', 'D': '9.62%'}
        else:
            for om in re.finditer(
                r'(?:^|\n)\s*([1-4])\.\s*(.*?)(?=(?:\n\s*[1-4]\.|\Z))',
                raw_o, re.DOTALL
            ):
                letter = ans_map.get(om.group(1), om.group(1))
                opts[letter] = re.sub(r'\s+', ' ', om.group(2).strip())

        if not raw_ans or raw_ans.lower() == 'none':
            ans_display = 'None'
        else:
            tokens = [t.strip() for t in raw_ans.split(',')]
            ans_display = ', '.join(f'({ans_map.get(t, t)})' for t in tokens)

        questions.append(dict(
            q_num=q_num, topic=topic, subtopic=subtopic, q_text=raw_q,
            options=opts, raw_ans=raw_ans,
            ans_display=ans_display, exam=clean_exam, note=note,
            fig_paths=fig_paths,
        ))

    return questions, topic_order, subtopic_order


# ---------------------------------------------------------------------------
# Markdown -> ReportLab HTML helper
# ---------------------------------------------------------------------------
def clean_md(text):
    if not text:
        return ''
    text = text.replace('\xa0', ' ')
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Match-the-following table builder  (#7 upgraded)
# ---------------------------------------------------------------------------
def build_table_flowable(table_text, col_width, styles):
    lines = [l.strip() for l in table_text.strip().split('\n') if l.strip()]
    if len(lines) < 2:
        return None

    table_data = []
    is_header  = True
    for line in lines:
        if re.match(r'^\|?[\s\-:|]+\|?$', line):
            is_header = False
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        sk = 'TableHeader' if is_header else 'TableCell'
        row = [Paragraph(clean_md(c), styles[sk]) for c in cells]
        if row:
            table_data.append(row)
        if is_header:
            is_header = False

    if not table_data:
        return None

    nc = max(len(r) for r in table_data)
    for r in table_data:
        while len(r) < nc:
            r.append(Paragraph('', styles['TableCell']))

    cw = col_width / float(nc)
    t  = Table(table_data, colWidths=[cw] * nc)

    cmds = [
        ('BOX',       (0, 0), (-1, -1), 0.5, colors.HexColor('#9CA3AF')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor(C_DIVIDER)),
        ('BACKGROUND',(0, 0), (-1,  0), colors.HexColor(C_TBL_HDR)),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('VALIGN',    (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for ri in range(1, len(table_data)):
        bg = colors.HexColor(C_TBL_Z2) if ri % 2 == 0 else colors.HexColor(C_TBL_Z1)
        cmds.append(('BACKGROUND', (0, ri), (-1, ri), bg))

    t.setStyle(TableStyle(cmds))
    return t


# ---------------------------------------------------------------------------
# Sub-statement detector
# ---------------------------------------------------------------------------
_SUB_PAT = re.compile(
    r'^(?:[IVX]+\.|[ivx]+\.|[a-zA-Z]\.\s|'
    r'Statement\s+[IVXivx\d]+|Assertion\s*:|Reason\s*:|'
    r'\(\s*[ivxIVX\d]+\s*\))',
    re.IGNORECASE
)

def _is_sub(line):
    return bool(_SUB_PAT.match(line.strip()))


# ---------------------------------------------------------------------------
# Question prompt renderer
# ---------------------------------------------------------------------------
def render_question_flowables(q_num, raw_q_text, col_w, styles, Q_HANG):
    flowables = []
    if raw_q_text == '*(No text)*':
        raw_q_text = ''

    # Detect embedded markdown table
    tbl_match = re.search(
        r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)', raw_q_text
    )
    embedded_table = None
    pre_text  = raw_q_text
    post_text = ''

    if tbl_match:
        tbl_str   = tbl_match.group(1)
        pre_text  = raw_q_text[:tbl_match.start()].strip()
        post_text = raw_q_text[tbl_match.end():].strip()
        embedded_table = build_table_flowable(tbl_str, col_w - Q_HANG - 4, styles)

    paras = [p.strip() for p in re.split(r'\n\s*\n', pre_text) if p.strip()] if pre_text else []

    # -- First paragraph: Q.<num> inline, bold+larger, rest is regular body weight
    if not paras:
        flowables.append(Paragraph(
            f'<font fontName="{FONT_BOLD}" size="9.5">Q.{q_num}</font>',
            styles['QPrompt']
        ))
    else:
        first_lines = [clean_md(l.strip()) for l in paras[0].split('\n') if l.strip()]
        q_label     = f'<font fontName="{FONT_BOLD}" size="9.5">Q.{q_num}</font>\u00a0\u00a0'
        first_html  = q_label + '<br/>'.join(first_lines)
        flowables.append(Paragraph(first_html, styles['QPrompt']))

        for p in paras[1:]:
            lines = [l.strip() for l in p.split('\n') if l.strip()]
            buf   = []
            for line in lines:
                if _is_sub(line):
                    if buf:
                        flowables.append(Spacer(1, 3))
                        flowables.append(Paragraph('<br/>'.join(buf), styles['QPromptSub']))
                        buf = []
                    flowables.append(Paragraph(clean_md(line), styles['QSubIndent']))
                else:
                    buf.append(clean_md(line))
            if buf:
                flowables.append(Spacer(1, 3))
                flowables.append(Paragraph('<br/>'.join(buf), styles['QPromptSub']))

    if embedded_table:
        flowables.append(Spacer(1, 5))
        flowables.append(embedded_table)
        flowables.append(Spacer(1, 5))

    if post_text:
        for p in [x.strip() for x in re.split(r'\n\s*\n', post_text) if x.strip()]:
            lines = [clean_md(l.strip()) for l in p.split('\n') if l.strip()]
            flowables.append(Spacer(1, 3))
            flowables.append(Paragraph('<br/>'.join(lines), styles['QPromptSub']))

    return flowables


# ---------------------------------------------------------------------------
# Main PDF generator
# ---------------------------------------------------------------------------
def generate_topicwise_pdf(md_input_path, pdf_output_path, header_override=None, single_col=False, page_per_topic=False):
    parsed_res = parse_markdown_questions(md_input_path)
    if len(parsed_res) == 3:
        questions, topic_order, subtopic_order = parsed_res
    else:
        questions, topic_order = parsed_res
        subtopic_order = {}
    header_title = _derive_header_title(md_input_path, header_override=header_override)

    # Group & order by topic
    topics_dict = {}
    for q in questions:
        topics_dict.setdefault(q['topic'], []).append(q)
    ordered_topics = [t for t in topic_order if t in topics_dict]
    for t in topics_dict:
        if t not in ordered_topics:
            ordered_topics.append(t)

    # ----- Page geometry -----
    page_w, page_h = A4
    MARGIN     = 42.0   # wider outer margin (was 32)
    TOP_M      = 38.0
    BOTTOM_M   = 38.0
    GUTTER     = 16.0
    content_w  = page_w - MARGIN * 2

    # Single-column mode: col_w spans full content width (no gutter needed).
    # All indents, option widths, and image widths are derived from col_w,
    # so they expand automatically. Backward compatible: default is False.
    if single_col:
        col_w = content_w
    else:
        col_w = (content_w - GUTTER) / 2.0   # ~244 pt (two-column default)

    # Indent constants
    Q_HANG   = 28.0   # hanging indent for Q. label
    OPT_IND  = Q_HANG # options align below question body (same left edge)
    OPT_HANG = 20.0   # hanging for (A)/(B) label within option cell

    # ----- Styles -----
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    ST = {
        # Topic header: white bold on dark charcoal
        'TopicHeading': S('TopicHeading',
            fontName=FONT_BOLD, fontSize=9.0, leading=12.0,
            textColor=colors.HexColor(C_TOPIC_TXT)),

        # Subtopic header: pronounced yet soft, dark charcoal bold on soft slate tint
        'SubtopicHeading': S('SubtopicHeading',
            fontName=FONT_BOLD, fontSize=7.8, leading=10.5,
            textColor=colors.HexColor(C_SUBTOPIC_TXT)),

        # Question number: regular style; Q.<n> inline gets larger bold via font tag
        'QPrompt': S('QPrompt',
            fontName=FONT_REGULAR, fontSize=8.5, leading=12.0,
            textColor=colors.HexColor(C_INK),
            leftIndent=Q_HANG, firstLineIndent=-Q_HANG,
            spaceAfter=0),

        # Continuation paragraphs (sub-clauses, multi-para)
        'QPromptSub': S('QPromptSub',
            fontName=FONT_REGULAR, fontSize=8.5, leading=12.0,
            textColor=colors.HexColor(C_INK),
            leftIndent=Q_HANG, spaceAfter=0),

        # Numbered sub-statements (i. ii. iii. / Roman numerals)
        'QSubIndent': S('QSubIndent',
            fontName=FONT_REGULAR, fontSize=8.2, leading=11.5,
            textColor=colors.HexColor('#374151'),
            leftIndent=Q_HANG + 12, spaceBefore=1, spaceAfter=1),

        # Option text: body weight, hanging for (A) label
        'OptText': S('OptText',
            fontName=FONT_REGULAR, fontSize=8.2, leading=11.0,
            textColor=colors.HexColor(C_INK),
            leftIndent=OPT_HANG, firstLineIndent=-OPT_HANG),

        # Answer text: dark charcoal bold (no blue)
        'AnsText': S('AnsText',
            fontName=FONT_BOLD, fontSize=8.0, leading=10.5,
            textColor=colors.HexColor(C_ANS_TEXT)),

        # Exam tag: light gray, right-aligned
        'ExamText': S('ExamText',
            fontName=FONT_REGULAR, fontSize=7.5, leading=9.5,
            alignment=2, textColor=colors.HexColor(C_META)),

        # Note text
        'NoteText': S('NoteText',
            fontName=FONT_ITALIC, fontSize=7.2, leading=9.5,
            textColor=colors.HexColor(C_META)),

        # Match-table cells
        'TableCell': S('TableCell',
            fontName=FONT_REGULAR, fontSize=7.5, leading=9.5,
            textColor=colors.HexColor(C_INK)),
        'TableHeader': S('TableHeader',
            fontName=FONT_BOLD, fontSize=7.5, leading=9.5,
            textColor=colors.HexColor('#FFFFFF')),
    }

    # Helper: wrap any flowable in an indent spacer table
    def indented(flowable, indent, total_w):
        t = Table([[Spacer(1, 1), flowable]],
                  colWidths=[indent, total_w - indent])
        t.setStyle(TableStyle([
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ]))
        return t

    def render_subtopic_banner(subtopic_name, width):
        p_sub = Paragraph(f'{clean_md(subtopic_name)}', ST['SubtopicHeading'])
        sub_tbl = Table([[p_sub]], colWidths=[width])
        sub_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor(C_SUBTOPIC_BG)),
            ('BOX',           (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('LINEBEFORE',    (0, 0), (0,  0), 2.5, colors.HexColor(C_SUBTOPIC_ACC)),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ]))
        return sub_tbl

    # ---- Story ----
    story = []

    for topic_idx, topic_name in enumerate(ordered_topics):
        topic_qs = topics_dict[topic_name]

        # Start each topic on a fresh page if page_per_topic is True (after first topic)
        if page_per_topic and topic_idx > 0:
            story.append(PageBreak())

        # Dark charcoal topic banner with slate left stripe
        p_topic = Paragraph(f'<b>{topic_name.upper()}</b>', ST['TopicHeading'])
        topic_tbl = Table([[p_topic]], colWidths=[col_w])
        topic_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor(C_HDR_BG)),
            ('BOX',           (0, 0), (-1, -1), 0, colors.HexColor(C_HDR_BG)),
            ('LINEBEFORE',    (0, 0), (0,  0), 4.0, colors.HexColor(C_HDR_ACC)),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 9),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ]))
        story.extend([Spacer(1, 8), topic_tbl, Spacer(1, 6)])

        # Subtopic groupings within topic
        # Check if any question has a subtopic
        has_subtopics = any(bool(q.get('subtopic')) for q in topic_qs)

        if has_subtopics:
            sub_dict = {}
            for q in topic_qs:
                sub_dict.setdefault(q.get('subtopic', ''), []).append(q)

            defined_sub_order = subtopic_order.get(topic_name, [])
            ordered_subs = [s for s in defined_sub_order if s in sub_dict]
            for s in sub_dict:
                if s and s not in ordered_subs:
                    ordered_subs.append(s)
            if '' in sub_dict:
                ordered_subs.append('')

            subtopic_groups = [(s, sub_dict[s]) for s in ordered_subs]
        else:
            subtopic_groups = [('', topic_qs)]

        for sub_name, qs_in_sub in subtopic_groups:
            if sub_name:
                sub_banner = render_subtopic_banner(sub_name, col_w)
                story.extend([Spacer(1, 4), sub_banner, Spacer(1, 6)])

            for q in qs_in_sub:
                # 1. Question prompt (Q. number bold 9.5pt; body regular 8.5pt)
                prompt_fls = render_question_flowables(
                    q['q_num'], q['q_text'], col_w, ST, Q_HANG
                )

                # 2. Options: rigid 2-col grid, indented to align below question body
                opts   = q['options']
                opt_a  = opts.get('A', '')
                opt_b  = opts.get('B', '')
                opt_c  = opts.get('C', '')
                opt_d  = opts.get('D', '')

                lbl_a = f'<font fontName="{FONT_BOLD}">(A)</font>\u00a0'
                lbl_b = f'<font fontName="{FONT_BOLD}">(B)</font>\u00a0'
                lbl_c = f'<font fontName="{FONT_BOLD}">(C)</font>\u00a0'
                lbl_d = f'<font fontName="{FONT_BOLD}">(D)</font>\u00a0'

                p_a = Paragraph(f'{lbl_a}{clean_md(opt_a)}', ST['OptText'])
                p_b = Paragraph(f'{lbl_b}{clean_md(opt_b)}', ST['OptText'])
                p_c = Paragraph(f'{lbl_c}{clean_md(opt_c)}', ST['OptText'])
                p_d = Paragraph(f'{lbl_d}{clean_md(opt_d)}', ST['OptText'])

                opts_inner_w  = col_w - OPT_IND - 4
                max_len = max(len(opt_a), len(opt_b), len(opt_c), len(opt_d))

                if max_len <= 26 and '\n' not in (opt_a + opt_b + opt_c + opt_d):
                    hw = opts_inner_w / 2.0
                    t_opts = Table([[p_a, p_b], [p_c, p_d]], colWidths=[hw, hw])
                else:
                    t_opts = Table([[p_a], [p_b], [p_c], [p_d]], colWidths=[opts_inner_w])

                t_opts.setStyle(TableStyle([
                    ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING',   (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
                    ('TOPPADDING',    (0, 0), (-1, -1), 1),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))

                # 3. Answer strip: subtle gray background, single line
                ans_w    = col_w - OPT_IND
                p_ans    = Paragraph(f'Ans\u00a0:\u00a0{q["ans_display"]}', ST['AnsText'])
                exam_txt = f'[{clean_md(q["exam"])}]' if q['exam'] else ''
                p_exam   = Paragraph(exam_txt, ST['ExamText'])

                ans_strip = Table(
                    [[p_ans, p_exam]],
                    colWidths=[ans_w * 0.55, ans_w * 0.45]
                )
                ans_strip.setStyle(TableStyle([
                    ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor(C_ANS_BG)),
                    ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING',   (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
                    ('TOPPADDING',    (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))

                # Assemble: extend story with prompt, then optional figures, then KeepTogether for opts+ans+divider
                story.extend(prompt_fls)

                # Inline diagram images (Graphic-Heavy CBT mode).
                # Backward compatible: fig_paths is [] for all non-graphic questions.
                for fig_abs in q.get('fig_paths', []):
                    fig_p = Path(fig_abs)
                    if fig_p.exists():
                        try:
                            # Determine natural image dimensions to compute proportional height.
                            # PIL is already a transitive dep (via Pillow used by fitz).
                            from PIL import Image as PILImage
                            with PILImage.open(str(fig_p)) as _pil:
                                nat_w, nat_h = _pil.size  # pixels
                            if nat_w > 0:
                                target_w = col_w * 0.90          # 90% of column width in points
                                target_h = target_w * nat_h / nat_w
                                img_fl = RLImage(str(fig_p), width=target_w, height=target_h)
                                story.append(Spacer(1, 4))
                                story.append(img_fl)
                                story.append(Spacer(1, 4))
                        except Exception as _img_err:
                            # Silently skip unreadable/corrupt image files
                            pass

                ans_block = [
                    Spacer(1, 5),
                    indented(t_opts, OPT_IND, col_w),
                    Spacer(1, 4),
                    indented(ans_strip, OPT_IND, col_w),
                ]

                if q['note']:
                    ans_block.append(Spacer(1, 2))
                    ans_block.append(Paragraph(clean_md(q['note']), ST['NoteText']))

                # In 2-col mode: ONE light-gray divider per question, with breathing room after.
                # In single-col mode: omit the separator line for a clean layout.
                if not single_col:
                    ans_block.append(HRFlowable(
                        width='100%', thickness=0.35,
                        color=colors.HexColor(C_DIVIDER),
                        spaceBefore=5, spaceAfter=8   # 8pt between questions
                    ))
                else:
                    ans_block.append(Spacer(1, 10))

                story.append(KeepTogether(ans_block))

    # ----- Frames & doc -----
    content_h = page_h - TOP_M - BOTTOM_M

    if single_col:
        # One full-width frame spanning the entire content area
        frames = [Frame(
            MARGIN, BOTTOM_M, content_w, content_h,
            id='col1', leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0
        )]
        page_template_id = 'SingleColA4'
    else:
        # Standard two-column layout
        frames = [
            Frame(MARGIN,                  BOTTOM_M, col_w, content_h,
                  id='col1', leftPadding=0, rightPadding=4,
                  topPadding=0, bottomPadding=0),
            Frame(MARGIN + col_w + GUTTER, BOTTOM_M, col_w, content_h,
                  id='col2', leftPadding=4, rightPadding=0,
                  topPadding=0, bottomPadding=0),
        ]
        page_template_id = 'TwoColA4'

    os.makedirs(os.path.dirname(os.path.abspath(pdf_output_path)), exist_ok=True)

    doc = BaseDocTemplate(
        pdf_output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=TOP_M,   bottomMargin=BOTTOM_M
    )
    doc.addPageTemplates([PageTemplate(
        id=page_template_id, frames=frames
    )])

    def canvas_maker(*args, **kwargs):
        return NumberedCanvas(
            *args,
            header_title=header_title,
            outer_margin=MARGIN,
            show_column_divider=(not single_col),
            **kwargs
        )

    doc.build(story, canvasmaker=canvas_maker)
    print(f"Successfully generated PDF at: {pdf_output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate clean topic-wise question paper PDF from markdown.',
        add_help=False
    )
    # Enable -h / --header or help manually
    parser.add_argument('md_file', nargs='?', default=r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA.md',
                        help='Path to input markdown file')
    parser.add_argument('pdf_file', nargs='?', default=None,
                        help='Path to output PDF file (optional)')
    parser.add_argument('-h', '--header', dest='header', default=None,
                        help='Header label override (e.g. GSMA -> "APPSC 2026 GSMA – Topic-wise Question Bank")')
    parser.add_argument('--single-col', action='store_true', default=False,
                        help='Use single-column layout instead of the default two-column layout. '
                             'Recommended for graphic-heavy papers with large diagram images.')
    parser.add_argument('--page-per-topic', action='store_true', default=False,
                        help='Start each topic section on a new page.')
    parser.add_argument('--help', action='help', help='Show this help message and exit')

    args = parser.parse_args()

    md_file = args.md_file
    if args.pdf_file:
        pdf_file = args.pdf_file
    else:
        pdf_file = os.path.join(
            os.path.dirname(os.path.abspath(md_file)),
            os.path.splitext(os.path.basename(md_file))[0] + '_TopicWise.pdf'
        )

    generate_topicwise_pdf(
        md_file, pdf_file,
        header_override=args.header,
        single_col=args.single_col,
        page_per_topic=args.page_per_topic
    )
