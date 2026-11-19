from __future__ import annotations

from packet_analyzer.models import PacketRecord
from packet_analyzer.statistics import (
    BUCKET_LARGE,
    BUCKET_MEDIUM,
    BUCKET_SMALL,
    StatsAggregator,
    length_bucket,
)


def record(
    *,
    index: int,
    ip_version: int | None,
    ip_length: int | None,
    ether_type: int | None = None,
    transport: str | None = None,
    parse_error: str | None = None,
    timestamp: float = 1000.0,
) -> PacketRecord:
    return PacketRecord(
        index=index,
        timestamp=timestamp,
        frame_length=ip_length or 60,
        wire_length=ip_length or 60,
        ether_type=ether_type,
        ip_version=ip_version,
        ip_length=ip_length,
        transport_protocol=transport,
        parse_error=parse_error,
    )


def test_length_bucket_boundaries() -> None:
    assert length_bucket(46) == BUCKET_SMALL
    assert length_bucket(47) == BUCKET_MEDIUM
    assert length_bucket(1499) == BUCKET_MEDIUM
    assert length_bucket(1500) == BUCKET_LARGE


def test_statistics_counts_protocols_and_buckets() -> None:
    stats = StatsAggregator()
    stats.add(record(index=1, ip_version=4, ip_length=46, ether_type=0x0800, transport="TCP"))
    stats.add(record(index=2, ip_version=4, ip_length=47, ether_type=0x0800, transport="UDP"))
    stats.add(record(index=3, ip_version=6, ip_length=1499, ether_type=0x86DD, transport="TCP"))
    stats.add(record(index=4, ip_version=6, ip_length=1500, ether_type=0x86DD))
    stats.add(record(index=5, ip_version=None, ip_length=None, ether_type=0x0806))

    snapshot = stats.snapshot(now=1000.0)

    assert snapshot.total_packets == 5
    assert snapshot.parsed_packets == 5
    assert snapshot.parse_errors == 0
    assert snapshot.ipv4_packets == 2
    assert snapshot.ipv6_packets == 2
    assert snapshot.other_packets == 1
    assert dict(snapshot.bucket_counts) == {
        BUCKET_SMALL: 1,
        BUCKET_MEDIUM: 2,
        BUCKET_LARGE: 1,
    }
    assert dict(snapshot.length_counts)[1500] == 1
    assert dict(snapshot.ether_type_counts)[0x0806] == 1
    assert dict(snapshot.transport_counts) == {"TCP": 2, "UDP": 1}


def test_parse_errors_are_counted() -> None:
    stats = StatsAggregator()
    stats.add(
        record(
            index=1,
            ip_version=None,
            ip_length=None,
            parse_error="truncated",
        )
    )

    snapshot = stats.snapshot(now=1000.0)

    assert snapshot.total_packets == 1
    assert snapshot.parsed_packets == 0
    assert snapshot.parse_errors == 1


def test_rate_uses_requested_window() -> None:
    stats = StatsAggregator()
    stats.add(record(index=1, ip_version=4, ip_length=60, timestamp=1000.0))
    stats.add(record(index=2, ip_version=4, ip_length=60, timestamp=1001.0))
    stats.add(record(index=3, ip_version=4, ip_length=60, timestamp=1009.0))

    assert stats.packet_rate(window_seconds=5, now=1009.0) == 1 / 5
