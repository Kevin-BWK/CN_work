"""Run the capture pipeline for a long, continuous soak test.

Example:
    .venv\\Scripts\\python.exe tools\\soak_test.py --hours 24 --interface WLAN
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packet_analyzer.capture import discover_interfaces
from packet_analyzer.session import CaptureSession, analyze_pcapng


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--interface", default="WLAN")
    parser.add_argument("--filter", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--status-interval", type=float, default=300.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    interfaces = discover_interfaces()
    interface = next(
        (item for item in interfaces if item.name == args.interface),
        None,
    )
    if interface is None:
        names = ", ".join(item.name for item in interfaces)
        raise SystemExit(f"Interface {args.interface!r} not found. Available: {names}")

    output = args.output or (
        Path("data") / "soak" / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    duration = max(1.0, args.hours * 3600)
    session = CaptureSession()
    started = time.monotonic()
    print(f"interface: {interface.name} ({interface.description})")
    print(f"output: {output.resolve()}")
    print(f"duration: {duration / 3600:.2f} hours")

    session.start(interface, bpf_filter=args.filter, record_dir=output)
    summary: dict[str, object] = {}
    try:
        next_status = started + min(args.status_interval, duration)
        while time.monotonic() - started < duration:
            time.sleep(min(5.0, max(0.2, duration - (time.monotonic() - started))))
            now = time.monotonic()
            if now >= next_status:
                snapshot = session.snapshot(recent_limit=0)
                print(
                    f"[{now - started:8.1f}s] packets={snapshot.stats.total_packets} "
                    f"errors={snapshot.stats.parse_errors} "
                    f"queue={snapshot.queue_depth} "
                    f"drops={snapshot.queue_dropped + snapshot.record_dropped}"
                )
                next_status = now + args.status_interval
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        session.stop()

    snapshot = session.snapshot(recent_limit=0)
    if snapshot.segments:
        exported = session.export_recording(output / "session.pcapng")
        loaded, _ = analyze_pcapng(exported)
        summary = {
            "duration_seconds": snapshot.uptime_seconds,
            "live_total": snapshot.stats.total_packets,
            "loaded_total": loaded.total_packets,
            "ipv4": loaded.ipv4_packets,
            "ipv6": loaded.ipv6_packets,
            "other": loaded.other_packets,
            "parse_errors": loaded.parse_errors,
            "queue_dropped": snapshot.queue_dropped,
            "record_dropped": snapshot.record_dropped,
        }
    else:
        summary = {"duration_seconds": snapshot.uptime_seconds}

    summary_path = output / "soak_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
