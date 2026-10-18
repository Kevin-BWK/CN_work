from __future__ import annotations

from pathlib import Path

from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import ARP, Ether

from packet_analyzer.models import RawPacket
from packet_analyzer.session import CaptureSession, analyze_pcapng


def raw(packet, timestamp: float = 1000.0) -> RawPacket:
    data = bytes(packet)
    return RawPacket(timestamp=timestamp, data=data, wire_length=len(data))


def test_session_process_raw_updates_stats_and_recent() -> None:
    session = CaptureSession(max_recent=10)
    session.process_raw(
        raw(
            Ether()
            / IP(src="192.0.2.1", dst="198.51.100.1")
            / TCP(sport=1000, dport=80, flags="S")
        )
    )
    session.process_raw(
        raw(Ether() / IPv6(src="2001:db8::1", dst="2001:db8::2") / TCP())
    )
    session.process_raw(raw(Ether() / ARP()))

    snapshot = session.snapshot()

    assert snapshot.stats.total_packets == 3
    assert snapshot.stats.ipv4_packets == 1
    assert snapshot.stats.ipv6_packets == 1
    assert snapshot.stats.other_packets == 1
    assert len(snapshot.recent) == 3
    assert snapshot.recent[0].src_port == 1000


def test_analyze_pcapng_matches_live_session(tmp_path: Path) -> None:
    from packet_analyzer.recording import PcapNgRecorder

    session = CaptureSession()
    frames = [
        raw(
            Ether()
            / IP(src="192.0.2.1", dst="198.51.100.1")
            / TCP(sport=1000, dport=80, flags="S")
        ),
        raw(Ether() / ARP()),
    ]
    for frame in frames:
        session.process_raw(frame)
    live = session.snapshot().stats

    recorder = PcapNgRecorder(tmp_path)
    recorder.start()
    for frame in frames:
        recorder.write(frame)
    recorder.stop()

    loaded, recent = analyze_pcapng(recorder.segment_paths[0])

    assert loaded.total_packets == live.total_packets == 2
    assert loaded.ipv4_packets == live.ipv4_packets == 1
    assert loaded.other_packets == live.other_packets == 1
    assert dict(loaded.bucket_counts) == dict(live.bucket_counts)
    assert len(recent) == 2
