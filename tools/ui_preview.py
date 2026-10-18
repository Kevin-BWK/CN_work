"""Render a deterministic offscreen UI preview for layout review."""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from packet_analyzer.session import analyze_pcapng
from packet_analyzer.ui.main_window import MainWindow


def main() -> None:
    files = sorted(Path("data").glob("smoke/**/session.pcapng"))
    if not files:
        raise SystemExit("Run tools/session_smoke_test.py first.")

    stats, records = analyze_pcapng(files[-1], max_recent=200)
    app = QApplication([])
    window = MainWindow()
    window._apply_snapshot(stats, records)
    window.show()
    if records:
        window.table.selectRow(0)
    for _ in range(4):
        app.processEvents()

    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    for index, name in enumerate(
        ("ui_preview.png", "ui_preview_buckets.png", "ui_preview_protocol.png")
    ):
        window.charts.setCurrentIndex(index)
        for _ in range(2):
            app.processEvents()
        path = output / name
        if not window.grab().save(str(path)):
            raise SystemExit("Failed to save UI preview.")
        print(path)
    window.close()


if __name__ == "__main__":
    main()
