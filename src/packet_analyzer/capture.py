"""Interface discovery and Npcap-backed packet capture."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import time

import psutil
from scapy.all import AsyncSniffer, conf

from .models import RawPacket


@dataclass(frozen=True, slots=True)
class InterfaceInfo:
    name: str
    description: str
    network_name: str
    mac: str | None
    addresses: tuple[str, ...]
    is_up: bool
    speed_mbps: int

    @property
    def label(self) -> str:
        state = "Up" if self.is_up else "Down"
        address = self.addresses[0] if self.addresses else "no IP"
        return f"{self.name} [{state}] - {address}"


def _flatten_addresses(values: object) -> tuple[str, ...]:
    addresses: list[str] = []
    if isinstance(values, dict):
        for value in values.values():
            addresses.extend(_flatten_addresses(value))
    elif isinstance(values, (list, tuple, set)):
        for value in values:
            addresses.extend(_flatten_addresses(value))
    elif values:
        text = str(values)
        if text not in {"0.0.0.0", "::"}:
            addresses.append(text)
    return tuple(dict.fromkeys(addresses))


def discover_interfaces() -> list[InterfaceInfo]:
    """Return Npcap interfaces, with active physical adapters first."""

    stats = psutil.net_if_stats()
    seen: set[str] = set()
    interfaces: list[InterfaceInfo] = []

    for iface in conf.ifaces.values():
        name = str(getattr(iface, "name", "") or "")
        network_name = str(getattr(iface, "network_name", "") or "")
        if not name or not network_name or network_name in seen:
            continue
        seen.add(network_name)

        stat = stats.get(name)
        mac = str(getattr(iface, "mac", "") or "") or None
        interfaces.append(
            InterfaceInfo(
                name=name,
                description=str(getattr(iface, "description", "") or ""),
                network_name=network_name,
                mac=mac,
                addresses=_flatten_addresses(getattr(iface, "ips", {})),
                is_up=bool(stat.isup) if stat is not None else False,
                speed_mbps=int(stat.speed) if stat is not None else 0,
            )
        )

    def sort_key(interface: InterfaceInfo) -> tuple[int, int, int, str]:
        virtual = int(
            "WAN Miniport" in interface.description
            or "Loopback" in interface.description
        )
        return (
            int(not interface.is_up),
            int(not bool(interface.addresses)),
            virtual,
            interface.name,
        )

    return sorted(interfaces, key=sort_key)


class CaptureWorker:
    """Run Scapy's asynchronous sniffer and put raw frames into a queue."""

    def __init__(self, max_queue_size: int = 50_000) -> None:
        self.queue: queue.Queue[RawPacket | None] = queue.Queue(
            maxsize=max_queue_size
        )
        self.dropped = 0
        self._sniffer: AsyncSniffer | None = None
        self._interface: InterfaceInfo | None = None

    @property
    def running(self) -> bool:
        return bool(self._sniffer is not None and self._sniffer.running)

    def start(
        self,
        interface: InterfaceInfo,
        bpf_filter: str | None = None,
    ) -> None:
        if self.running:
            raise RuntimeError("capture is already running")
        kwargs: dict[str, object] = {
            "iface": interface.network_name,
            "store": False,
            "prn": self._on_packet,
        }
        if bpf_filter and bpf_filter.strip():
            kwargs["filter"] = bpf_filter.strip()

        self._interface = interface
        self._sniffer = AsyncSniffer(**kwargs)
        self._sniffer.start()
        time.sleep(0.15)
        if not self._sniffer.running:
            self._sniffer = None
            raise RuntimeError(
                "抓包线程未能启动，请检查 Npcap、网卡状态和权限。"
            )

    def _on_packet(self, packet: object) -> None:
        try:
            raw = bytes(packet)
            timestamp = float(getattr(packet, "time", time.time()))
            wire_length = int(getattr(packet, "wirelen", len(raw)) or len(raw))
        except Exception:
            return

        try:
            self.queue.put_nowait(
                RawPacket(
                    timestamp=timestamp,
                    data=raw,
                    wire_length=wire_length,
                )
            )
        except queue.Full:
            self.dropped += 1

    def stop(self) -> None:
        if self._sniffer is not None:
            try:
                self._sniffer.stop()
            finally:
                self._sniffer = None
