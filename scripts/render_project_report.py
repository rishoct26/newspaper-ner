"""Render docs/project_report.md to a paginated PDF with embedded local figures."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageTemplate,
    PageBreak,
    NextPageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/project_report.md"
OUTPUT = ROOT / "docs/project_report.pdf"
NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#245B83")
PALE = colors.HexColor("#EAF1F6")
INK = colors.HexColor("#202A33")
MUTED = colors.HexColor("#5D6973")


def inline_markup(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^ )]+)\)",
        lambda m: f'<link href="{html.escape(m.group(2), quote=True)}" color="#245B83"><u>{m.group(1)}</u></link>',
        text,
    )
    return text


def page_chrome(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D6DEE5"))
    canvas.setLineWidth(0.5)
    canvas.line(0.67 * inch, height - 0.48 * inch, width - 0.67 * inch, height - 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.68 * inch, height - 0.36 * inch, "NEWSPAPER NER | ENGLISH DEVELOPMENT PILOT")
    canvas.line(0.67 * inch, 0.52 * inch, width - 0.67 * inch, 0.52 * inch)
    canvas.drawString(0.68 * inch, 0.34 * inch, "Experiential Learning Group Assignment | 12 November 2026")
    canvas.drawRightString(width - 0.68 * inch, 0.34 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=NAVY, alignment=TA_LEFT, spaceAfter=16),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Heading2"], fontName="Helvetica", fontSize=15, leading=20, textColor=BLUE, spaceAfter=18),
        "h2": ParagraphStyle("Section", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=15, spaceAfter=8, keepWithNext=True),
        "h3": ParagraphStyle("Subsection", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "h4": ParagraphStyle("MinorHeading", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=8, spaceAfter=4, keepWithNext=True),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.3, textColor=INK, spaceAfter=7, alignment=TA_LEFT, splitLongWords=1),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.0, leading=10.4, textColor=INK, spaceAfter=5, splitLongWords=1),
        "caption": ParagraphStyle("Caption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4, spaceAfter=9),
        "quote": ParagraphStyle("Quote", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=8.6, leading=12, leftIndent=12, rightIndent=8, borderColor=BLUE, borderWidth=2, borderPadding=7, textColor=MUTED, backColor=PALE, spaceBefore=5, spaceAfter=10),
        "code": ParagraphStyle("CodeBlock", parent=base["Code"], fontName="Courier", fontSize=7.1, leading=9.4, textColor=INK, leftIndent=5, rightIndent=5, spaceBefore=4, spaceAfter=8, splitLongWords=1),
    }


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_to_story(markdown: str, styles: dict):
    lines = markdown.splitlines()
    story = []
    i = 0
    in_code = False
    code_lines: list[str] = []
    first_title = True
    list_items: list[tuple[str, str]] = []

    def flush_list():
        nonlocal list_items
        if not list_items:
            return
        for index, (kind, text) in enumerate(list_items, start=1):
            prefix = "- " if kind == "bullet" else f"{index}. "
            story.append(Paragraph(prefix + inline_markup(text), styles["body"]))
        list_items = []

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            flush_list()
            if in_code:
                code = Preformatted("\n".join(code_lines), styles["code"], maxLineLength=105)
                story.append(Table([[code]], colWidths=[6.9 * inch], style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F5F7")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6DEE5")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])))
                if any(item.strip() for item in lines[i + 1 :]):
                    story.append(Spacer(1, 5))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if line.strip() == "<!-- pagebreak -->":
            flush_list()
            story.append(NextPageTemplate("report"))
            story.append(PageBreak())
            i += 1
            continue
        if line.startswith("| ") or line.startswith("||"):
            flush_list()
            table_lines = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = [split_table_row(item) for item in table_lines]
            rows = [row for row in rows if not all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in row)]
            if rows:
                cols = max(map(len, rows))
                fixed = [row + [""] * (cols - len(row)) for row in rows]
                available = 6.95 * inch
                widths = [available / cols] * cols
                font_size = 7.6 if cols <= 4 else 7.0
                cell_style = ParagraphStyle("Cell", parent=styles["small"], fontSize=font_size, leading=font_size + 2.2, spaceAfter=0)
                header_style = ParagraphStyle("HeaderCell", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
                data = [[Paragraph(inline_markup(cell), header_style if row_index == 0 else cell_style) for cell in row] for row_index, row in enumerate(fixed)]
                table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BAC6D0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F9")]),
                ]))
                story.append(KeepTogether([table, Spacer(1, 8)]))
            continue
        if not line.strip():
            flush_list()
            i += 1
            continue
        if line.strip() in {"---", "***"}:
            flush_list()
            story.append(Spacer(1, 6))
            i += 1
            continue
        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip())
        if image_match:
            flush_list()
            image_path = (SOURCE.parent / image_match.group(2)).resolve()
            if image_path.is_file():
                img = Image(str(image_path), width=6.85 * inch, height=6.85 * inch, kind="proportional", hAlign="CENTER")
                story.extend([img, Paragraph(html.escape(image_match.group(1)), styles["caption"])])
            else:
                story.append(Paragraph(f"[Figure asset not available locally: {html.escape(image_match.group(1))}]", styles["caption"]))
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            flush_list()
            level, text = len(heading.group(1)), heading.group(2).strip()
            if level == 1 and first_title:
                story.append(Spacer(1, 1.1 * inch))
                story.append(Paragraph(inline_markup(text), styles["title"]))
                first_title = False
            elif level == 2:
                story.append(Paragraph(inline_markup(text), styles["h2"]))
            elif level == 3:
                story.append(Paragraph(inline_markup(text), styles["h3"]))
            else:
                story.append(Paragraph(inline_markup(text), styles["h4"]))
            i += 1
            continue
        if line.startswith("> "):
            flush_list()
            story.append(Paragraph(inline_markup(line[2:]), styles["quote"]))
            i += 1
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        numbered = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if bullet or numbered:
            kind, text = ("bullet", bullet.group(1)) if bullet else ("number", numbered.group(1))
            list_items.append((kind, text))
            i += 1
            continue
        flush_list()
        paragraph = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "> ", "```", "<!-- pagebreak")) and not re.match(r"^\s*[-*]\s+|^\s*\d+\.\s+|^!\[", lines[i]):
            paragraph.append(lines[i].strip())
            i += 1
        text = " ".join(paragraph)
        if text.startswith("**") and "  " in text:
            parts = text.split("  ")
            for part in parts:
                if part:
                    story.append(Paragraph(inline_markup(part), styles["small"]))
        else:
            story.append(Paragraph(inline_markup(text), styles["body"]))
    flush_list()
    return story


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    styles = build_styles()
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=0.68 * inch, rightMargin=0.68 * inch,
        topMargin=0.68 * inch, bottomMargin=0.72 * inch,
        title="Named Entity Recognition from Scanned Newspaper Pages",
        author="Experiential Learning Group - complete member details before submission",
        subject="English development prototype report",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=page_chrome)])
    doc.build(markdown_to_story(markdown, styles))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
