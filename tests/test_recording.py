from __future__ import annotations

from pathlib import Path

from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether
from scapy.utils import wrpcap

from packet_analyzer.models import RawPacket
from packet_analyzer.recording import PcapNgRecorder, read_capture, read_pcapng


def make_packet(payload: bytes = b"hello") -> bytes:
    return bytes(
        Ether()
        / IP(src="192.0.2.10", dst="198.51.100.20")
        / TCP(sport=1234, dport=80, flags="S")
        / payload
    )


def test_pcapng_round_trip_preserves_frame_and_timestamp(tmp_path: Path) -> None:
    recorder = PcapNgRecorder(tmp_path)
    recorder.start()
    recorder.write(
        RawPacket(
            timestamp=1_700_000_000.125,
            data=make_packet(b"abc"),
            wire_length=100,
        )
    )
    recorder.write(
        RawPacket(
            timestamp=1_700_000_001.5,
            data=make_packet(b"def"),
            wire_length=100,
        )
    )
    recorder.stop()

    packets = list(read_pcapng(recorder.segment_paths[0]))

    assert len(packets) == 2
    assert packets[0].data == make_packet(b"abc")
    assert packets[0].wire_length == 100
    assert abs(packets[0].timestamp - 1_700_000_000.125) < 0.001
    assert abs(packets[1].timestamp - 1_700_000_001.5) < 0.001


def test_export_single_from_one_segment(tmp_path: Path) -> None:
    recorder = PcapNgRecorder(tmp_path / "segments")
    recorder.start()
    recorder.write(
        RawPacket(
            timestamp=1_700_000_000.0,
            data=make_packet(),
            wire_length=60,
        )
    )
    recorder.stop()

    exported = recorder.export_single(tmp_path / "single.pcapng")

    assert exported.exists()
    assert len(list(read_pcapng(exported))) == 1


def test_export_single_can_overwrite(tmp_path: Path) -> None:
    recorder = PcapNgRecorder(tmp_path / "segments")
    recorder.start()
    recorder.write(
        RawPacket(
            timestamp=1_700_000_000.0,
            data=make_packet(),
            wire_length=60,
        )
    )
    recorder.stop()
    destination = tmp_path / "single.pcapng"
    destination.write_bytes(b"old")

    recorder.export_single(destination, overwrite=True)

    assert len(list(read_pcapng(destination))) == 1


def test_read_capture_accepts_classic_pcap(tmp_path: Path) -> None:
    path = tmp_path / "sample.pcap"
    wrpcap(str(path), [Ether() / IP(src="192.0.2.1", dst="192.0.2.2") / TCP()])

    packets = list(read_capture(path))

    assert len(packets) == 1
    assert packets[0].wire_length > 0
