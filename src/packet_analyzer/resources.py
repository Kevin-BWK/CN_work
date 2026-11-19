"""Periodic resource sampling for the long-running test."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import threading
import time
from typing import Callable

import psutil


class ResourceLogger:
    """Write process and session metrics to CSV without blocking capture."""

    HEADERS = (
        "timestamp",
        "uptime_seconds",
        "cpu_percent",
        "rss_mb",
        "disk_write_mb",
        "system_memory_percent",
        "disk_free_mb",
        "captured",
        "parsed",
        "parse_errors",
        "queue_dropped",
        "record_dropped",
    )

    def __init__(
        self,
        path: str | Path,
        counters: Callable[[], dict[str, int]],
        interval_seconds: float = 10.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.path = Path(path).resolve()
        self._counters = counters
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._file = None
        self._writer = None
        self._started_monotonic = 0.0
        self._baseline_disk_write = 0
        self._process = psutil.Process()
        self._process.cpu_percent(None)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("resource logger is already started")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.HEADERS)
        self._file.flush()
        self._started_monotonic = time.monotonic()
        self._baseline_disk_write = self._process.io_counters().write_bytes
        self._thread = threading.Thread(
            target=self._loop,
            name="resource-logger",
            daemon=True,
        )
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self.write_sample()

    def write_sample(self) -> None:
        if self._writer is None:
            return
        try:
            counters = self._counters()
        except Exception:
            counters = {}
        try:
            disk_write = (
                self._process.io_counters().write_bytes
                - self._baseline_disk_write
            ) / (1024 * 1024)
        except Exception:
            disk_write = 0.0
        try:
            disk_free = psutil.disk_usage(self.path.anchor).free / (1024 * 1024)
        except Exception:
            disk_free = 0.0

        row = (
            datetime.now().isoformat(timespec="seconds"),
            f"{time.monotonic() - self._started_monotonic:.1f}",
            f"{self._process.cpu_percent(None):.1f}",
            f"{self._process.memory_info().rss / (1024 * 1024):.1f}",
            f"{disk_write:.1f}",
            f"{psutil.virtual_memory().percent:.1f}",
            f"{disk_free:.1f}",
            counters.get("captured", 0),
            counters.get("parsed", 0),
            counters.get("parse_errors", 0),
            counters.get("queue_dropped", 0),
            counters.get("record_dropped", 0),
        )
        with self._lock:
            self._writer.writerow(row)
            self._file.flush()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=5)
        self._thread = None
        self.write_sample()
        with self._lock:
            if self._file is not None:
                self._file.close()
        self._file = None
        self._writer = None
