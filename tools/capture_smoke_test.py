"""Capture a few real packets through Npcap and print protocol summaries."""

from __future__ import annotations

import subprocess
import time

from scapy.all import AsyncSniffer, conf


def main() -> None:
    iface = conf.ifaces.dev_from_name("WLAN")
    if iface is None:
        raise SystemExit("WLAN interface was not found.")

    sniffer = AsyncSniffer(iface=iface.network_name, store=True)
    sniffer.start()
    try:
        subprocess.run(
            ["ping", "-n", "4", "10.195.116.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(2)
    finally:
        packets = sniffer.stop()

    print(f"Captured {len(packets)} packets on {iface.name}.")
    for packet in packets[:10]:
        print(packet.summary())

    if not packets:
        raise SystemExit("No packets were captured.")


if __name__ == "__main__":
    main()
