"""Summarise a soak run and draw its resource charts.

Reads the newest (or a given) session's resources.csv, writes
docs/figures/fig5_soak.png and build/soak_summary.json.

Run:
    python tools/make_soak_charts.py --session data/sessions/20261116_152631
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
SCALE = 2

PANEL_W, PANEL_H = 620, 330
MARGIN_X, MARGIN_Y = 110, 90
GAP_X, GAP_Y = 80, 95
WIDTH = MARGIN_X * 2 + PANEL_W * 2 + GAP_X
HEIGHT = MARGIN_Y * 2 + PANEL_H * 2 + GAP_Y

NAVY = "#0F172A"
SLATE = "#475569"
GRID = "#E2E8F0"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size * SCALE, index=0)


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    import math

    if high <= low:
        high = low + 1
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = magnitude
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            step = factor * magnitude
            break
    start = math.floor(low / step) * step
    ticks = []
    value = start
    while value <= high + step * 0.5:
        ticks.append(round(value, 6))
        value += step
    return ticks


def draw_panel(draw, origin, title, series, y_label, x_label):
    x0, y0 = origin
    left = x0 * SCALE
    top = y0 * SCALE
    width = PANEL_W * SCALE
    height = PANEL_H * SCALE

    all_x = [x for _, xs, _, _ in series for x in xs]
    all_y = [y for _, _, ys, _ in series for y in ys]
    if not all_x or not all_y:
        return
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    if ymax == ymin:
        ymax = ymin + 1
    pad = (ymax - ymin) * 0.08
    ymin = max(0, ymin - pad) if ymin >= 0 else ymin - pad
    ymax = ymax + pad

    draw.rectangle([left, top, left + width, top + height], fill="white", outline="#CBD5E1", width=SCALE)
    title_font = font(15, True)
    draw.text((left + width / 2 - draw.textlength(title, font=title_font) / 2, top - 34 * SCALE), title, font=title_font, fill=NAVY)

    for tick in nice_ticks(ymin, ymax):
        y = top + height - (tick - ymin) / (ymax - ymin) * height
        draw.line([left, y, left + width, y], fill=GRID, width=SCALE)
        label = f"{tick:g}"
        draw.text((left - 8 * SCALE - draw.textlength(label, font=font(11)), y - 8 * SCALE), label, font=font(11), fill=SLATE)

    x_ticks = nice_ticks(xmin, xmax, 6)
    for tick in x_ticks:
        if tick < xmin or tick > xmax:
            continue
        x = left + (tick - xmin) / (xmax - xmin) * width
        label = f"{tick:g}"
        draw.text((x - draw.textlength(label, font=font(11)) / 2, top + height + 8 * SCALE), label, font=font(11), fill=SLATE)

    for label, xs, ys, color in series:
        points = []
        for x, y in zip(xs, ys):
            px = left + (x - xmin) / (xmax - xmin) * width
            py = top + height - (y - ymin) / (ymax - ymin) * height
            points.append((px, py))
        if len(points) > 1:
            draw.line(points, fill=color, width=2 * SCALE, joint="curve")

    draw.text((left + width / 2 - draw.textlength(x_label, font=font(11)) / 2, top + height + 30 * SCALE), x_label, font=font(11), fill=SLATE)

    legend_x = left + 10 * SCALE
    for label, _, _, color in series:
        draw.rectangle([legend_x, top + 8 * SCALE, legend_x + 18 * SCALE, top + 12 * SCALE], fill=color)
        draw.text((legend_x + 22 * SCALE, top + 2 * SCALE), label, font=font(10), fill=SLATE)
        legend_x += 22 * SCALE + draw.textlength(label, font=font(10)) + 18 * SCALE


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                rows.append(
                    {
                        "uptime": float(row["uptime_seconds"]),
                        "cpu": float(row["cpu_percent"]),
                        "rss": float(row["rss_mb"]),
                        "disk_free": float(row["disk_free_mb"]),
                        "captured": int(row["captured"]),
                        "errors": int(row["parse_errors"]),
                        "dropped": int(row["queue_dropped"]) + int(row["record_dropped"]),
                        "mem": float(row["system_memory_percent"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def summarise(rows: list[dict]) -> dict:
    duration = rows[-1]["uptime"] - rows[0]["uptime"] if len(rows) > 1 else 0.0
    cpu = [row["cpu"] for row in rows]
    rss = [row["rss"] for row in rows]
    disk = [row["disk_free"] for row in rows]
    return {
        "samples": len(rows),
        "duration_hours": round(duration / 3600, 3),
        "packets": rows[-1]["captured"],
        "parse_errors": rows[-1]["errors"],
        "dropped": rows[-1]["dropped"],
        "cpu_avg": round(sum(cpu) / len(cpu), 1),
        "cpu_max": max(cpu),
        "rss_max_mb": max(rss),
        "rss_end_mb": rss[-1],
        "system_memory_max_percent": max(row["mem"] for row in rows),
        "disk_free_min_mb": min(disk),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "figures" / "fig5_soak.png")
    parser.add_argument("--summary", type=Path, default=ROOT / "build" / "soak_summary.json")
    args = parser.parse_args()

    session = args.session
    if session is None:
        sessions = sorted((ROOT / "data" / "sessions").glob("*"))
        session = sessions[-1]
    rows = load_rows(session / "resources.csv")
    if not rows:
        raise SystemExit(f"no samples in {session}")

    summary = summarise(rows)
    summary["session"] = str(session)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    stride = max(1, len(rows) // 600)
    rows = rows[::stride]
    hours = [row["uptime"] / 3600 for row in rows]

    image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), "white")
    draw = ImageDraw.Draw(image)
    panels = [
        ((MARGIN_X, MARGIN_Y), "进程 CPU（%）", [("CPU", hours, [r["cpu"] for r in rows], "#2563EB")], "%", "运行时长（小时）"),
        ((MARGIN_X + PANEL_W + GAP_X, MARGIN_Y), "进程内存（MB）", [("RSS", hours, [r["rss"] for r in rows], "#16A34A")], "MB", "运行时长（小时）"),
        ((MARGIN_X, MARGIN_Y + PANEL_H + GAP_Y), "累计捕获报文数", [("packets", hours, [r["captured"] for r in rows], "#D97706")], "包", "运行时长（小时）"),
        ((MARGIN_X + PANEL_W + GAP_X, MARGIN_Y + PANEL_H + GAP_Y), "磁盘剩余（MB）", [("free", hours, [r["disk_free"] for r in rows], "#64748B")], "MB", "运行时长（小时）"),
    ]
    for origin, title, series, y_label, x_label in panels:
        draw_panel(draw, origin, title, series, y_label, x_label)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, "PNG")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(args.output)


if __name__ == "__main__":
    main()
