from __future__ import annotations

import csv
from pathlib import Path
import time

from packet_analyzer.resources import ResourceLogger


def test_resource_logger_writes_header_and_samples(tmp_path: Path) -> None:
    path = tmp_path / "resources.csv"
    logger = ResourceLogger(
        path,
        counters=lambda: {
            "captured": 10,
            "parsed": 9,
            "parse_errors": 1,
            "queue_dropped": 0,
            "record_dropped": 0,
        },
        interval_seconds=0.02,
    )
    logger.start()
    time.sleep(0.06)
    logger.stop()

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0][0] == "timestamp"
    assert len(rows) >= 2
    assert rows[1][7] == "10"
    assert rows[1][9] == "1"
