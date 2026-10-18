"""Capture session pipeline: capture -> parse -> aggregate -> record."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time

from .capture import CaptureWorker, InterfaceInfo
from .models import PacketRecord, RawPacket
from .parser import parse_packet
from .recording import PcapNgRecorder, read_pcapng
from .resources import ResourceLogger
from .statistics import StatsAggregator, StatsSnapshot


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    stats: StatsSnapshot
    recent: tuple[PacketRecord, ...]
    running: bool
    started_at: float | None
    uptime_seconds: float
    queue_depth: int
    queue_dropped: int
    record_dropped: int
    recording: bool
    segments: tuple[Path, ...]
    last_error: str | None


class CaptureSession:
    """Own the processing pipeline and expose immutable UI snapshots."""

    def __init__(
        self,
        max_recent: int = 10_000,
        capture_queue_size: int = 50_000,
        record_queue_size: int = 10_000,
    ) -> None:
        self.max_recent = max_recent
        self._capture = CaptureWorker(capture_queue_size)
        self._record_queue: queue.Queue[RawPacket | None] = queue.Queue(
            maxsize=record_queue_size
        )
        self._stats = StatsAggregator()
        self._recent: deque[PacketRecord] = deque(maxlen=max_recent)
        self._lock = threading.RLock()
        self._next_index = 1
        self._processing_thread: threading.Thread | None = None
        self._record_thread: threading.Thread | None = None
        self._recorder: PcapNgRecorder | None = None
        self._running = False
        self._recording = False
        self._started_at: float | None = None
        self._started_monotonic: float | None = None
        self._stopped_uptime = 0.0
        self._queue_dropped = 0
        self._record_dropped = 0
        self._last_error: str | None = None
        self._interface: InterfaceInfo | None = None
        self._bpf_filter = ""
        self._record_dir: Path | None = None
        self._resource_logger: ResourceLogger | None = None

    @property
    def running(self) -> bool:
        return self._running

    def start(
        self,
        interface: InterfaceInfo,
        bpf_filter: str = "",
        record_dir: str | Path | None = None,
    ) -> None:
        if self._running:
            raise RuntimeError("session is already running")

        self._interface = interface
        self._bpf_filter = bpf_filter
        self._started_at = time.time()
        self._started_monotonic = time.monotonic()
        self._stopped_uptime = 0.0
        self._last_error = None
        self._queue_dropped = 0
        self._record_dropped = 0

        if record_dir is not None:
            self._record_dir = Path(record_dir)
            self._recorder = PcapNgRecorder(self._record_dir)
            self._recorder.start()
            self._recording = True
            self._record_thread = threading.Thread(
                target=self._record_loop,
                name="pcapng-recorder",
                daemon=True,
            )
            self._record_thread.start()
            self._resource_logger = ResourceLogger(
                self._record_dir / "resources.csv",
                self._resource_counters,
            )
            self._resource_logger.start()

        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            name="packet-processor",
            daemon=True,
        )
        self._processing_thread.start()

        try:
            self._capture.start(interface, bpf_filter)
        except Exception:
            self._running = False
            self._capture.queue.put(None)
            if self._processing_thread is not None:
                self._processing_thread.join(timeout=5)
            self._shutdown_recorder()
            if self._resource_logger is not None:
                self._resource_logger.stop()
                self._resource_logger = None
            raise

        self._running = True

    def _processing_loop(self) -> None:
        try:
            while True:
                packet = self._capture.queue.get()
                try:
                    if packet is None:
                        break
                    self._process_one(packet)
                finally:
                    self._capture.queue.task_done()
        except Exception as exc:  # keep the last error visible in the UI
            self._last_error = f"处理线程异常: {exc}"
        finally:
            if self._recording:
                try:
                    self._record_queue.put_nowait(None)
                except queue.Full:
                    self._record_dropped += 1
                    self._record_queue.put(None)

    def _record_loop(self) -> None:
        try:
            while True:
                packet = self._record_queue.get()
                try:
                    if packet is None:
                        break
                    if self._recorder is not None:
                        self._recorder.write(packet)
                finally:
                    self._record_queue.task_done()
        except Exception as exc:
            self._last_error = f"记录线程异常: {exc}"

    def _process_one(self, packet: RawPacket) -> None:
        with self._lock:
            index = self._next_index
            self._next_index += 1

        record = parse_packet(packet.data, packet.timestamp, index)
        with self._lock:
            self._stats.add(record)
            self._recent.append(record)

        if self._recording:
            try:
                self._record_queue.put_nowait(packet)
            except queue.Full:
                self._record_dropped += 1

    def process_raw(self, packet: RawPacket) -> PacketRecord:
        """Process one frame synchronously. Useful for tests and file import."""

        with self._lock:
            index = self._next_index
            self._next_index += 1
            record = parse_packet(packet.data, packet.timestamp, index)
            self._stats.add(record)
            self._recent.append(record)
            return record

    def stop(self) -> None:
        if not self._running and self._processing_thread is None:
            return

        self._running = False
        self._capture.stop()
        if self._started_monotonic is not None:
            self._stopped_uptime = max(
                0.0, time.monotonic() - self._started_monotonic
            )

        try:
            self._capture.queue.put_nowait(None)
        except queue.Full:
            # The processing thread drains the queue, so a short blocking put
            # is preferable to losing the shutdown sentinel.
            self._capture.queue.put(None)

        if self._processing_thread is not None:
            self._processing_thread.join(timeout=15)
            self._processing_thread = None

        self._shutdown_recorder()
        if self._resource_logger is not None:
            self._resource_logger.stop()
            self._resource_logger = None
        self._write_metadata()

    def _resource_counters(self) -> dict[str, int]:
        snapshot = self.snapshot(recent_limit=0)
        return {
            "captured": snapshot.stats.total_packets,
            "parsed": snapshot.stats.parsed_packets,
            "parse_errors": snapshot.stats.parse_errors,
            "queue_dropped": snapshot.queue_dropped,
            "record_dropped": snapshot.record_dropped,
        }

    def _shutdown_recorder(self) -> None:
        if self._record_thread is not None:
            try:
                self._record_queue.put_nowait(None)
            except queue.Full:
                self._record_queue.put(None)
            self._record_thread.join(timeout=15)
            self._record_thread = None
        if self._recorder is not None:
            self._recorder.stop()
            self._recording = False

    def _write_metadata(self) -> None:
        if self._recorder is None or self._record_dir is None:
            return
        metadata = {
            "software_version": "0.1.0",
            "started_at": self._started_at,
            "stopped_at": time.time(),
            "interface": asdict(self._interface) if self._interface else None,
            "bpf_filter": self._bpf_filter,
            "segments": [path.name for path in self._recorder.segment_paths],
        }
        metadata_path = self._record_dir / "session.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self, recent_limit: int | None = None) -> SessionSnapshot:
        with self._lock:
            stats = self._stats.snapshot(now=time.time())
            if recent_limit is None:
                recent = tuple(self._recent)
            elif recent_limit <= 0:
                recent = ()
            else:
                recent = tuple(list(self._recent)[-recent_limit:])

        uptime = self._stopped_uptime
        if self._running and self._started_monotonic is not None:
            uptime = max(0.0, time.monotonic() - self._started_monotonic)

        segments: tuple[Path, ...] = ()
        if self._recorder is not None:
            segments = tuple(self._recorder.segment_paths)

        return SessionSnapshot(
            stats=stats,
            recent=recent,
            running=self._running,
            started_at=self._started_at,
            uptime_seconds=uptime,
            queue_depth=self._capture.queue.qsize(),
            queue_dropped=self._capture.dropped + self._queue_dropped,
            record_dropped=self._record_dropped,
            recording=self._recording,
            segments=segments,
            last_error=self._last_error,
        )

    def export_recording(
        self,
        destination: str | Path,
        overwrite: bool = False,
    ) -> Path:
        if self._recorder is None:
            raise RuntimeError("this session has no recording")
        return self._recorder.export_single(destination, overwrite=overwrite)


def analyze_pcapng(
    path: str | Path,
    max_recent: int = 10_000,
) -> tuple[StatsSnapshot, tuple[PacketRecord, ...]]:
    """Parse a saved pcapng with the same parser used for live traffic."""

    stats = StatsAggregator()
    recent: deque[PacketRecord] = deque(maxlen=max_recent)
    for index, packet in enumerate(read_pcapng(path), start=1):
        record = parse_packet(packet.data, packet.timestamp, index)
        stats.add(record)
        recent.append(record)
    return stats.snapshot(now=time.time()), tuple(recent)
