from __future__ import annotations

from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import (
    ICMPv6EchoRequest,
    IPv6,
    IPv6ExtHdrFragment,
    IPv6ExtHdrHopByHop,
)
from scapy.layers.l2 import ARP, Dot1Q, Dot3, Ether, LLC

from packet_analyzer.parser import parse_packet


def parse(packet, index: int = 1):
    return parse_packet(bytes(packet), timestamp=1000.0, index=index)


def test_ipv4_tcp_fields_and_flags() -> None:
    packet = (
        Ether(
            src="00:11:22:33:44:55",
            dst="66:77:88:99:aa:bb",
        )
        / IP(src="192.0.2.10", dst="198.51.100.20", ttl=64)
        / TCP(sport=12345, dport=443, flags="SA")
    )

    record = parse(packet)

    assert record.parse_error is None
    assert record.src_mac == "00:11:22:33:44:55"
    assert record.dst_mac == "66:77:88:99:aa:bb"
    assert record.ether_type == 0x0800
    assert record.ip_version == 4
    assert record.src_ip == "192.0.2.10"
    assert record.dst_ip == "198.51.100.20"
    assert record.ttl == 64
    assert record.protocol_number == 6
    assert record.transport_protocol == "TCP"
    assert record.src_port == 12345
    assert record.dst_port == 443
    assert record.tcp_syn is True
    assert record.tcp_ack is True
    assert record.tcp_fin is False
    assert record.tcp_rst is False
    assert record.ip_length == len(bytes(packet)) - 14


def test_ipv4_udp_fields() -> None:
    packet = (
        Ether()
        / IP(src="10.0.0.1", dst="10.0.0.2", ttl=63)
        / UDP(sport=5353, dport=53)
    )

    record = parse(packet)

    assert record.parse_error is None
    assert record.transport_protocol == "UDP"
    assert record.protocol_number == 17
    assert record.src_port == 5353
    assert record.dst_port == 53
    assert record.tcp_flags == 0
    assert record.ttl == 63


def test_ipv6_tcp_fields() -> None:
    packet = (
        Ether()
        / IPv6(src="2001:db8::1", dst="2001:db8::2", hlim=32)
        / TCP(sport=8080, dport=443, flags="A")
    )

    record = parse(packet)

    assert record.parse_error is None
    assert record.ip_version == 6
    assert record.src_ip == "2001:db8::1"
    assert record.dst_ip == "2001:db8::2"
    assert record.ttl == 32
    assert record.protocol_number == 6
    assert record.transport_protocol == "TCP"
    assert record.src_port == 8080
    assert record.dst_port == 443
    assert record.tcp_ack is True
    assert record.ip_length == 40 + len(bytes(packet)) - 14 - 40


def test_arp_is_other_and_field_na() -> None:
    packet = Ether() / ARP(psrc="192.0.2.1", pdst="192.0.2.2")

    record = parse(packet)

    assert record.parse_error is None
    assert record.ether_type == 0x0806
    assert record.ip_version is None
    assert record.ip_length is None
    assert record.protocol_label == "ARP"
    assert record.protocol_number is None
    assert record.transport_protocol is None


def test_vlan_uses_inner_ether_type() -> None:
    packet = (
        Ether()
        / Dot1Q(vlan=10, type=0x0800)
        / IP(src="172.16.0.1", dst="172.16.0.2")
        / TCP(sport=1000, dport=80)
    )

    record = parse(packet)

    assert record.parse_error is None
    assert record.vlan_id == 10
    assert record.ether_type == 0x0800
    assert record.ip_version == 4
    assert record.src_port == 1000
    assert record.dst_port == 80


def test_non_first_fragment_does_not_guess_ports() -> None:
    packet = (
        Ether()
        / IP(src="192.0.2.1", dst="192.0.2.2", frag=10)
        / TCP(sport=1234, dport=80, flags="S")
    )

    record = parse(packet)

    assert record.parse_error is None
    assert record.ip_version == 4
    assert record.protocol_number == 6
    assert record.transport_protocol is None
    assert record.src_port is None
    assert record.dst_port is None


def test_truncated_frame_returns_record_without_exception() -> None:
    packet = Ether() / IP(src="192.0.2.1", dst="192.0.2.2") / TCP()
    raw = bytes(packet)[:10]

    record = parse_packet(raw, timestamp=1000.0, index=7)

    assert record.index == 7
    assert record.frame_length == 10
    assert record.parse_error is not None


def test_8023_stp_frame_is_recorded_as_unsupported() -> None:
    # 802.3/LLC frames carry a length field instead of an EtherType and have
    # no ``type`` attribute; parsing used to kill the processing thread.
    frame = (
        Dot3(dst="01:80:c2:00:00:00", src="00:11:22:33:44:55")
        / LLC(dsap=0x42, ssap=0x42, ctrl=3)
        / (b"\x00" * 35)
    )

    record = parse(bytes(frame), index=9)

    assert record.parse_error is None
    assert record.unsupported == "802.3/LLC"
    assert record.ip_version is None
    assert record.ether_type is None
    assert record.src_mac == "00:11:22:33:44:55"
    assert record.frame_length == len(bytes(frame))


def test_wire_length_comes_from_capture_source() -> None:
    packet = Ether() / IP() / TCP()

    record = parse_packet(bytes(packet)[:20], timestamp=1000.0, index=3, wire_length=1500)

    assert record.frame_length == 20
    assert record.wire_length == 1500


def test_tunneled_ipv4_does_not_expose_inner_ports() -> None:
    packet = (
        Ether()
        / IP(src="192.0.2.1", dst="198.51.100.1")
        / IP(src="10.0.0.1", dst="10.0.0.2")
        / TCP(sport=1234, dport=80)
    )

    record = parse(packet)

    assert record.protocol_number == 4
    assert record.transport_protocol is None
    assert record.src_port is None
    assert record.src_ip == "192.0.2.1"


def test_ipv6_extension_header_reports_final_protocol() -> None:
    packet = Ether() / IPv6() / IPv6ExtHdrHopByHop() / TCP(sport=1000, dport=443)

    record = parse(packet)

    assert record.ip_version == 6
    assert record.protocol_number == 6
    assert record.transport_protocol == "TCP"
    assert record.src_port == 1000
    assert record.dst_port == 443


def test_icmp_and_icmpv6_have_no_transport_ports() -> None:
    icmp = parse(Ether() / IP(src="192.0.2.1", dst="192.0.2.2") / ICMP())
    assert icmp.protocol_number == 1
    assert icmp.transport_protocol is None
    assert icmp.src_port is None

    icmpv6 = parse(
        Ether()
        / IPv6(src="2001:db8::1", dst="2001:db8::2")
        / ICMPv6EchoRequest()
    )
    assert icmpv6.protocol_number == 58
    assert icmpv6.transport_protocol is None
    assert icmpv6.src_port is None
    assert icmpv6.protocol_label == "ICMPv6"


def test_tcp_flag_bits_are_exposed_individually() -> None:
    record = parse(
        Ether() / IP() / TCP(sport=1, dport=2, flags="FRA")
    )

    assert record.tcp_fin is True
    assert record.tcp_rst is True
    assert record.tcp_ack is True
    assert record.tcp_syn is False
    assert record.tcp_flags_label == "ACK, FIN, RST"


def test_double_vlan_keeps_the_inner_tag() -> None:
    # The parser keeps only the innermost VLAN id; outer tags are not modeled.
    packet = (
        Ether()
        / Dot1Q(vlan=100)
        / Dot1Q(vlan=200, type=0x0800)
        / IP(src="192.0.2.1", dst="192.0.2.2")
        / TCP()
    )

    record = parse(packet)

    assert record.vlan_id == 200
    assert record.ether_type == 0x0800
    assert record.ip_version == 4


def test_ipv6_non_first_fragment_has_no_ports() -> None:
    packet = (
        Ether()
        / IPv6(src="2001:db8::1", dst="2001:db8::2")
        / IPv6ExtHdrFragment(offset=10)
        / TCP(sport=1000, dport=80)
    )

    record = parse(packet)

    assert record.transport_protocol is None
    assert record.src_port is None
    assert record.dst_port is None
