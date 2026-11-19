"""Build the course report DOCX from docs/report_draft.md.

The Markdown subset supported here is deliberately small: headings, paragraphs,
bullet/numbered lists, pipe tables, fenced code blocks, images with captions and
**bold** / `code` inline spans.

Run:
    python tools/build_report.py
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "docs" / "report_draft.md"
OUTPUT = ROOT / "docs" / "FlowLens课程设计报告.docx"

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
CODE_FONT = "Consolas"

MEMBERS = [
    ("A", "2024****", "组长", "总体方案、解析与会话管线、集成与验收", "25%"),
    ("B", "2024****", "组员", "字段语义、报文表、详情与图表", "25%"),
    ("C", "2024****", "组员", "统计口径、pcapng 与资源日志", "25%"),
    ("D", "2024****", "组员", "协议测试、长稳与测试记录", "25%"),
]


def set_run_font(run, name: str, size: float, bold: bool = False, color=None) -> None:
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name if name != BODY_FONT else "Times New Roman")
    rfonts.set(qn("w:hAnsi"), name if name != BODY_FONT else "Times New Roman")


def style_paragraph(paragraph, font=BODY_FONT, size=12, bold=False, align=None):
    if align is not None:
        paragraph.alignment = align
    for run in paragraph.runs:
        set_run_font(run, font, size, bold)
    return paragraph


def add_heading(document, text: str, level: int) -> None:
    sizes = {1: 16, 2: 14, 3: 12.5}
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    # Keep headings discoverable by Word's navigation pane / TOC.
    paragraph.style = document.styles[f"Heading {min(level, 4)}"]
    for run in paragraph.runs:
        set_run_font(
            run,
            HEAD_FONT,
            sizes.get(level, 12),
            bold=True,
            color=RGBColor(0, 0, 0),
        )


def add_page_number_footer(document) -> None:
    section = document.sections[0]
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def build_cover(document) -> None:
    for _ in range(2):
        document.add_paragraph()
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("FlowLens 流镜")
    set_run_font(run, HEAD_FONT, 30, bold=True)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("网络流量分析系统")
    set_run_font(run, HEAD_FONT, 20, bold=True)

    line = document.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = line.add_run("《计算机网络》课程设计报告")
    set_run_font(run, HEAD_FONT, 16)

    info = [
        ("课程名称", "计算机网络"),
        ("设计题目", "FlowLens 流镜——网络流量分析系统"),
        ("选题方向", "2 网络流量分析系统"),
        ("专业班级", "网络工程"),
        ("组别", "第19组"),
        ("指导教师", "袁华"),
    ]
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for key, value in info:
        row = table.add_row()
        row.cells[0].text = key
        row.cells[1].text = value
        row.cells[0].width = Cm(3.6)
        row.cells[1].width = Cm(12.4)
        for cell, bold in ((row.cells[0], True), (row.cells[1], False)):
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    set_run_font(run, BODY_FONT, 11, bold)

    document.add_paragraph()

    members = document.add_table(rows=1, cols=5)
    members.style = "Table Grid"
    members.alignment = WD_TABLE_ALIGNMENT.CENTER
    members.autofit = False
    header = ["姓名", "学号", "角色", "主要分工", "工作量"]
    widths = [Cm(2.1), Cm(2.9), Cm(1.2), Cm(6.6), Cm(1.6)]
    for index, text in enumerate(header):
        cell = members.rows[0].cells[index]
        cell.text = text
        cell.width = widths[index]
        for paragraph in cell.paragraphs:
            paragraph.paragraph_format.space_after = Pt(1)
            for run in paragraph.runs:
                set_run_font(run, BODY_FONT, 10, True)
    for member in MEMBERS:
        row = members.add_row()
        for index, text in enumerate(member):
            row.cells[index].text = text
            row.cells[index].width = widths[index]
            for paragraph in row.cells[index].paragraphs:
                paragraph.paragraph_format.space_after = Pt(1)
                for run in paragraph.runs:
                    set_run_font(run, BODY_FONT, 9.5)

    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.space_before = Pt(18)
    run = note.add_run("2026 年 11 月")
    set_run_font(run, BODY_FONT, 14)
    document.add_page_break()


def add_inline(paragraph, text: str, size: float = 12) -> None:
    parts = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, BODY_FONT, size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            set_run_font(run, CODE_FONT, size - 1.5, color=RGBColor(0x9C, 0x27, 0x27))
        else:
            run = paragraph.add_run(part)
            set_run_font(run, BODY_FONT, size)


def keep_table_rows_together(table) -> None:
    for row_index, row in enumerate(table.rows):
        trpr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        trpr.append(cant_split)
        if row_index == 0:
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            trpr.append(header)


def table_widths(rows: list[list[str]], total_cm: float = 15.6) -> list[float]:
    columns = max(len(row) for row in rows)
    lengths = []
    for index in range(columns):
        values = [row[index] for row in rows[1:] if index < len(row)]
        average = sum(len(value) for value in values) / max(1, len(values))
        lengths.append(max(average, 4.0))
    total = sum(lengths)
    widths = [max(1.8, total_cm * length / total) for length in lengths]
    scale = total_cm / sum(widths)
    return [width * scale for width in widths]


def add_table(document, rows: list[list[str]], caption: str = "") -> None:
    if not rows:
        return
    if caption:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(4)
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run(caption)
        set_run_font(run, BODY_FONT, 10, bold=True)

    width = max(len(row) for row in rows)
    table = document.add_table(rows=0, cols=width)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    widths = table_widths(rows)
    for index, column_width in enumerate(widths):
        table.columns[index].width = Cm(column_width)
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for index in range(width):
            text = row[index] if index < len(row) else ""
            text = text.replace("`", "").replace("**", "")
            cells[index].text = text
            cells[index].width = Cm(widths[index])
            for paragraph in cells[index].paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    set_run_font(run, BODY_FONT, 10, bold=(row_index == 0))
    keep_table_rows_together(table)
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def add_code(document, code: str) -> None:
    for line in code.splitlines():
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.left_indent = Cm(0.6)
        run = paragraph.add_run(line if line else " ")
        set_run_font(run, CODE_FONT, 9)
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:fill"), "F1F5F9")
        paragraph._p.get_or_add_pPr().append(shading)


def add_picture(document, alt: str, target: Path) -> None:
    if not target.exists():
        raise FileNotFoundError(target)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(target), width=Cm(16))
    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = caption.add_run(alt)
    set_run_font(run, BODY_FONT, 10, color=RGBColor(0x47, 0x55, 0x69))


def build_body(document, markdown: str, base: Path) -> None:
    lines = markdown.splitlines()
    index = 0
    first_heading = True
    pending_caption = ""
    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1
            add_code(document, "\n".join(code_lines))
            continue

        image = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
        if image:
            caption, relative = image.group(1), image.group(2)
            add_picture(document, caption, base / relative)
            index += 1
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            if level == 1 and not first_heading:
                document.add_page_break()
            first_heading = False
            add_heading(document, text, level)
            index += 1
            continue

        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = lines[index].strip().strip("|")
                cells = [cell.strip() for cell in row.split("|")]
                if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    index += 1
                    continue
                rows.append(cells)
                index += 1
            add_table(document, rows, pending_caption)
            pending_caption = ""
            continue

        if stripped.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            add_inline(paragraph, stripped[2:].strip())
            index += 1
            continue

        if re.match(r"^\d+\.\s", stripped):
            paragraph = document.add_paragraph(style="List Number")
            add_inline(paragraph, re.sub(r"^\d+\.\s", "", stripped))
            index += 1
            continue

        if stripped.startswith(">"):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.8)
            add_inline(paragraph, stripped.lstrip("> ").strip(), size=11)
            for run in paragraph.runs:
                run.font.italic = True
            index += 1
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if (
                not candidate
                or candidate.startswith(("#", "|", "- ", ">", "```", "!["))
                or re.match(r"^\d+\.\s", candidate)
            ):
                break
            paragraph_lines.append(candidate)
            index += 1
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.first_line_indent = Cm(0.74)
        paragraph.paragraph_format.line_spacing = 1.5
        text = "".join(paragraph_lines)
        add_inline(paragraph, text)

        reference = re.search(r"如表\s*(\d+)\s*所示", text)
        if reference:
            prefix = text[: reference.start()].strip("。；， ")
            prefix = prefix.split("。")[-1]
            pending_caption = (
                f"表 {reference.group(1)}　{prefix}"
                if prefix
                else f"表 {reference.group(1)}"
            )


def main() -> None:
    draft = Path(sys.argv[1]) if len(sys.argv) > 1 else DRAFT
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT

    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    normal = document.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(12)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), BODY_FONT)

    build_cover(document)
    build_body(document, draft.read_text(encoding="utf-8-sig"), draft.parent)
    add_page_number_footer(document)
    document.save(output)
    print(output)


if __name__ == "__main__":
    main()
