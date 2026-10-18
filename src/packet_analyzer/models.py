"""Data models shared by capture, parsing, statistics and the UI."""

from __future__ import annotations

from dataclasses import dataclass


ETHER_TYPE_NAMES: dict[int, str] = {
    0x0800: "IPv4",
    0x0806: "ARP",
    0x8100: "802.1Q",
    0x86DD: "IPv6",
    0x88CC: "LLDP",
    0x8847: "MPLS",
}

IP_PROTOCOL_NAMES: dict[int, str] = {
    1: "ICMP",
    2: "IGMP",
    6: "TCP",
    17: "UDP",
    41: "IPv6",
    47: "GRE",
    50: "ESP",
    51: "AH",
    58: "ICMPv6",
}


@dataclass(frozen=True, slots=True)
class RawPacket:
    """One captured frame before protocol parsing."""

    timestamp: float
    data: bytes
    wire_length: int


@dataclass(frozen=True, slots=True)
class PacketRecord:
    """A compact, UI-friendly record for one captured frame.

    Raw bytes are intentionally not retained here. The recorder is responsible
    for writing raw packets to pcapng, while this object keeps only the fields
    required by the table, detail view and statistics.
    """

    index: int
    timestamp: float
    frame_length: int
    wire_length: int
    src_mac: str | None = None
    dst_mac: str | None = None
    ether_type: int | None = None
    vlan_id: int | None = None
    ip_version: int | None = None
    ip_length: int | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    ttl: int | None = None
    protocol_number: int | None = None
    transport_protocol: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    tcp_flags: int = 0
    summary: str = ""
    parse_error: str | None = None

    @property
    def is_ipv4(self) -> bool:
        return self.ip_version == 4

    @property
    def is_ipv6(self) -> bool:
        return self.ip_version == 6

    @property
    def is_ip(self) -> bool:
        return self.ip_version in (4, 6)

    @property
    def tcp_syn(self) -> bool:
        return bool(self.tcp_flags & 0x02)

    @property
    def tcp_ack(self) -> bool:
        return bool(self.tcp_flags & 0x10)

    @property
    def tcp_fin(self) -> bool:
        return bool(self.tcp_flags & 0x01)

    @property
    def tcp_rst(self) -> bool:
        return bool(self.tcp_flags & 0x04)

    @property
    def protocol_label(self) -> str:
        if self.transport_protocol:
            return self.transport_protocol
        if self.protocol_number is not None:
            return IP_PROTOCOL_NAMES.get(
                self.protocol_number, f"IP/{self.protocol_number}"
            )
        if self.ether_type is not None:
            return ETHER_TYPE_NAMES.get(
                self.ether_type, f"0x{self.ether_type:04X}"
            )
        return "Unknown"

    @property
    def ether_type_label(self) -> str:
        if self.ether_type is None:
            return "N/A"
        return ETHER_TYPE_NAMES.get(
            self.ether_type, f"0x{self.ether_type:04X}"
        )

    @property
    def length_label(self) -> str:
        if self.ip_length is not None:
            return str(self.ip_length)
        return f"{self.frame_length} (frame)"

    @property
    def tcp_flags_label(self) -> str:
        if self.transport_protocol != "TCP":
            return "N/A"
        flags = [
            name
            for name, enabled in (
                ("SYN", self.tcp_syn),
                ("ACK", self.tcp_ack),
                ("FIN", self.tcp_fin),
                ("RST", self.tcp_rst),
            )
            if enabled
        ]
        return ", ".join(flags) if flags else "none"
