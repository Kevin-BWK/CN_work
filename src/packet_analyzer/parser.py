"""Packet parsing for the fields required by the course project."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6, IPv6ExtHdrFragment
from scapy.layers.l2 import Dot1Q, Ether

from .models import PacketRecord


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _effective_ether_type(packet: Ether) -> tuple[int, int | None]:
    """Return the innermost EtherType and the outermost VLAN id, if any."""

    ether_type = int(packet.type)
    vlan_id: int | None = None
    payload = packet.payload
    while isinstance(payload, Dot1Q):
        vlan_id = int(payload.vlan)
        ether_type = int(payload.type)
        payload = payload.payload
    return ether_type, vlan_id


def _ipv4_transport(
    packet: Ether, ipv4: IP
) -> tuple[str | None, int | None, int | None, int]:
    """Return transport name, ports and TCP flags for an IPv4 packet."""

    # Offset != 0 means this is not the first fragment, so transport headers
    # are not present in this frame.
    if int(ipv4.frag) != 0:
        return None, None, None, 0

    tcp = packet.getlayer(TCP)
    if tcp is not None:
        return (
            "TCP",
            _safe_int(tcp.sport),
            _safe_int(tcp.dport),
            _safe_int(tcp.flags, 0) or 0,
        )

    udp = packet.getlayer(UDP)
    if udp is not None:
        return (
            "UDP",
            _safe_int(udp.sport),
            _safe_int(udp.dport),
            0,
        )

    return None, None, None, 0


def _ipv6_transport(
    packet: Ether, ipv6: IPv6
) -> tuple[str | None, int | None, int | None, int, int]:
    """Return transport data and the effective IPv6 next-header value."""

    fragment = packet.getlayer(IPv6ExtHdrFragment)
    if fragment is not None and int(fragment.offset) != 0:
        return None, None, None, 0, int(ipv6.nh)

    tcp = packet.getlayer(TCP)
    if tcp is not None:
        return (
            "TCP",
            _safe_int(tcp.sport),
            _safe_int(tcp.dport),
            _safe_int(tcp.flags, 0) or 0,
            6,
        )

    udp = packet.getlayer(UDP)
    if udp is not None:
        return (
            "UDP",
            _safe_int(udp.sport),
            _safe_int(udp.dport),
            0,
            17,
        )

    return None, None, None, 0, int(ipv6.nh)


def parse_packet(raw: bytes, timestamp: float, index: int) -> PacketRecord:
    """Parse one raw Ethernet frame into a compact record.

    Parsing never raises for malformed/truncated input. The returned record
    contains a ``parse_error`` string when the frame cannot be fully decoded.
    """

    frame_length = len(raw)
    try:
        packet = Ether(raw)
    except Exception as exc:  # pragma: no cover - exact Scapy errors vary
        return PacketRecord(
            index=index,
            timestamp=timestamp,
            frame_length=frame_length,
            wire_length=frame_length,
            parse_error=f"Ether: {exc}",
        )

    src_mac = str(getattr(packet, "src", "")) or None
    dst_mac = str(getattr(packet, "dst", "")) or None
    ether_type, vlan_id = _effective_ether_type(packet)
    wire_length = _safe_int(getattr(packet, "wirelen", None), frame_length) or frame_length

    try:
        summary = packet.summary()
    except Exception:
        summary = ""

    record = PacketRecord(
        index=index,
        timestamp=timestamp,
        frame_length=frame_length,
        wire_length=wire_length,
        src_mac=src_mac,
        dst_mac=dst_mac,
        ether_type=ether_type,
        vlan_id=vlan_id,
        summary=summary[:240],
    )

    try:
        if ether_type == 0x0800:
            ipv4 = packet.getlayer(IP)
            if ipv4 is None:
                raise ValueError("IPv4 EtherType without an IPv4 layer")

            ip_length = _safe_int(ipv4.len)
            if not ip_length:
                ip_length = len(bytes(ipv4))

            transport, src_port, dst_port, tcp_flags = _ipv4_transport(
                packet, ipv4
            )
            record = replace(
                record,
                ip_version=4,
                ip_length=ip_length,
                src_ip=str(ipv4.src),
                dst_ip=str(ipv4.dst),
                ttl=_safe_int(ipv4.ttl),
                protocol_number=_safe_int(ipv4.proto),
                transport_protocol=transport,
                src_port=src_port,
                dst_port=dst_port,
                tcp_flags=tcp_flags,
            )

        elif ether_type == 0x86DD:
            ipv6 = packet.getlayer(IPv6)
            if ipv6 is None:
                raise ValueError("IPv6 EtherType without an IPv6 layer")

            payload_length = _safe_int(ipv6.plen, 0) or 0
            ip_length = 40 + payload_length if payload_length else len(bytes(ipv6))
            transport, src_port, dst_port, tcp_flags, next_header = (
                _ipv6_transport(packet, ipv6)
            )
            record = replace(
                record,
                ip_version=6,
                ip_length=ip_length,
                src_ip=str(ipv6.src),
                dst_ip=str(ipv6.dst),
                ttl=_safe_int(ipv6.hlim),
                protocol_number=next_header,
                transport_protocol=transport,
                src_port=src_port,
                dst_port=dst_port,
                tcp_flags=tcp_flags,
            )

    except Exception as exc:
        record = replace(record, parse_error=str(exc))

    return record
