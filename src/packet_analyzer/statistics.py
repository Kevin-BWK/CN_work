"""Aggregate packet statistics with bounded memory usage."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import time

from .models import PacketRecord


BUCKET_SMALL = "<=46"
BUCKET_MEDIUM = "47-1499"
BUCKET_LARGE = ">=1500"
LENGTH_BUCKETS = (BUCKET_SMALL, BUCKET_MEDIUM, BUCKET_LARGE)


def length_bucket(length: int) -> str:
    if length <= 46:
        return BUCKET_SMALL
    if length < 1500:
        return BUCKET_MEDIUM
    return BUCKET_LARGE


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    total_packets: int
    parsed_packets: int
    parse_errors: int
    ipv4_packets: int
    ipv6_packets: int
    other_packets: int
    total_bytes: int
    length_counts: tuple[tuple[int, int], ...]
    bucket_counts: tuple[tuple[str, int], ...]
    ether_type_counts: tuple[tuple[int, int], ...]
    transport_counts: tuple[tuple[str, int], ...]
    first_timestamp: float | None
    last_timestamp: float | None
    packets_per_second: float


class StatsAggregator:
    """Incremental statistics that do not retain every packet.

    The class is not internally locked. The session layer owns it and updates
    it from one processing thread; the UI receives immutable snapshots.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.total_packets = 0
        self.parsed_packets = 0
        self.parse_errors = 0
        self.ipv4_packets = 0
        self.ipv6_packets = 0
        self.other_packets = 0
        self.total_bytes = 0
        self.length_counts: Counter[int] = Counter()
        self.bucket_counts: Counter[str] = Counter(
            {bucket: 0 for bucket in LENGTH_BUCKETS}
        )
        self.ether_type_counts: Counter[int] = Counter()
        self.transport_counts: Counter[str] = Counter()
        self.first_timestamp: float | None = None
        self.last_timestamp: float | None = None
        self._second_counts: Counter[int] = Counter()
        self._recent_seconds: deque[int] = deque(maxlen=120)

    def add(self, record: PacketRecord) -> None:
        self.total_packets += 1
        self.total_bytes += record.frame_length

        if record.parse_error:
            self.parse_errors += 1
        else:
            self.parsed_packets += 1

        if record.ip_version == 4:
            self.ipv4_packets += 1
        elif record.ip_version == 6:
            self.ipv6_packets += 1
        else:
            self.other_packets += 1

        if record.ether_type is not None:
            self.ether_type_counts[record.ether_type] += 1

        if record.transport_protocol:
            self.transport_counts[record.transport_protocol] += 1

        if record.ip_length is not None and record.ip_length > 0:
            self.length_counts[record.ip_length] += 1
            self.bucket_counts[length_bucket(record.ip_length)] += 1

        timestamp = float(record.timestamp)
        if self.first_timestamp is None or timestamp < self.first_timestamp:
            self.first_timestamp = timestamp
        if self.last_timestamp is None or timestamp > self.last_timestamp:
            self.last_timestamp = timestamp

        second = int(timestamp)
        if second not in self._second_counts:
            self._recent_seconds.append(second)
        self._second_counts[second] += 1
        self._prune_seconds(second)

    def _prune_seconds(self, current_second: int) -> None:
        while self._recent_seconds and self._recent_seconds[0] < current_second - 60:
            old_second = self._recent_seconds.popleft()
            self._second_counts.pop(old_second, None)

    def packet_rate(self, window_seconds: int = 5, now: float | None = None) -> float:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        current = time.time() if now is None else now
        start = int(current) - window_seconds + 1
        total = sum(
            count
            for second, count in self._second_counts.items()
            if start <= second <= int(current)
        )
        return total / window_seconds

    def snapshot(self, now: float | None = None) -> StatsSnapshot:
        rate_now = (
            self.last_timestamp
            if now is None and self.last_timestamp is not None
            else now
        )
        return StatsSnapshot(
            total_packets=self.total_packets,
            parsed_packets=self.parsed_packets,
            parse_errors=self.parse_errors,
            ipv4_packets=self.ipv4_packets,
            ipv6_packets=self.ipv6_packets,
            other_packets=self.other_packets,
            total_bytes=self.total_bytes,
            length_counts=tuple(sorted(self.length_counts.items())),
            bucket_counts=tuple(
                (bucket, self.bucket_counts[bucket]) for bucket in LENGTH_BUCKETS
            ),
            ether_type_counts=tuple(sorted(self.ether_type_counts.items())),
            transport_counts=tuple(sorted(self.transport_counts.items())),
            first_timestamp=self.first_timestamp,
            last_timestamp=self.last_timestamp,
            packets_per_second=self.packet_rate(now=rate_now),
        )
