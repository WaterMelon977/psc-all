import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether, BaseDocTemplate, PageTemplate, Frame
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = r'C:\Windows\Fonts'
font_regular = os.path.join(FONTS_DIR, 'BOOKOS.TTF')
font_bold = os.path.join(FONTS_DIR, 'BOOKOSB.TTF')
font_italic = os.path.join(FONTS_DIR, 'BOOKOSI.TTF')
font_bolditalic = os.path.join(FONTS_DIR, 'BOOKOSBI.TTF')

if os.path.exists(font_regular) and os.path.exists(font_bold):
    pdfmetrics.registerFont(TTFont('Bookman', font_regular))
    pdfmetrics.registerFont(TTFont('Bookman-Bold', font_bold))
    FONT_REGULAR = 'Bookman'
    FONT_BOLD = 'Bookman-Bold'
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
        normal='Bookman',
        bold='Bookman-Bold',
        italic=FONT_ITALIC,
        boldItalic=FONT_BOLDITALIC
    )
else:
    FONT_REGULAR = 'Times-Roman'
    FONT_BOLD = 'Times-Bold'
    FONT_ITALIC = 'Times-Italic'
    FONT_BOLDITALIC = 'Times-BoldItalic'
    pdfmetrics.registerFontFamily(
        'Times-Roman',
        normal='Times-Roman',
        bold='Times-Bold',
        italic='Times-Italic',
        boldItalic='Times-BoldItalic'
    )


def _derive_header_title(md_path):
    """[#2] Derive running header title from markdown filename."""
    base = os.path.splitext(os.path.basename(md_path))[0]
    parts = base.replace('_', '-').split('-')
    parts_clean = [p.upper() for p in parts if p]
    title_core = ' '.join(parts_clean)
    return f"APPSC {title_core} - Topic-wise Question Bank"


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for running header, vertical divider, page numbers."""
    def __init__(self, *args, header_title="APPSC - Topic-wise Question Bank", **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []
        self._header_title = header_title

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_decorations(self, total_pages):
        self.saveState()
        page_w, page_h = A4
        margin = 32.0
        self.setFont(FONT_REGULAR, 8.5)
        self.setFillColor(colors.HexColor('#1E293B'))
        self.drawString(margin, page_h - 25, self._header_title)
        self.setLineWidth(0.6)
        self.setStrokeColor(colors.HexColor('#64748B'))
        self.line(margin, page_h - 29, page_w - margin, page_h - 29)
        self.setLineWidth(0.4)
        self.setStrokeColor(colors.HexColor('#94A3B8'))
        self.line(page_w / 2.0, 32, page_w / 2.0, page_h - 35)
        self.setLineWidth(0.4)
        self.setStrokeColor(colors.HexColor('#CBD5E1'))
        self.line(margin, 28, page_w - margin, 28)
        self.setFont(FONT_REGULAR, 8.5)
        self.setFillColor(colors.HexColor('#334155'))
        self.drawCentredString(page_w / 2.0, 16, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()


def parse_markdown_questions(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    topic_order = []
    idx_match = re.search(r'## Topic Index\s*\n(.*?)\n---', text, re.DOTALL)
    if idx_match:
        for line in idx_match.group(1).split('\n'):
            line = line.strip()
            if line.startswith('### '):
                t_name = line.replace('### ', '').strip()
                if t_name and t_name not in topic_order:
                    topic_order.append(t_name)

    q_blocks = re.split(r'## Question (\d+)', text)
    questions = []
    ans_map = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}

    for i in range(1, len(q_blocks), 2):
        q_num = int(q_blocks[i])
        q_body = q_blocks[i+1]

        t_match = re.search(r'\*\*Topic:\*\*\s*(.+)', q_body)
        topic = t_match.group(1).strip() if t_match else 'General'

        q_match = re.search(r'### Question\s*\n\s*(.*?)\s*### Options', q_body, re.DOTALL)
        raw_q_text = q_match.group(1).strip() if q_match else ''

        o_match = re.search(r'### Options\s*\n\s*(.*?)\s*### Answer', q_body, re.DOTALL)
        raw_o_text = o_match.group(1).strip() if o_match else ''

        a_match = re.search(r'### Answer\s*\n\s*>\s*\*\*Answer:\s*(.*?)\*\*', q_body, re.DOTALL)
        raw_ans = a_match.group(1).strip() if a_match else ''

        e_match = re.search(r'### Exam\s*\n\s*(.*?)(?=\n---|\n##|\Z)', q_body, re.DOTALL)
        raw_exam = e_match.group(1).strip() if e_match else ''
        clean_exam = raw_exam.replace('-', ' ')
        clean_exam = re.sub(r'\s+', ' ', clean_exam).strip()

        note = ''
        if 'Note:' in raw_o_text:
            parts = raw_o_text.split('Note:')
            raw_o_text = parts[0].strip()
            n_text = parts[1].strip()
            if n_text:
                note = f'Note: {n_text}'

        opts = {}
        if q_num == 24:
            opts = {'A': '', 'B': '78%', 'C': '8.89%', 'D': '9.62%'}
        else:
            opt_matches = list(re.finditer(r'(?:^|\n)\s*([1-4])\.\s*(.*?)(?=(?:\n\s*[1-4]\.|\Z))', raw_o_text, re.DOTALL))
            for om in opt_matches:
                digit = om.group(1)
                letter = ans_map.get(digit, digit)
                val = om.group(2).strip()
                val = re.sub(r'\s+', ' ', val)
                opts[letter] = val

        if not raw_ans or raw_ans.lower() == 'none':
            ans_display = 'None'
        else:
            tokens = [t.strip() for t in raw_ans.split(',')]
            ans_display = ', '.join([f'({ans_map.get(t, t)})' for t in tokens])

        questions.append({
            'q_num': q_num,
            'topic': topic,
            'q_text': raw_q_text,
            'options': opts,
            'raw_ans': raw_ans,
            'ans_display': ans_display,
            'exam': clean_exam,
            'note': note
        })

    return questions, topic_order


def clean_markdown_text(text):
    if not text:
        return ''
    text = text.replace('\xa0', ' ')
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    return text.strip()


def build_table_flowable(table_text, col_width, styles):
    """[#7] Markdown table -> ReportLab Table with zebra rows and dark header."""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    if len(lines) < 2:
        return None

    table_data = []
    is_header = True
    for line in lines:
        if re.match(r'^\|?[\s\-:|]+\|?$', line):
            is_header = False
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        row = []
        for cell in cells:
            clean_c = clean_markdown_text(cell)
            style_key = 'TableHeader' if is_header else 'TableCell'
            row.append(Paragraph(clean_c, styles[style_key]))
        if row:
            table_data.append(row)
        if is_header:
            is_header = False

    if not table_data:
        return None

    num_cols = max(len(r) for r in table_data)
    for r in table_data:
        while len(r) < num_cols:
            r.append(Paragraph('', styles['TableCell']))

    cell_w = col_width / float(num_cols)
    col_widths = [cell_w] * num_cols

    t = Table(table_data, colWidths=col_widths)
    ts_cmds = [
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#475569')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for row_idx in range(1, len(table_data)):
        bg = colors.HexColor('#F1F5F9') if row_idx % 2 == 0 else colors.HexColor('#FFFFFF')
        ts_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

    t.setStyle(TableStyle(ts_cmds))
    return t


_SUBSTATEMENT_PAT = re.compile(
    r'^(?:[IVX]+\.|[ivx]+\.|[a-zA-Z]\.\s|Statement\s+[IVXivx\d]+|Assertion\s*:|Reason\s*:|\(\s*[ivxIVX\d]+\s*\))',
    re.IGNORECASE
)


def _is_substatement_line(line):
    return bool(_SUBSTATEMENT_PAT.match(line.strip()))


def render_question_prompt_flowables(q_num, raw_q_text, col_w, styles):
    """[#1, #5] Question prompt with hanging-indent and sub-statement indentation."""
    flowables = []
    if raw_q_text == '*(No text)*':
        raw_q_text = ''

    table_match = re.search(r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)', raw_q_text)
    embedded_table = None
    pre_text = raw_q_text
    post_text = ''

    if table_match:
        table_str = table_match.group(1)
        pre_text = raw_q_text[:table_match.start()].strip()
        post_text = raw_q_text[table_match.end():].strip()
        embedded_table = build_table_flowable(table_str, col_w - 4, styles)

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', pre_text) if p.strip()] if pre_text else []

    if not paragraphs:
        flowables.append(Paragraph(f"<b>Q.{q_num}</b>", styles['QPrompt']))
    else:
        first_p_lines = [clean_markdown_text(l.strip()) for l in paragraphs[0].split('\n') if l.strip()]
        first_p_html = f"<b>Q.{q_num}</b>\u00a0\u00a0" + "<br/>".join(first_p_lines)
        flowables.append(Paragraph(first_p_html, styles['QPrompt']))

        for p in paragraphs[1:]:
            lines_in_p = [l.strip() for l in p.split('\n') if l.strip()]
            accumulated = []
            for line in lines_in_p:
                if _is_substatement_line(line):
                    if accumulated:
                        flowables.append(Spacer(1, 4))
                        flowables.append(Paragraph("<br/>".join(accumulated), styles['QPromptSub']))
                        accumulated = []
                    flowables.append(Paragraph(clean_markdown_text(line), styles['QPromptSubIndent']))
                else:
                    accumulated.append(clean_markdown_text(line))
            if accumulated:
                flowables.append(Spacer(1, 4))
                flowables.append(Paragraph("<br/>".join(accumulated), styles['QPromptSub']))

    if embedded_table:
        flowables.append(Spacer(1, 5))
        flowables.append(embedded_table)
        flowables.append(Spacer(1, 5))

    if post_text:
        for p in [p.strip() for p in re.split(r'\n\s*\n', post_text) if p.strip()]:
            p_lines = [clean_markdown_text(l.strip()) for l in p.split('\n') if l.strip()]
            flowables.append(Spacer(1, 4))
            flowables.append(Paragraph("<br/>".join(p_lines), styles['QPromptSub']))

    return flowables


def generate_topicwise_pdf(md_input_path, pdf_output_path):
    questions, topic_order = parse_markdown_questions(md_input_path)

    # [#2] Dynamic header title
    header_title = _derive_header_title(md_input_path)

    topics_dict = {}
    for q in questions:
        topics_dict.setdefault(q['topic'], []).append(q)

    ordered_topics = []
    for t in topic_order:
        if t in topics_dict:
            ordered_topics.append(t)
    for t in topics_dict:
        if t not in ordered_topics:
            ordered_topics.append(t)

    page_w, page_h = A4
    margin = 32.0
    top_margin = 35.0
    bottom_margin = 35.0
    gutter = 14.0
    content_w = page_w - (margin * 2)
    col_w = (content_w - gutter) / 2.0

    # Hanging indent constants
    Q_HANG = 26.0
    OPT_HANG = 18.0

    styles = {
        'TopicHeading': ParagraphStyle(
            'TopicHeading',
            fontName=FONT_BOLD,
            fontSize=9.0,
            leading=12.0,
            textColor=colors.HexColor('#FFFFFF'),
            spaceBefore=0,
            spaceAfter=0
        ),
        # [#1] Hanging indent: wrap lines align after "Q.XX  "
        'QPrompt': ParagraphStyle(
            'QPrompt',
            fontName=FONT_REGULAR,
            fontSize=8.3,
            leading=11.5,
            textColor=colors.HexColor('#0F172A'),
            leftIndent=Q_HANG,
            firstLineIndent=-Q_HANG,
            spaceAfter=3
        ),
        'QPromptSub': ParagraphStyle(
            'QPromptSub',
            fontName=FONT_REGULAR,
            fontSize=8.3,
            leading=11.5,
            textColor=colors.HexColor('#0F172A'),
            leftIndent=Q_HANG,
            spaceBefore=0,
            spaceAfter=3
        ),
        # [#5] Sub-statement lines with deeper indent
        'QPromptSubIndent': ParagraphStyle(
            'QPromptSubIndent',
            fontName=FONT_REGULAR,
            fontSize=8.1,
            leading=11.0,
            textColor=colors.HexColor('#1E293B'),
            leftIndent=Q_HANG + 10,
            spaceBefore=1,
            spaceAfter=1
        ),
        'TableCell': ParagraphStyle(
            'TableCell',
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#1E293B')
        ),
        # [#7] Table header row: white text on dark bg
        'TableHeader': ParagraphStyle(
            'TableHeader',
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#FFFFFF')
        ),
        # [#3] Option text with hanging indent
        'OptText': ParagraphStyle(
            'OptText',
            fontName=FONT_REGULAR,
            fontSize=8.0,
            leading=10.8,
            textColor=colors.HexColor('#1E293B'),
            leftIndent=OPT_HANG,
            firstLineIndent=-OPT_HANG,
        ),
        # [#4] Answer: navy bold
        'AnsText': ParagraphStyle(
            'AnsText',
            fontName=FONT_BOLD,
            fontSize=8.0,
            leading=10.5,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=2,
            spaceAfter=2
        ),
        'ExamText': ParagraphStyle(
            'ExamText',
            fontName=FONT_BOLD,
            fontSize=7.2,
            leading=9.2,
            alignment=2,
            textColor=colors.HexColor('#475569'),
            spaceBefore=2,
            spaceAfter=2
        ),
        'NoteText': ParagraphStyle(
            'NoteText',
            fontName=FONT_ITALIC,
            fontSize=7.2,
            leading=9.2,
            textColor=colors.HexColor('#475569'),
            spaceBefore=1,
            spaceAfter=2
        ),
    }

    story = []

    for topic_name in ordered_topics:
        topic_qs = topics_dict[topic_name]

        # [#6] Dark navy topic header with sky-blue left accent stripe
        p_topic = Paragraph(f"<b>{topic_name.upper()}</b>", styles['TopicHeading'])
        topic_table = Table([[p_topic]], colWidths=[col_w])
        topic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A5F')),
            ('BOX', (0, 0), (-1, -1), 0, colors.HexColor('#1E3A5F')),
            ('LINEBEFORE', (0, 0), (0, 0), 4.0, colors.HexColor('#38BDF8')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.extend([Spacer(1, 7), topic_table, Spacer(1, 7)])

        for q in topic_qs:
            prompt_flowables = render_question_prompt_flowables(
                q_num=q['q_num'],
                raw_q_text=q['q_text'],
                col_w=col_w,
                styles=styles
            )

            opts = q['options']
            opt_a = opts.get('A', '')
            opt_b = opts.get('B', '')
            opt_c = opts.get('C', '')
            opt_d = opts.get('D', '')

            # [#3] Bold label + hanging indent via OptText
            label_a = f'<font fontName="{FONT_BOLD}"><b>(A)</b></font>\u00a0'
            label_b = f'<font fontName="{FONT_BOLD}"><b>(B)</b></font>\u00a0'
            label_c = f'<font fontName="{FONT_BOLD}"><b>(C)</b></font>\u00a0'
            label_d = f'<font fontName="{FONT_BOLD}"><b>(D)</b></font>\u00a0'

            p_a = Paragraph(f"{label_a}{clean_markdown_text(opt_a)}", styles['OptText'])
            p_b = Paragraph(f"{label_b}{clean_markdown_text(opt_b)}", styles['OptText'])
            p_c = Paragraph(f"{label_c}{clean_markdown_text(opt_c)}", styles['OptText'])
            p_d = Paragraph(f"{label_d}{clean_markdown_text(opt_d)}", styles['OptText'])

            max_opt_len = max(len(opt_a), len(opt_b), len(opt_c), len(opt_d))

            if max_opt_len <= 26 and '\n' not in (opt_a + opt_b + opt_c + opt_d):
                half_w = (col_w - 4) / 2.0
                t_opts = Table([[p_a, p_b], [p_c, p_d]], colWidths=[half_w, half_w])
            else:
                t_opts = Table([[p_a], [p_b], [p_c], [p_d]], colWidths=[col_w - 4])

            t_opts.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ]))

            story.extend(prompt_flowables)
            story.append(Spacer(1, 4))
            story.append(t_opts)

            # [#4] Answer row: navy bold + subtle top rule
            ans_flowables = [Spacer(1, 4)]

            p_ans = Paragraph(f"Ans\u00a0:\u00a0{q['ans_display']}", styles['AnsText'])
            p_exam_txt = f'<font fontName="{FONT_BOLD}"><b>[{clean_markdown_text(q["exam"])}]</b></font>' if q['exam'] else ""
            p_exam = Paragraph(p_exam_txt, styles['ExamText'])

            ans_row_table = Table(
                [[p_ans, p_exam]],
                colWidths=[(col_w - 4) * 0.55, (col_w - 4) * 0.45]
            )
            ans_row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                # Subtle blue top rule above answer
                ('LINEABOVE', (0, 0), (-1, 0), 0.4, colors.HexColor('#BFDBFE')),
            ]))
            ans_flowables.append(ans_row_table)

            if q['note']:
                ans_flowables.append(Paragraph(clean_markdown_text(q['note']), styles['NoteText']))

            ans_flowables.append(Spacer(1, 2))
            ans_flowables.append(HRFlowable(
                width="100%", thickness=0.4,
                color=colors.HexColor('#E2E8F0'),
                spaceBefore=2, spaceAfter=4
            ))

            story.append(KeepTogether(ans_flowables))

    content_h = page_h - top_margin - bottom_margin
    frame_left = Frame(margin, bottom_margin, col_w, content_h, id='col1', leftPadding=0, rightPadding=4, topPadding=0, bottomPadding=0)
    frame_right = Frame(margin + col_w + gutter, bottom_margin, col_w, content_h, id='col2', leftPadding=4, rightPadding=0, topPadding=0, bottomPadding=0)

    os.makedirs(os.path.dirname(pdf_output_path), exist_ok=True)

    doc = BaseDocTemplate(
        pdf_output_path,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )
    doc.addPageTemplates([PageTemplate(id='TwoColA4', frames=[frame_left, frame_right])])

    # [#2] Pass dynamic header title via closure
    def canvas_maker(*args, **kwargs):
        return NumberedCanvas(*args, header_title=header_title, **kwargs)

    doc.build(story, canvasmaker=canvas_maker)
    print(f"Successfully generated PDF at: {pdf_output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        md_file = sys.argv[1]
        if len(sys.argv) > 2:
            pdf_file = sys.argv[2]
        else:
            base_dir = os.path.dirname(os.path.abspath(md_file))
            base_name = os.path.splitext(os.path.basename(md_file))[0]
            pdf_file = os.path.join(base_dir, f"{base_name}_TopicWise.pdf")
    else:
        md_file = r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA.md'
        pdf_file = r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA_TopicWise.pdf'

    generate_topicwise_pdf(md_file, pdf_file)
