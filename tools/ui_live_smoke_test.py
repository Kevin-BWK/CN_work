"""Exercise the real GUI pipeline with a short live capture."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from packet_analyzer.ui.main_window import MainWindow


def main() -> None:
    app = QApplication([])
    window = MainWindow()
    window.show()
    window.start_capture()
    QTest.qWait(500)

    if window._session is None or not window._session.running:
        raise SystemExit("Live capture did not start.")

    subprocess.run(
        ["ping", "-n", "4", "10.195.116.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    QTest.qWait(2500)
    window.stop_capture()
    QTest.qWait(300)

    snapshot = window._session.snapshot()
    print(
        f"live GUI: packets={snapshot.stats.total_packets} "
        f"rows={window.table_model.rowCount()} "
        f"errors={snapshot.stats.parse_errors}"
    )
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    path = output / "ui_live.png"
    if not window.grab().save(str(path)):
        raise SystemExit("Failed to save live UI screenshot.")
    print(path)
    window.close()
    app.processEvents()


if __name__ == "__main__":
    main()
