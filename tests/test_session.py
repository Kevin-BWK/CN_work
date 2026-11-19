from __future__ import annotations

from pathlib import Path
import threading
import time

from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import ARP, Dot3, Ether, LLC

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


def test_unsupported_link_frame_keeps_processing() -> None:
    session = CaptureSession(max_recent=10)
    stp = (
        Dot3(dst="01:80:c2:00:00:00", src="00:11:22:33:44:55")
        / LLC(dsap=0x42, ssap=0x42, ctrl=3)
        / (b"\x00" * 35)
    )

    session.process_raw(raw(stp))
    session.process_raw(
        raw(Ether() / IP(src="192.0.2.1", dst="198.51.100.1") / TCP(sport=1234, dport=80))
    )

    snapshot = session.snapshot()

    assert snapshot.stats.total_packets == 2
    assert snapshot.stats.parse_errors == 0
    assert snapshot.stats.other_packets == 1
    assert snapshot.recent[-1].src_port == 1234


def test_stop_is_bounded_when_recorder_failed_and_queue_full(
    tmp_path: Path, monkeypatch
) -> None:
    session = CaptureSession(max_recent=10, record_queue_size=1)
    session._start_recording(tmp_path)
    session._start_processing()

    def disk_full(packet) -> None:
        raise OSError("模拟磁盘写入失败")

    monkeypatch.setattr(session._recorder, "write", disk_full)

    # The first packet makes the recorder thread die; later packets fill the
    # record queue because _recording still claims to be true.
    for _ in range(6):
        session._process_one(raw(Ether() / IP(src="192.0.2.1", dst="198.51.100.1") / TCP()))
        time.sleep(0.02)

    stopper = threading.Thread(target=session.stop, daemon=True)
    stopper.start()
    stopper.join(timeout=10)

    assert not stopper.is_alive(), "记录线程失败且队列已满时 stop() 不应无限阻塞"
    assert session.snapshot().recording is False
    assert session.snapshot().last_error is not None


def test_low_disk_stops_recording_but_keeps_statistics(
    tmp_path: Path, monkeypatch
) -> None:
    from packet_analyzer import session as session_module
    from packet_analyzer.recording import PcapNgRecorder

    monkeypatch.setattr(
        session_module,
        "PcapNgRecorder",
        lambda path: PcapNgRecorder(path, min_free_bytes=10**15),
    )

    session = CaptureSession(max_recent=10, record_queue_size=100)
    session._start_recording(tmp_path)
    session._start_processing()

    for _ in range(3):
        session._process_one(
            raw(Ether() / IP(src="192.0.2.1", dst="198.51.100.1") / TCP())
        )
        time.sleep(0.05)

    snapshot = session.snapshot()

    assert snapshot.recording is False
    assert "磁盘" in (snapshot.last_error or "")
    assert snapshot.stats.total_packets == 3

    session.stop()


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
