from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from packet_analyzer.models import PacketRecord
from packet_analyzer.statistics import StatsAggregator
from packet_analyzer.ui.main_window import MainWindow, format_uptime


def test_main_window_can_build_and_render() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    stats = StatsAggregator()
    record = PacketRecord(
        index=1,
        timestamp=1_700_000_000.0,
        frame_length=74,
        wire_length=74,
        src_mac="00:11:22:33:44:55",
        dst_mac="66:77:88:99:aa:bb",
        ether_type=0x0800,
        ip_version=4,
        ip_length=60,
        src_ip="192.0.2.1",
        dst_ip="198.51.100.1",
        ttl=64,
        protocol_number=6,
        transport_protocol="TCP",
        src_port=1234,
        dst_port=80,
        tcp_flags=0x02,
        summary="Ether / IP / TCP 192.0.2.1:1234 > 198.51.100.1:80 S",
    )
    stats.add(record)

    window._apply_snapshot(stats.snapshot(now=1_700_000_000.0), (record,))
    window.show()
    app.processEvents()

    assert window.table_model.rowCount() == 1
    assert window.table_model.record_at(0) == record
    assert not window.grab().isNull()

    window.close()
    app.processEvents()


def test_format_uptime_crosses_days() -> None:
    assert format_uptime(3_661) == "01:01:01"
    assert format_uptime(86_400 + 3_661) == "1天 01:01:01"
