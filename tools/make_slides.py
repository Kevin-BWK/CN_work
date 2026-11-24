"""Build the defence slide deck for FlowLens.

Run:
    python tools/make_slides.py
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"
OUTPUT = ROOT / "docs" / "FlowLens展示.pptx"

NAVY = RGBColor(0x0F, 0x17, 0x2A)
SLATE = RGBColor(0x33, 0x41, 0x55)
MUTED = RGBColor(0x64, 0x74, 0x8B)
BLUE = RGBColor(0x25, 0x63, 0xEB)
LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x16, 0xA3, 0x4A)

FONT = "Microsoft YaHei"
WIDTH = Inches(13.333)
HEIGHT = Inches(7.5)


def add_textbox(slide, left, top, width, height, text, size=18, bold=False, color=SLATE, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_rect(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def footer(slide, number: int) -> None:
    add_textbox(slide, Inches(0.6), Inches(7.02), Inches(6), Inches(0.3), "FlowLens 流镜 · 计算机网络课程设计", 10, color=MUTED)
    add_textbox(slide, Inches(12.2), Inches(7.02), Inches(0.6), Inches(0.3), str(number), 10, color=MUTED, align=PP_ALIGN.RIGHT)


def title_slide(prs, number: int) -> None:
    slide = blank_slide(prs)
    add_rect(slide, 0, 0, WIDTH, HEIGHT, NAVY)
    add_textbox(slide, Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.2), "FlowLens 流镜", 54, True, WHITE)
    add_textbox(slide, Inches(0.95), Inches(3.1), Inches(11.5), Inches(0.8), "网络流量分析系统", 30, True, RGBColor(0xBF, 0xDB, 0xFE))
    add_textbox(slide, Inches(0.95), Inches(4.3), Inches(11.5), Inches(0.5), "计算机网络课程设计 · 选题 2", 18, False, RGBColor(0xCB, 0xD5, 0xE1))
    add_textbox(slide, Inches(0.95), Inches(5.6), Inches(11.5), Inches(0.5), "网络工程 第19组", 16, False, WHITE)
    add_textbox(slide, Inches(0.95), Inches(6.1), Inches(11.5), Inches(0.5), "2026 年 11 月", 14, False, RGBColor(0x94, 0xA3, 0xB8))


def content_slide(prs, number: int, title: str):
    slide = blank_slide(prs)
    add_rect(slide, 0, 0, WIDTH, Inches(0.12), BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.35), Inches(12), Inches(0.7), title, 28, True, NAVY)
    add_rect(slide, Inches(0.62), Inches(1.02), Inches(1.1), Inches(0.06), BLUE)
    footer(slide, len(prs.slides))
    return slide


def bullets_slide(prs, number: int, title: str, bullets: list[tuple[str, str]]) -> None:
    slide = content_slide(prs, number, title)
    top = Inches(1.45)
    for head, body in bullets:
        add_textbox(slide, Inches(0.8), top, Inches(0.35), Inches(0.4), "•", 22, True, BLUE)
        add_textbox(slide, Inches(1.15), top, Inches(11.3), Inches(0.4), head, 18, True, NAVY)
        if body:
            add_textbox(slide, Inches(1.15), top + Inches(0.38), Inches(11.3), Inches(0.6), body, 14, False, MUTED)
            top += Inches(1.02)
        else:
            top += Inches(0.55)


def image_slide(prs, number: int, title: str, image: Path, caption: str = "") -> None:
    slide = content_slide(prs, number, title)
    if not image.exists():
        add_textbox(slide, Inches(1), Inches(3), Inches(10), Inches(1), f"缺少图片：{image.name}", 18, color=MUTED)
        return
    from PIL import Image

    with Image.open(image) as handle:
        ratio = handle.height / handle.width
    max_width = Inches(11.9)
    width = max_width
    height = Emu(int(width * ratio))
    if height > Inches(4.9):
        height = Inches(4.9)
        width = Emu(int(height / ratio))
    left = Emu(int((WIDTH - width) / 2))
    slide.shapes.add_picture(str(image), left, Inches(1.45), width=width, height=height)
    if caption:
        add_textbox(slide, Inches(0.8), Inches(6.45), Inches(11.7), Inches(0.4), caption, 13, False, MUTED, PP_ALIGN.CENTER)


def table_slide(prs, number: int, title: str, header: list[str], rows: list[list[str]], widths=None) -> None:
    slide = content_slide(prs, number, title)
    columns = len(header)
    top = Inches(1.5)
    row_height = Inches(0.42)
    left = Inches(0.7)
    total_width = Inches(11.9)
    if widths is None:
        widths = [1.0 / columns] * columns
    table = slide.shapes.add_table(len(rows) + 1, columns, left, top, total_width, row_height * (len(rows) + 1)).table
    for index, width in enumerate(widths):
        table.columns[index].width = Emu(int(total_width * width))
    for column, text in enumerate(header):
        cell = table.cell(0, column)
        cell.text = text
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(13)
                run.font.bold = True
                run.font.name = FONT
                run.font.color.rgb = WHITE
        cell.fill.solid()
        cell.fill.fore_color.rgb = BLUE
    for row_index, row in enumerate(rows, start=1):
        for column, text in enumerate(row):
            cell = table.cell(row_index, column)
            cell.text = text
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(11)
                    run.font.name = FONT
                    run.font.color.rgb = SLATE
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if row_index % 2 else LIGHT


def stats_slide(prs, title: str, items: list[tuple[str, str]]) -> None:
    slide = content_slide(prs, 0, title)
    count = len(items)
    total = Inches(11.9)
    width = Emu(int(total / count))
    for index, (value, label) in enumerate(items):
        left = Inches(0.7) + Emu(int(width * index))
        add_textbox(slide, left, Inches(2.4), width, Inches(1.2), value, 40, True, BLUE, PP_ALIGN.CENTER)
        add_textbox(slide, left, Inches(3.7), width, Inches(0.8), label, 14, False, MUTED, PP_ALIGN.CENTER)


def build() -> None:
    prs = Presentation()
    prs.slide_width = WIDTH
    prs.slide_height = HEIGHT

    title_slide(prs, 1)

    bullets_slide(
        prs,
        2,
        "一页概览",
        [
            ("做什么", "Windows 本机抓包，逐层展示链路层、网络层、传输层字段，统计 IP 长度与协议分类，原始数据可保存、可回读"),
            ("怎么用", "选网卡 → 开始抓包 → 查看报文与字段 → 停止 → 导出/回读；会话数据落在本地 pcapng 与 CSV"),
            ("关键数字", "35 项自动化测试 · 24.52 小时连续运行 · 418,745 个报文 · 0 解析错误 · 0 队列丢弃"),
            ("交付形态", "DOC 报告与手册、SRC 源码与测试、BIN 可直接运行的 one-dir 程序"),
        ],
    )

    image_slide(prs, 3, "系统结构", FIGURES / "fig1_architecture.png", "GUI 与纯 Python 核心分离，实时与离线共用同一套解析/统计")

    image_slide(prs, 4, "实时数据流", FIGURES / "fig2_pipeline.png", "抓包线程 → 队列 → 处理线程 → 记录线程，GUI 每 250 ms 取快照")

    image_slide(prs, 5, "运行界面", FIGURES / "ui_live.png", "报文表、字段详情、会话概览与三类统计图同屏联动")

    table_slide(
        prs,
        6,
        "核心能力",
        ["能力", "实现", "说明"],
        [
            ["三层字段", "Ethernet / IPv4 / IPv6 / TCP / UDP", "VLAN、分片、隧道、802.3 都有明确处理"],
            ["三类统计", "长度频次折线、长度分段柱状、版本分类柱状", "分桶互斥，边界有测试"],
            ["保存与回读", "pcapng 256 MiB 分段、单文件导出、流式回读", "回读计数与实时一致"],
            ["资源记录", "每 10 秒写 CPU / 内存 / 磁盘 / 计数", "长稳数据可追溯"],
        ],
        widths=[0.2, 0.42, 0.38],
    )

    image_slide(prs, 7, "可靠性设计", FIGURES / "fig3_lifecycle.png", "解析异常隔离、停止有界、记录失败降级、磁盘余量保护")

    stats_slide(
        prs,
        "长稳结果",
        [
            ("24.52 h", "连续运行"),
            ("418,745", "捕获报文"),
            ("0", "解析错误"),
            ("0", "队列丢弃"),
        ],
    )
    image_slide(prs, 9, "资源曲线", FIGURES / "fig5_soak.png", "CPU、RSS、累计报文与磁盘剩余（10 秒采样，24.52 小时）")

    stats_slide(
        prs,
        "质量保证",
        [
            ("35", "自动化测试"),
            ("5", "故障注入场景"),
            ("8,819", "资源采样"),
            ("100%", "回读一致"),
        ],
    )

    bullets_slide(
        prs,
        11,
        "交付与边界",
        [
            ("交付物", "设计报告、使用手册、DOC/SRC/BIN 提交包、one-dir 可执行程序"),
            ("支持边界", "面向 Ethernet II 单层 VLAN；不做分片/流重组；IPv6 实机样本较少；异常检测为可选扩展"),
            ("后续可做", "异常流量提示、多网卡并行、TCP 流重组"),
        ],
    )

    slide = blank_slide(prs)
    add_rect(slide, 0, 0, WIDTH, HEIGHT, NAVY)
    add_textbox(slide, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.0), "FlowLens 流镜", 44, True, WHITE)
    add_textbox(slide, Inches(0.95), Inches(3.7), Inches(11.5), Inches(0.6), "网络流量分析系统 · 网络工程 第19组", 20, False, RGBColor(0xBF, 0xDB, 0xFE))
    add_textbox(slide, Inches(0.95), Inches(4.5), Inches(11.5), Inches(0.6), "计算机网络课程设计 · 选题 2 · 2026 年 11 月", 14, False, RGBColor(0x94, 0xA3, 0xB8))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
