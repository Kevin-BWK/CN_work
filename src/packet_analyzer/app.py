"""Application entry point."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


def _run_self_test() -> int:
    from packet_analyzer.capture import discover_interfaces
    from packet_analyzer.session import CaptureSession

    boot_log = Path("data") / "boot.log"
    boot_log.parent.mkdir(parents=True, exist_ok=True)
    boot_log.write_text(
        json.dumps(
            {
                "argv": sys.argv,
                "cwd": str(Path.cwd()),
                "self_test_env": os.environ.get("PACKET_ANALYZER_SELF_TEST"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    interfaces = discover_interfaces()
    interface = next(
        (item for item in interfaces if item.name == "WLAN" and item.is_up),
        next((item for item in interfaces if item.is_up and item.addresses), None),
    )
    output = Path("data") / "self_test.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if interface is None:
        output.write_text(
            json.dumps({"ok": False, "error": "no interface"}, ensure_ascii=False),
            encoding="utf-8",
        )
        return 2

    session = CaptureSession()
    try:
        session.start(interface, record_dir=None)
        time.sleep(3)
    finally:
        session.stop()
    snapshot = session.snapshot(recent_limit=0)
    result = {
        "ok": snapshot.stats.total_packets > 0,
        "interface": interface.name,
        "packets": snapshot.stats.total_packets,
        "parse_errors": snapshot.stats.parse_errors,
        "argv": sys.argv,
        "cwd": str(Path.cwd()),
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if result["ok"] else 3


def main() -> int:
    if (
        "--self-test" in sys.argv
        or os.environ.get("PACKET_ANALYZER_SELF_TEST") == "1"
    ):
        return _run_self_test()

    from PySide6.QtWidgets import QApplication

    from packet_analyzer.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("网络流量分析系统")
    app.setOrganizationName("Computer Networks Course Design")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
