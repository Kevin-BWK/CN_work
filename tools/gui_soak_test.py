"""Run the real GUI for a long soak test and keep evidence.

This is an acceptance-test harness, not part of the shipped application. It
opens the normal main window, starts a capture session through the GUI code
path, keeps the event loop running, saves periodic window screenshots and
writes a summary when the run ends.

Example:
    .venv\\Scripts\\python.exe tools\\gui_soak_test.py --hours 24.5
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from packet_analyzer.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=24.5)
    parser.add_argument("--screenshot-interval", type=float, default=1800.0)
    parser.add_argument("--output", type=Path, default=Path("data") / "soak_gui")
    args = parser.parse_args()

    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S")
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "soak_gui.log"

    def log(message: str) -> None:
        line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
        try:
            print(line, flush=True)
        except Exception:
            pass  # pythonw has no console
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    app = QApplication(sys.argv[:1])
    # A modal message box would block an unattended run; turn them into log
    # lines instead of waiting for a click nobody will make.
    QMessageBox.critical = lambda *a, **k: log(f"critical: {a[2:] if len(a) > 2 else a}")
    QMessageBox.warning = lambda *a, **k: log(f"warning: {a[2:] if len(a) > 2 else a}")
    QMessageBox.information = lambda *a, **k: log(
        f"information: {a[2:] if len(a) > 2 else a}"
    )

    window = MainWindow()
    window.show()
    started = time.monotonic()
    started_at = datetime.now()
    log(f"start interface={window.interface_combo.currentText()!r}")
    window.start_capture()

    session = window._session
    if session is None:
        log("start failed: no session")
        return 2

    def take_screenshot() -> None:
        snapshot = session.snapshot(recent_limit=0)
        path = output / f"gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        window.grab().save(str(path))
        log(
            f"shot={path.name} uptime={snapshot.uptime_seconds:.0f}s "
            f"packets={snapshot.stats.total_packets} "
            f"errors={snapshot.stats.parse_errors} "
            f"recording={snapshot.recording} "
            f"drops={snapshot.queue_dropped + snapshot.record_dropped} "
            f"error={snapshot.last_error}"
        )

    screenshot_timer = QTimer()
    screenshot_timer.setInterval(int(args.screenshot_interval * 1000))
    screenshot_timer.timeout.connect(take_screenshot)
    screenshot_timer.start()
    QTimer.singleShot(5000, take_screenshot)

    def finish() -> None:
        window.stop_capture()
        snapshot = session.snapshot(recent_limit=0)
        ended_at = datetime.now()
        summary = {
            "started_at": started_at.isoformat(timespec="seconds"),
            "ended_at": ended_at.isoformat(timespec="seconds"),
            "wall_seconds": (ended_at - started_at).total_seconds(),
            "uptime_seconds": snapshot.uptime_seconds,
            "total_packets": snapshot.stats.total_packets,
            "parsed": snapshot.stats.parsed_packets,
            "parse_errors": snapshot.stats.parse_errors,
            "ipv4": snapshot.stats.ipv4_packets,
            "ipv6": snapshot.stats.ipv6_packets,
            "other": snapshot.stats.other_packets,
            "queue_dropped": snapshot.queue_dropped,
            "record_dropped": snapshot.record_dropped,
            "recording": snapshot.recording,
            "segments": [path.name for path in snapshot.segments],
            "last_error": snapshot.last_error,
        }
        (output / "soak_gui_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"finished {json.dumps(summary, ensure_ascii=False)}")
        app.quit()

    QTimer.singleShot(int(args.hours * 3600 * 1000), finish)
    log(f"planned_hours={args.hours} output={output.resolve()}")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
