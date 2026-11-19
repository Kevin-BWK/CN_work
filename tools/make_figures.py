"""Generate architecture/flow figures for the course report.

Outputs PNG (for the DOCX) and .drawio (editable source) from one layout
definition, so the report figures and the editable files cannot drift apart.

Run:
    .venv\\Scripts\\python.exe tools\\make_figures.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
SCALE = 2
OUTPUT = Path("docs") / "figures"

TITLE_FILL = "#F8FAFC"
BLUE_FILL = "#EFF6FF"
BLUE_LINE = "#2563EB"
GREEN_FILL = "#F0FDF4"
GREEN_LINE = "#16A34A"
AMBER_FILL = "#FFFBEB"
AMBER_LINE = "#D97706"
GREY_FILL = "#F1F5F9"
GREY_LINE = "#64748B"
RED_FILL = "#FEF2F2"
RED_LINE = "#DC2626"


@dataclass
class Box:
    key: str
    x: float
    y: float
    w: float
    h: float
    text: str
    fill: str = BLUE_FILL
    line: str = BLUE_LINE
    size: int = 18
    bold: bool = False


@dataclass
class Arrow:
    start: tuple[float, float]
    end: tuple[float, float]
    label: str = ""
    dashed: bool = False
    waypoints: list[tuple[float, float]] = field(default_factory=list)


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), "white")
        self.draw = ImageDraw.Draw(self.image)
        self._fonts: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(
                FONT_PATH, size * SCALE, index=0
            )
        return self._fonts[key]

    def text_center(
        self,
        cx: float,
        cy: float,
        text: str,
        size: int = 18,
        bold: bool = False,
        color: str = "#0F172A",
        max_width: float | None = None,
    ) -> None:
        font = self.font(size, bold)
        lines = wrap_text(self.draw, text, font, max_width, SCALE)
        line_height = (size + 7) * SCALE
        total = line_height * len(lines)
        y = cy * SCALE - total / 2
        for line in lines:
            width = self.draw.textlength(line, font=font)
            self.draw.text(
                (cx * SCALE - width / 2, y),
                line,
                font=font,
                fill=color,
            )
            y += line_height

    def box(self, box: Box) -> None:
        self.draw.rounded_rectangle(
            (
                box.x * SCALE,
                box.y * SCALE,
                (box.x + box.w) * SCALE,
                (box.y + box.h) * SCALE,
            ),
            radius=10 * SCALE,
            fill=box.fill,
            outline=box.line,
            width=2 * SCALE,
        )
        self.text_center(
            box.x + box.w / 2,
            box.y + box.h / 2,
            box.text,
            size=box.size,
            bold=box.bold,
            max_width=box.w - 16,
        )

    def arrow(self, arrow: Arrow) -> None:
        points = [(arrow.start[0] * SCALE, arrow.start[1] * SCALE)]
        points += [(x * SCALE, y * SCALE) for x, y in arrow.waypoints]
        points.append((arrow.end[0] * SCALE, arrow.end[1] * SCALE))
        color = "#475569"
        for index in range(len(points) - 1):
            self._segment(points[index], points[index + 1], arrow.dashed, color)
        self._head(points[-2], points[-1], color)
        if arrow.label:
            mid_x = (points[0][0] + points[-1][0]) / 2 / SCALE
            mid_y = (points[0][1] + points[-1][1]) / 2 / SCALE
            self._label(mid_x, mid_y, arrow.label)

    def _segment(self, a, b, dashed: bool, color: str) -> None:
        if not dashed:
            self.draw.line([a, b], fill=color, width=2 * SCALE)
            return
        total = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        if total == 0:
            return
        step = 10 * SCALE
        pos = 0.0
        while pos < total:
            end = min(pos + step * 0.6, total)
            start_pt = (
                a[0] + (b[0] - a[0]) * pos / total,
                a[1] + (b[1] - a[1]) * pos / total,
            )
            end_pt = (
                a[0] + (b[0] - a[0]) * end / total,
                a[1] + (b[1] - a[1]) * end / total,
            )
            self.draw.line([start_pt, end_pt], fill=color, width=2 * SCALE)
            pos += step

    def _head(self, a, b, color: str) -> None:
        size = 9 * SCALE
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        left = (
            b[0] - size * math.cos(angle - 0.4),
            b[1] - size * math.sin(angle - 0.4),
        )
        right = (
            b[0] - size * math.cos(angle + 0.4),
            b[1] - size * math.sin(angle + 0.4),
        )
        self.draw.polygon([b, left, right], fill=color)

    def _label(self, cx: float, cy: float, text: str) -> None:
        font = self.font(13)
        width = self.draw.textlength(text, font=font)
        pad = 4 * SCALE
        self.draw.rectangle(
            (
                cx * SCALE - width / 2 - pad,
                cy * SCALE - 9 * SCALE,
                cx * SCALE + width / 2 + pad,
                cy * SCALE + 9 * SCALE,
            ),
            fill="white",
        )
        self.draw.text(
            (cx * SCALE - width / 2, cy * SCALE - 9 * SCALE),
            text,
            font=font,
            fill="#334155",
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(path, "PNG")


def wrap_text(draw, text: str, font, max_width: float | None, scale: int):
    if max_width is None:
        return [text]
    max_px = max_width * scale
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and draw.textlength(candidate, font=font) > max_px:
                lines.append(current)
                current = char
            else:
                current = candidate
        lines.append(current)
    return lines


def bus(start: tuple[float, float], bus_y: float, target_x: float, target_y: float) -> Arrow:
    """Elbow arrow: down from start, across at bus_y, then down into target."""

    return Arrow(
        start,
        (target_x, target_y),
        waypoints=[(start[0], bus_y), (target_x, bus_y)],
    )


# ---------------------------------------------------------------- figures


def figure_architecture() -> tuple[Canvas, list[Box], list[Arrow]]:
    gui = Box(
        "gui", 60, 30, 1380, 70,
        "GUI 层：MainWindow / PacketTableModel / DetailTree / ChartsPanel / SummaryPanel（Qt 主线程）",
        BLUE_FILL, BLUE_LINE, 18, True,
    )
    session = Box("session", 200, 150, 440, 80, "CaptureSession（实时会话编排）\n协调抓包、解析、统计、记录、资源日志", GREEN_FILL, GREEN_LINE, 16, True)
    offline = Box("offline", 860, 150, 440, 80, "analyze_pcapng()（离线分析）\n复用同一解析器与统计器", AMBER_FILL, AMBER_LINE, 16, True)
    capture = Box("capture", 40, 300, 250, 86, "CaptureWorker\nAsyncSniffer + 抓包队列", BLUE_FILL, BLUE_LINE, 15)
    core = Box("core", 320, 300, 280, 86, "解析与统计核心\nparse_packet / StatsAggregator", BLUE_FILL, BLUE_LINE, 15)
    recorder = Box("recorder", 630, 300, 250, 86, "PcapNgRecorder\n分段写入与导出", BLUE_FILL, BLUE_LINE, 15)
    resource = Box("resource", 910, 300, 230, 86, "ResourceLogger\n10 秒资源采样", BLUE_FILL, BLUE_LINE, 15)
    reader = Box("reader", 1170, 300, 260, 86, "read_capture()\n流式回读 pcap/pcapng", BLUE_FILL, BLUE_LINE, 15)
    npcap = Box("npcap", 40, 440, 250, 62, "Npcap 驱动", GREY_FILL, GREY_LINE, 16)
    pcap = Box("pcap", 630, 440, 250, 62, "pcapng 分段 + session.json", GREY_FILL, GREY_LINE, 15)
    csv = Box("csv", 910, 440, 230, 62, "resources.csv", GREY_FILL, GREY_LINE, 16)

    arrows = [
        Arrow((600, 100), (400, 150), label="命令 / 快照"),
        Arrow((900, 100), (1100, 150)),
        bus((420, 230), 262, 165, 300),
        bus((420, 230), 272, 460, 300),
        bus((420, 230), 282, 755, 300),
        bus((420, 230), 292, 1025, 300),
        bus((1080, 230), 266, 520, 300),
        bus((1080, 230), 276, 1300, 300),
        Arrow((165, 386), (165, 440), label="驱动"),
        Arrow((755, 386), (755, 440), label="写入"),
        Arrow((1025, 386), (1025, 440)),
        Arrow((1230, 386), (1230, 440), label="读取", dashed=True),
    ]
    canvas = Canvas(1500, 540)
    return canvas, [gui, session, offline, capture, core, recorder, resource, reader, npcap, pcap, csv], arrows


def figure_pipeline() -> tuple[Canvas, list[Box], list[Arrow]]:
    boxes = [
        Box("nic", 30, 90, 170, 84, "网卡 / Npcap", GREY_FILL, GREY_LINE, 16, True),
        Box("sniffer", 240, 90, 230, 84, "抓包线程\nAsyncSniffer(store=False)", BLUE_FILL, BLUE_LINE, 15),
        Box("q1", 510, 90, 160, 84, "抓包队列\n50 000 条", AMBER_FILL, AMBER_LINE, 15),
        Box("proc", 710, 90, 240, 84, "处理线程\n解析 → 统计 → 最近记录", GREEN_FILL, GREEN_LINE, 15),
        Box("q2", 990, 90, 160, 84, "记录队列\n10 000 条", AMBER_FILL, AMBER_LINE, 15),
        Box("writer", 1190, 90, 230, 84, "记录线程\nPcapNgRecorder", BLUE_FILL, BLUE_LINE, 15),
        Box("qt", 710, 250, 240, 80, "Qt 主线程\n每 250 ms 取快照刷新", BLUE_FILL, BLUE_LINE, 15),
        Box("pcap", 1190, 250, 230, 70, "pcapng 分段\n256 MiB/段", GREY_FILL, GREY_LINE, 15),
        Box("meta", 990, 250, 160, 70, "session.json", GREY_FILL, GREY_LINE, 15),
        Box("monitor", 30, 250, 300, 80, "资源线程（10 秒）\nCPU / RSS / 磁盘 / 会话计数", BLUE_FILL, BLUE_LINE, 14),
        Box("csv", 370, 250, 160, 70, "resources.csv", GREY_FILL, GREY_LINE, 15),
    ]
    arrows = [
        Arrow((200, 132), (240, 132)),
        Arrow((470, 132), (510, 132)),
        Arrow((670, 132), (710, 132)),
        Arrow((950, 132), (990, 132)),
        Arrow((1150, 132), (1190, 132)),
        Arrow((830, 174), (830, 250), label="快照"),
        Arrow((1305, 174), (1305, 250)),
        Arrow((1210, 174), (1070, 250), waypoints=[(1210, 214), (1070, 214)], label="停止时写入", dashed=True),
        Arrow((330, 290), (370, 290)),
    ]
    canvas = Canvas(1460, 380)
    return canvas, boxes, arrows


def figure_lifecycle() -> tuple[Canvas, list[Box], list[Arrow]]:
    boxes = [
        Box("idle", 30, 60, 160, 64, "未启动", GREY_FILL, GREY_LINE, 17, True),
        Box("start", 240, 50, 220, 84, "启动\n记录器 + 日志 + 处理线程\n + 抓包", BLUE_FILL, BLUE_LINE, 14),
        Box("run", 510, 60, 190, 64, "运行中\nrunning=True", GREEN_FILL, GREEN_LINE, 17, True),
        Box("stop", 750, 50, 220, 84, "停止\n停抓包 → 哨兵(5 s)\n → join(15 s) → 关文件", AMBER_FILL, AMBER_LINE, 14),
        Box("done", 1020, 60, 170, 64, "已停止\nrunning=False", GREY_FILL, GREY_LINE, 17, True),
        Box("proc_err", 460, 250, 250, 92, "处理线程异常\nrunning=False\n写入 last_error", RED_FILL, RED_LINE, 14),
        Box("rec_err", 760, 250, 260, 92, "记录失败 / 磁盘不足\n停止记录、关闭文件\n统计继续", RED_FILL, RED_LINE, 14),
        Box("timeout", 1070, 250, 240, 92, "线程超时未停\n保留文件不关闭\n记录错误", RED_FILL, RED_LINE, 14),
    ]
    arrows = [
        Arrow((190, 92), (240, 92)),
        Arrow((460, 92), (510, 92)),
        Arrow((700, 92), (750, 92)),
        Arrow((970, 92), (1020, 92)),
        Arrow((605, 124), (585, 250), label="未捕获异常"),
        Arrow((860, 134), (890, 250), label="写入失败"),
        Arrow((950, 134), (1170, 250), waypoints=[(950, 205), (1190, 205), (1190, 250)], dashed=True, label="超时"),
    ]
    canvas = Canvas(1340, 380)
    return canvas, boxes, arrows


def figure_replay() -> tuple[Canvas, list[Box], list[Arrow]]:
    boxes = [
        Box("file", 30, 60, 200, 80, "pcapng 文件\n（单文件或分段）", GREY_FILL, GREY_LINE, 15, True),
        Box("read", 290, 60, 230, 80, "read_capture()\nScapy 读取器，逐条产出", BLUE_FILL, BLUE_LINE, 14),
        Box("parse", 580, 60, 220, 80, "parse_packet()\n与实时同一套解析", BLUE_FILL, BLUE_LINE, 14),
        Box("stats", 860, 60, 220, 80, "StatsAggregator\n累计统计", GREEN_FILL, GREEN_LINE, 14),
        Box("ui", 1140, 60, 250, 80, "MainWindow\n表格 · 详情 · 图表", BLUE_FILL, BLUE_LINE, 14),
        Box("export", 290, 240, 230, 80, "导出单文件\n多分段流式合并", AMBER_FILL, AMBER_LINE, 14),
        Box("tmp", 580, 240, 220, 80, "临时文件\n写完再替换目标", AMBER_FILL, AMBER_LINE, 14),
        Box("out", 860, 240, 220, 80, "目标 pcapng", GREY_FILL, GREY_LINE, 15),
        Box("note", 30, 250, 220, 80, "说明\n打开 / 导出均在后台线程\n带进度框，打开可取消", TITLE_FILL, GREY_LINE, 12),
    ]
    arrows = [
        Arrow((230, 100), (290, 100)),
        Arrow((520, 100), (580, 100)),
        Arrow((800, 100), (860, 100)),
        Arrow((1080, 100), (1140, 100)),
        Arrow((410, 240), (410, 140), label="逐段读取"),
        Arrow((520, 280), (580, 280)),
        Arrow((800, 280), (860, 280)),
    ]
    canvas = Canvas(1430, 380)
    return canvas, boxes, arrows


# ---------------------------------------------------------------- drawio

BOX_STYLE = "rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={line};fontSize=12;"


def write_drawio(path: Path, name: str, boxes: list[Box], arrows: list[Arrow], width: int, height: int) -> None:
    cells = []
    for box in boxes:
        cells.append(
            f'<mxCell id="{box.key}" value="{escape(box.text)}" '
            f'style="{BOX_STYLE.format(fill=box.fill, line=box.line)}" vertex="1" parent="1">'
            f'<mxGeometry x="{box.x}" y="{box.y}" width="{box.w}" height="{box.h}" as="geometry"/></mxCell>'
        )
    for index, arrow in enumerate(arrows):
        start = box_key_at(boxes, arrow.start)
        end = box_key_at(boxes, arrow.end)
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;"
            "strokeColor=#475569;fontSize=11;"
            + ("dashed=1;" if arrow.dashed else "")
        )
        if start and end:
            cells.append(
                f'<mxCell id="e{index}" value="{escape(arrow.label)}" style="{style}" edge="1" parent="1" '
                f'source="{start}" target="{end}"><mxGeometry relative="1" as="geometry"/></mxCell>'
            )
        else:
            points = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in arrow.waypoints)
            cells.append(
                f'<mxCell id="e{index}" value="{escape(arrow.label)}" style="{style}" edge="1" parent="1">'
                '<mxGeometry relative="1" as="geometry">'
                f'<mxPoint x="{arrow.start[0]}" y="{arrow.start[1]}" as="sourcePoint"/>'
                f'<mxPoint x="{arrow.end[0]}" y="{arrow.end[1]}" as="targetPoint"/>'
                f'{"<Array as=\"points\">" + points + "</Array>" if points else ""}'
                '</mxGeometry></mxCell>'
            )
    xml = (
        '<mxfile host="drawio"><diagram id="d1" name="'
        + escape(name)
        + '"><mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{width}" pageHeight="{height}" math="0" shadow="0"><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )
    path.write_text(xml, encoding="utf-8")


def box_key_at(boxes: list[Box], point: tuple[float, float]) -> str | None:
    for box in boxes:
        if (
            box.x - 2 <= point[0] <= box.x + box.w + 2
            and box.y - 2 <= point[1] <= box.y + box.h + 2
        ):
            return box.key
    return None


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    figures = [
        ("fig1_architecture", figure_architecture, "系统结构图"),
        ("fig2_pipeline", figure_pipeline, "实时抓包数据流"),
        ("fig3_lifecycle", figure_lifecycle, "会话生命周期与故障分支"),
        ("fig4_replay", figure_replay, "回读与导出流程"),
    ]
    for name, factory, title in figures:
        canvas, boxes, arrows = factory()
        for box in boxes:
            canvas.box(box)
        for arrow in arrows:
            canvas.arrow(arrow)
        canvas.save(OUTPUT / f"{name}.png")
        write_drawio(
            OUTPUT / f"{name}.drawio",
            title,
            boxes,
            arrows,
            canvas.width,
            canvas.height,
        )
        print(OUTPUT / f"{name}.png")


if __name__ == "__main__":
    main()
