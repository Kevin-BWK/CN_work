"""Validate a soak session directory and print a pass/fail summary.

Usage:
    .venv\\Scripts\\python.exe tools\\verify_soak_evidence.py data\\sessions\\20261116_152631

Checks: duration, log continuity, parsing errors, queue drops, and whether the
saved pcapng contains the same number of packets as the live statistics.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packet_analyzer.session import analyze_pcapng


def read_samples(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                rows.append(
                    {
                        "uptime": float(row["uptime_seconds"]),
                        "captured": int(row["captured"]),
                        "errors": int(row["parse_errors"]),
                        "dropped": int(row["queue_dropped"]) + int(row["record_dropped"]),
                        "disk_free": float(row["disk_free_mb"]),
                        "rss": float(row["rss_mb"]),
                        "cpu": float(row["cpu_percent"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--min-hours", type=float, default=24.0)
    parser.add_argument("--max-gap", type=float, default=120.0)
    args = parser.parse_args()

    session = args.session
    samples = read_samples(session / "resources.csv")
    if not samples:
        print("FAIL: resources.csv 没有有效采样")
        return 2

    duration_hours = (samples[-1]["uptime"] - samples[0]["uptime"]) / 3600
    gaps = [
        current["uptime"] - previous["uptime"]
        for previous, current in zip(samples, samples[1:])
    ]
    max_gap = max(gaps) if gaps else 0.0
    errors = samples[-1]["errors"]
    dropped = samples[-1]["dropped"]
    captured = samples[-1]["captured"]

    metadata = {}
    meta_path = session / "session.json"
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    segments = sorted(session.glob("*.pcapng"))
    readback = 0
    readback_errors = 0
    for segment in segments:
        stats, _ = analyze_pcapng(segment)
        readback += stats.total_packets
        readback_errors += stats.parse_errors

    checks = [
        ("时长 >= 24 小时", duration_hours >= args.min_hours),
        ("无解析错误", errors == 0 and readback_errors == 0),
        ("无应用队列丢弃", dropped == 0),
        ("采样间隔连续", max_gap <= args.max_gap),
        ("回读数量与实时一致", readback == captured - dropped),
        ("存在 pcapng 分段", len(segments) > 0),
        ("存在 session.json", bool(metadata)),
    ]

    print(f"session      : {session}")
    print(f"samples      : {len(samples)}")
    print(f"duration     : {duration_hours:.2f} h")
    print(f"max gap      : {max_gap:.1f} s")
    print(f"captured     : {captured}")
    print(f"parse errors : {errors}")
    print(f"dropped      : {dropped}")
    print(f"readback     : {readback}")
    print(f"segments     : {len(segments)}")
    print(
        "start/stop   : "
        f"{metadata.get('started_at')} -> {metadata.get('stopped_at')}"
    )
    print("")
    failed = 0
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
