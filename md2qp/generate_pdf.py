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

# 1. Register Bookman Old Style Font & Font Family for <b>, <i> tags
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

    # Register the font family so ReportLab <b> and <i> tags resolve correctly
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


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to draw running headers, vertical column divider, and page numbers."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

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

        # Running Top Header
        self.setFont(FONT_REGULAR, 8.5)
        self.setFillColor(colors.HexColor('#1E293B'))
        header_title = "APPSC 2025 GSMA - Topic-wise Question Bank"
        self.drawString(margin, page_h - 25, header_title)
        
        # Header Top Line
        self.setLineWidth(0.6)
        self.setStrokeColor(colors.HexColor('#64748B'))
        self.line(margin, page_h - 29, page_w - margin, page_h - 29)

        # Central Vertical Divider Line between the 2 columns
        self.setLineWidth(0.4)
        self.setStrokeColor(colors.HexColor('#94A3B8'))
        self.line(page_w / 2.0, 32, page_w / 2.0, page_h - 35)

        # Footer Bottom Line & Page Number
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

    # Extract Topic Index order from top of file
    topic_order = []
    idx_match = re.search(r'## Topic Index\s*\n(.*?)\n---', text, re.DOTALL)
    if idx_match:
        for line in idx_match.group(1).split('\n'):
            line = line.strip()
            if line.startswith('### '):
                t_name = line.replace('### ', '').strip()
                if t_name and t_name not in topic_order:
                    topic_order.append(t_name)

    # Split question blocks
    q_blocks = re.split(r'## Question (\d+)', text)
    questions = []
    ans_map = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}

    for i in range(1, len(q_blocks), 2):
        q_num = int(q_blocks[i])
        q_body = q_blocks[i+1]

        # Topic
        t_match = re.search(r'\*\*Topic:\*\*\s*(.+)', q_body)
        topic = t_match.group(1).strip() if t_match else 'General'

        # Question text
        q_match = re.search(r'### Question\s*\n\s*(.*?)\s*### Options', q_body, re.DOTALL)
        raw_q_text = q_match.group(1).strip() if q_match else ''

        # Options text
        o_match = re.search(r'### Options\s*\n\s*(.*?)\s*### Answer', q_body, re.DOTALL)
        raw_o_text = o_match.group(1).strip() if o_match else ''

        # Answer text
        a_match = re.search(r'### Answer\s*\n\s*>\s*\*\*Answer:\s*(.*?)\*\*', q_body, re.DOTALL)
        raw_ans = a_match.group(1).strip() if a_match else ''

        # Exam text
        e_match = re.search(r'### Exam\s*\n\s*(.*?)(?=\n---|\n##|\Z)', q_body, re.DOTALL)
        raw_exam = e_match.group(1).strip() if e_match else ''
        clean_exam = raw_exam.replace('-', ' ')
        clean_exam = re.sub(r'\s+', ' ', clean_exam).strip()

        # Extract note if present
        note = ''
        if 'Note:' in raw_o_text:
            parts = raw_o_text.split('Note:')
            raw_o_text = parts[0].strip()
            n_text = parts[1].strip()
            if n_text:
                note = f'Note: {n_text}'

        # Parse options
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

        # Format answer display (e.g. 1 -> Ans : (A), 3, 4 -> Ans : (C), (D))
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
    """Converts bold markdown, entities, and line breaks into ReportLab-safe tags."""
    if not text:
        return ''
    # Replace non-breaking space
    text = text.replace('\xa0', ' ')
    # Escape XML chars: ampersands, < and > if not tags
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    # Convert bold **text** to <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Convert italic *text*
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    return text.strip()


def build_table_flowable(table_text, col_width, styles):
    """Parses a markdown table into a ReportLab Table."""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    if len(lines) < 2:
        return None

    table_data = []
    for line in lines:
        if re.match(r'^\|?[\s\-:|]+\|?$', line):
            continue  # separator row
        cells = [c.strip() for c in line.strip('|').split('|')]
        row = []
        for cell in cells:
            clean_c = clean_markdown_text(cell)
            row.append(Paragraph(clean_c, styles['TableCell']))
        if row:
            table_data.append(row)

    if not table_data:
        return None

    num_cols = max(len(r) for r in table_data)
    for r in table_data:
        while len(r) < num_cols:
            r.append(Paragraph('', styles['TableCell']))

    cell_w = col_width / float(num_cols)
    col_widths = [cell_w] * num_cols

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#64748B')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def render_question_prompt_flowables(q_num, raw_q_text, col_w, styles):
    """
    Renders the question prompt.
    When there is a line gap in ### Question, it renders as an elegant 2-line visual gap
    between paragraphs/sub-clauses for high readability.
    """
    flowables = []
    if raw_q_text == '*(No text)*':
        raw_q_text = ''

    # Check for embedded markdown table
    table_match = re.search(r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)', raw_q_text)
    embedded_table = None
    pre_text = raw_q_text
    post_text = ''

    if table_match:
        table_str = table_match.group(1)
        pre_text = raw_q_text[:table_match.start()].strip()
        post_text = raw_q_text[table_match.end():].strip()
        embedded_table = build_table_flowable(table_str, col_w - 4, styles)

    # Split by blank lines (paragraph breaks)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', pre_text) if p.strip()] if pre_text else []

    if not paragraphs:
        flowables.append(Paragraph(f"<b>Q.{q_num}</b>", styles['QPrompt']))
    else:
        # First paragraph includes Q.<num>
        first_p_lines = [clean_markdown_text(l.strip()) for l in paragraphs[0].split('\n') if l.strip()]
        first_p_html = f"<b>Q.{q_num}</b> " + "<br/>".join(first_p_lines)
        flowables.append(Paragraph(first_p_html, styles['QPrompt']))

        # Subsequent paragraphs get a distinct 2-line gap (Spacer(1, 5))
        for p in paragraphs[1:]:
            p_lines = [clean_markdown_text(l.strip()) for l in p.split('\n') if l.strip()]
            p_html = "<br/>".join(p_lines)
            # 2-line gap
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(p_html, styles['QPromptSub']))

    # If there is an embedded table
    if embedded_table:
        flowables.append(Spacer(1, 4))
        flowables.append(embedded_table)
        flowables.append(Spacer(1, 4))

    # If there is post_text after table
    if post_text:
        post_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', post_text) if p.strip()]
        for p in post_paragraphs:
            p_lines = [clean_markdown_text(l.strip()) for l in p.split('\n') if l.strip()]
            p_html = "<br/>".join(p_lines)
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(p_html, styles['QPromptSub']))

    return flowables


def generate_topicwise_pdf(md_input_path, pdf_output_path):
    questions, topic_order = parse_markdown_questions(md_input_path)

    # Group questions by topic
    topics_dict = {}
    for q in questions:
        topics_dict.setdefault(q['topic'], []).append(q)

    # Order topics according to markdown index
    ordered_topics = []
    for t in topic_order:
        if t in topics_dict:
            ordered_topics.append(t)
    for t in topics_dict:
        if t not in ordered_topics:
            ordered_topics.append(t)

    # Page Geometry
    page_w, page_h = A4
    margin = 32.0
    top_margin = 35.0
    bottom_margin = 35.0
    gutter = 14.0
    content_w = page_w - (margin * 2)
    col_w = (content_w - gutter) / 2.0  # ~258 pt width per column

    # Typography and Styles
    styles = {
        'TopicHeading': ParagraphStyle(
            'TopicHeading',
            fontName=FONT_BOLD,
            fontSize=10.0,
            leading=13.0,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=0,
            spaceAfter=0
        ),
        'QPrompt': ParagraphStyle(
            'QPrompt',
            fontName=FONT_REGULAR,
            fontSize=8.3,
            leading=11.2,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=3
        ),
        'QPromptSub': ParagraphStyle(
            'QPromptSub',
            fontName=FONT_REGULAR,
            fontSize=8.3,
            leading=11.2,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=0,
            spaceAfter=3
        ),
        'TableCell': ParagraphStyle(
            'TableCell',
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#1E293B')
        ),
        'OptText': ParagraphStyle(
            'OptText',
            fontName=FONT_REGULAR,
            fontSize=8.0,
            leading=10.5,
            textColor=colors.HexColor('#1E293B')
        ),
        'AnsText': ParagraphStyle(
            'AnsText',
            fontName=FONT_REGULAR,
            fontSize=8.0,
            leading=10.5,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=2,
            spaceAfter=2
        ),
        'ExamText': ParagraphStyle(
            'ExamText',
            fontName=FONT_BOLD,
            fontSize=7.2,
            leading=9.2,
            alignment=2,  # TA_RIGHT
            textColor=colors.HexColor('#334155'),
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

        # Topic Header Banner
        p_topic = Paragraph(f"<b>{topic_name.upper()}</b>", styles['TopicHeading'])
        topic_table = Table([[p_topic]], colWidths=[col_w])
        topic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('LINEBEFORE', (0, 0), (0, 0), 3.0, colors.HexColor('#0F172A')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))

        topic_flowables = [
            Spacer(1, 6),
            topic_table,
            Spacer(1, 6)
        ]
        story.extend(topic_flowables)

        # Questions within Topic
        for q in topic_qs:
            # 1. Question Prompt (Q.<num> with 2-line gaps between paragraphs)
            prompt_flowables = render_question_prompt_flowables(
                q_num=q['q_num'],
                raw_q_text=q['q_text'],
                col_w=col_w,
                styles=styles
            )

            # 2. Options Formatting: (A), (B), (C), (D) explicitly bold in Bookman-Bold
            opts = q['options']
            opt_a = opts.get('A', '')
            opt_b = opts.get('B', '')
            opt_c = opts.get('C', '')
            opt_d = opts.get('D', '')

            label_a = f'<font fontName="{FONT_BOLD}"><b>(A)</b></font> '
            label_b = f'<font fontName="{FONT_BOLD}"><b>(B)</b></font> '
            label_c = f'<font fontName="{FONT_BOLD}"><b>(C)</b></font> '
            label_d = f'<font fontName="{FONT_BOLD}"><b>(D)</b></font> '

            p_a = Paragraph(f"{label_a}{clean_markdown_text(opt_a)}", styles['OptText'])
            p_b = Paragraph(f"{label_b}{clean_markdown_text(opt_b)}", styles['OptText'])
            p_c = Paragraph(f"{label_c}{clean_markdown_text(opt_c)}", styles['OptText'])
            p_d = Paragraph(f"{label_d}{clean_markdown_text(opt_d)}", styles['OptText'])

            max_opt_len = max(len(opt_a), len(opt_b), len(opt_c), len(opt_d))

            if max_opt_len <= 26 and '\n' not in (opt_a + opt_b + opt_c + opt_d):
                half_w = (col_w - 4) / 2.0
                opt_grid = [
                    [p_a, p_b],
                    [p_c, p_d]
                ]
                t_opts = Table(opt_grid, colWidths=[half_w, half_w])
            else:
                opt_grid = [
                    [p_a],
                    [p_b],
                    [p_c],
                    [p_d]
                ]
                t_opts = Table(opt_grid, colWidths=[col_w - 4])

            t_opts.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ]))

            # Question Prompt can break across columns if needed
            story.extend(prompt_flowables)

            # Options table can also fit at the bottom of the column
            story.append(Spacer(1, 4))
            story.append(t_opts)

            # Answer and Exam tag on the SAME line (Ans on left, Exam right-aligned)
            ans_flowables = []
            ans_flowables.append(Spacer(1, 4))
            
            p_ans = Paragraph(f"Ans : {q['ans_display']}", styles['AnsText'])
            p_exam = Paragraph(f'<font fontName="{FONT_BOLD}"><b>[{clean_markdown_text(q["exam"])}]</b></font>' if q['exam'] else "", styles['ExamText'])
            
            ans_row_table = Table([[p_ans, p_exam]], colWidths=[(col_w - 4) * 0.6, (col_w - 4) * 0.4])
            ans_row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            ans_flowables.append(ans_row_table)

            if q['note']:
                clean_note = clean_markdown_text(q['note'])
                ans_flowables.append(Paragraph(clean_note, styles['NoteText']))

            ans_flowables.append(Spacer(1, 2))
            ans_flowables.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor('#E2E8F0'), spaceBefore=2, spaceAfter=4))

            story.append(KeepTogether(ans_flowables))

    # Frame and Template Setup
    content_h = page_h - top_margin - bottom_margin
    frame_left = Frame(margin, bottom_margin, col_w, content_h, id='col1', leftPadding=0, rightPadding=4, topPadding=0, bottomPadding=0)
    frame_right = Frame(margin + col_w + gutter, bottom_margin, col_w, content_h, id='col2', leftPadding=4, rightPadding=0, topPadding=0, bottomPadding=0)

    # Ensure target directory exists
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

    doc.build(story, canvasmaker=NumberedCanvas)
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
        # Default fallback
        md_file = r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA.md'
        pdf_file = r'd:\appsc-loaded\pcb-ae\pdfs\2025-GSMA\2025-GSMA_TopicWise.pdf'
        
    generate_topicwise_pdf(md_file, pdf_file)
