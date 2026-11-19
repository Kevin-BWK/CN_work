"""Build the user manual DOCX from docs/manual.md."""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_report import (  # noqa: E402
    BODY_FONT,
    HEAD_FONT,
    add_page_number_footer,
    build_body,
    set_run_font,
)

DOC = ROOT / "docs" / "manual.md"
OUTPUT = ROOT / "docs" / "FlowLens使用手册.docx"


def main() -> None:
    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    title = document.add_paragraph()
    run = title.add_run("FlowLens 流镜 · 使用手册")
    set_run_font(run, HEAD_FONT, 24, bold=True)
    note = document.add_paragraph()
    run = note.add_run("适用于 FlowLens 1.0（2026-11）")
    set_run_font(run, BODY_FONT, 11)
    document.add_page_break()

    build_body(document, DOC.read_text(encoding="utf-8"), DOC.parent)
    add_page_number_footer(document)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
