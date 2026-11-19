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
OUTPUT = ROOT / "docs" / "FlowLens答辩.pptx"

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
    add_textbox(slide, Inches(0.95), Inches(5.6), Inches(11.5), Inches(0.5), "A　B　C　D", 16, False, WHITE)
    add_textbox(slide, Inches(0.95), Inches(6.1), Inches(11.5), Inches(0.5), "2026 年 11 月", 14, False, RGBColor(0x94, 0xA3, 0xB8))


def section_slide(prs, number: int, index: str, title: str) -> None:
    slide = blank_slide(prs)
    add_rect(slide, 0, 0, Inches(0.28), HEIGHT, BLUE)
    add_textbox(slide, Inches(1.0), Inches(2.6), Inches(2.0), Inches(1.0), index, 60, True, RGBColor(0xDB, 0xEA, 0xFE))
    add_textbox(slide, Inches(1.0), Inches(3.5), Inches(10.5), Inches(1.0), title, 36, True, NAVY)
    footer(slide, len(prs.slides))


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


def build() -> None:
    prs = Presentation()
    prs.slide_width = WIDTH
    prs.slide_height = HEIGHT

    title_slide(prs, 1)
    bullets_slide(
        prs,
        2,
        "汇报内容",
        [
            ("一、主要工作内容", "需求与边界 → 架构 → 解析统计 → 记录回读 → 界面 → 验证与交付"),
            ("二、关键问题与解决方案", "四类故障路径：定位、修复、回归验证"),
            ("三、设计亮点", "同源口径、故障可降级、证据链、资源有界"),
            ("四、结论与达成情况", "逐项对照课程要求与支持边界"),
        ],
    )

    section_slide(prs, 2, "01", "背景与目标")
    bullets_slide(
        prs,
        3,
        "课程要求与设计取舍",
        [
            ("必须完成", "GUI、三层字段、长度频次折线图、长度分段柱状图、IPv4/IPv6/其它柱状图、原始数据保存与回读、连续运行一天并分析资源"),
            ("技术路线", "Python + Npcap/Scapy 抓包解析，PySide6 桌面，pyqtgraph 绘图，pcapng 持久化，PyInstaller 打包"),
            ("明确边界", "面向 Ethernet II 单层 VLAN；非首片不取端口；不做流重组；异常检测列为可选扩展"),
        ],
    )

    section_slide(prs, 4, "02", "主要工作与系统设计")
    bullets_slide(
        prs,
        10,
        "主要工作（一）：设计与实现",
        [
            ("需求与边界", "字段口径与长度分桶歧义处理；明确 Ethernet II、单层 VLAN、不重组等支持范围"),
            ("架构与线程", "单进程多线程：抓包队列、处理线程、记录队列、GUI 快照；离线复用同一解析/统计"),
            ("协议解析", "Ethernet/VLAN、IPv4/IPv6、TCP/UDP、分片、隧道、IPv6 扩展头、802.3 兼容"),
            ("统计口径", "IP 长度频次、三段分桶、IPv4/IPv6/其它分类、5 秒速率，实时与回读一致"),
        ],
    )
    bullets_slide(
        prs,
        11,
        "主要工作（二）：可靠性、验证与交付",
        [
            ("持久化", "pcapng 分段写入、单文件导出合并、流式回读、磁盘余量保护"),
            ("界面", "报文表、字段详情、会话概览、三张图；增量刷新与后台打开/导出"),
            ("可靠性与故障处理", "解析异常隔离、停止有界、记录失败降级、会话健康可见"),
            ("验证与交付", "35 项自动化测试、打包自检、云主机 24.52 小时长稳、报告/手册/PPT/提交包"),
        ],
    )

    image_slide(prs, 5, "系统总体结构", FIGURES / "fig1_architecture.png", "图 1　系统结构：UI 与纯 Python 核心分离，实时与离线共用解析/统计")
    image_slide(prs, 6, "数据流与线程模型", FIGURES / "fig2_pipeline.png", "图 2　Npcap → 抓包线程 → 队列 → 处理线程 → 记录线程；GUI 250 ms 轮询快照")
    image_slide(prs, 7, "系统运行界面", FIGURES / "ui_live.png", "长稳运行中的主窗口：报文表、字段详情、会话概览与三类图表")

    table_slide(
        prs,
        8,
        "字段与统计口径",
        ["项目", "口径", "说明"],
        [
            ["IPv4 / IPv6 长度", "首部总长度 / 40 + Payload Length", "非 IP 数据不进入长度统计"],
            ["长度分桶", "<=46 / 47–1499 / >=1500", "三段互斥，边界有测试"],
            ["分类", "解析后的 IPv4 / IPv6 / 其它", "ARP、STP 等计入其它"],
            ["速率", "最近 5 个整秒桶 ÷ 5", "不是链路带宽"],
            ["协议号", "IPv4 proto；IPv6 有 TCP/UDP 取最终协议", "否则取基础 Next Header"],
        ],
        widths=[0.22, 0.36, 0.42],
    )

    section_slide(prs, 8, "03", "可靠性与故障处理")
    image_slide(prs, 9, "会话生命周期与故障分支", FIGURES / "fig3_lifecycle.png", "图 3　停止有界、记录失败降级、线程异常不再伪装运行")
    table_slide(
        prs,
        10,
        "关键问题与解决方案（一）",
        ["问题", "定位", "解决", "验证"],
        [
            ["802.3/STP 帧让处理线程退出", "解析器读取不存在的 type", "标记“不支持类型”+ 处理循环兜底", "2 项测试"],
            ["记录失败后停止无限阻塞", "满队列 + 无超时哨兵", "记录降级；哨兵 5 s / join 15 s", "1 项测试"],
            ["磁盘写满无保护", "只写不检查余量", "2 GiB 阈值停记录、统计继续", "3 项测试"],
        ],
        widths=[0.30, 0.24, 0.30, 0.16],
    )
    table_slide(
        prs,
        11,
        "关键问题与解决方案（二）",
        ["问题", "定位", "解决", "验证"],
        [
            ["满缓存表格重置、打开阻塞", "全量重置；主线程同步 IO", "滑动窗口 + 按序号恢复；后台线程", "测试 + 冒烟"],
            ["线上长度 / 隧道端口 / IPv6 口径", "未传 wirelen；getlayer 穿透隧道", "透传长度；只取外层；统一协议号", "3 项测试"],
            ["首次长稳被欠费停机中断", "云账号余额不足", "结清欠费；改计划任务正常停止后重跑", "24.52 h 达标"],
        ],
        widths=[0.30, 0.24, 0.30, 0.16],
    )

    section_slide(prs, 11, "04", "验证与结论")
    bullets_slide(
        prs,
        12,
        "测试体系与覆盖",
        [
            ("新增故障路径", "802.3 帧、满队列停止、磁盘不足、导出空间、低磁盘降级"),
            ("协议矩阵", "ARP、ICMP、ICMPv6、TCP 标志、UDP、IPv6 扩展头、双层 VLAN、分片"),
            ("数据一致性", "多分段导出回读数量一致；实时统计与回读统计对齐"),
        ],
    )
    image_slide(prs, 13, "长稳资源曲线（24.52 小时）", FIGURES / "fig5_soak.png", "图 5　CPU、RSS、累计报文与磁盘剩余（10 秒采样）")
    table_slide(
        prs,
        14,
        "长稳验收结论",
        ["指标", "结果"],
        [
            ["开始 / 结束", "11-17 21:33 / 11-18 22:04"],
            ["连续运行时长", "24.52 小时（88,275 秒）"],
            ["捕获报文 / 解析错误", "418,745 / 0"],
            ["丢弃（应用队列）", "0"],
            ["CPU 均值 / 峰值", "10.0% / 103.7%"],
            ["内存峰值 / 结束", "251.2 MB / 250.4 MB"],
        ],
        widths=[0.42, 0.58],
    )

    bullets_slide(
        prs,
        19,
        "设计亮点",
        [
            ("同一套口径", "实时与回读共用 parse_packet / StatsAggregator，统计不会出现两套标准"),
            ("故障可降级", "线程健康可见、停止有界、记录失败转为“继续统计并提示”"),
            ("证据链完整", "35 项测试 + 打包自检 + 24.52 小时长稳 + 回读一致性校验七项全 PASS"),
            ("资源有界", "定长队列与最近缓存；长稳 RSS 稳定在 250 MB 附近，无增长趋势"),
        ],
    )
    table_slide(
        prs,
        20,
        "结论：课程要求达成情况",
        ["课程要求", "完成情况", "证据"],
        [
            ["GUI + 链路/网络/传输三层字段", "完成", "界面截图、字段与协议矩阵测试"],
            ["长度频次折线图 + 分段柱状图 + 版本柱状图", "完成", "三张图随抓包刷新、46/47/1499/1500 边界测试"],
            ["原始数据保存并可回读", "完成", "pcapng 分段、单文件导出、回读 418,745 与实时一致"],
            ["连续运行 1 天以上并分析资源", "完成", "24.52 小时、418,745 包、0 错误 0 丢弃、资源曲线"],
            ["文档、图与提交包", "完成（提交前转 RAR）", "报告、使用手册、PPT、DOC/SRC/BIN"],
        ],
        widths=[0.42, 0.22, 0.36],
    )

    section_slide(prs, 14, "05", "交付与总结")
    image_slide(prs, 15, "回读与导出", FIGURES / "fig4_replay.png", "图 4　离线分析复用同一解析器；打开/导出在后台线程执行")
    bullets_slide(
        prs,
        16,
        "交付物与后续工作",
        [
            ("交付", "源码、打包程序 FlowLens.exe、报告、使用手册、PPT、DOC/SRC/BIN"),
            ("已知不足", "IPv6 实机样本少；只支持 Ethernet II；未实现异常检测"),
            ("后续可做", "异常流量提示、多网卡并行、TCP 流重组"),
        ],
    )
    slide = blank_slide(prs)
    add_rect(slide, 0, 0, WIDTH, HEIGHT, NAVY)
    add_textbox(slide, Inches(0.9), Inches(2.7), Inches(11.5), Inches(1.0), "汇报结束，敬请指正", 40, True, WHITE)
    add_textbox(slide, Inches(0.95), Inches(4.0), Inches(11.5), Inches(0.6), "现场演示：选网卡 → 抓包 → 查看字段 → 停止 → 保存 → 回读", 18, False, RGBColor(0xBF, 0xDB, 0xFE))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
