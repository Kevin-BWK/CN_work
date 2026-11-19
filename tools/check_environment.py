"""Check the Windows runtime used by the packet analyzer."""

from __future__ import annotations

import os
import platform
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import psutil
import pyqtgraph
import scapy
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication
from scapy.all import conf


def main() -> None:
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"Scapy: {scapy.__version__}")
    print(f"psutil: {psutil.__version__}")
    print(f"pyqtgraph: {pyqtgraph.__version__}")
    print(f"Qt: {QtCore.qVersion()}")

    app = QApplication([])
    print(f"Qt platform: {app.platformName()}")
    print(f"Monitors: {len(app.screens())}")
    print(f"Use pcap: {conf.use_pcap}")

    print("Interfaces:")
    for iface in conf.ifaces.values():
        description = getattr(iface, "description", "") or ""
        network_name = getattr(iface, "network_name", "") or ""
        mac = getattr(iface, "mac", "") or ""
        ips = getattr(iface, "ips", {}) or {}
        addresses = ", ".join(str(address) for address in ips.values())
        print(
            f"  name={iface.name!r} description={description!r} "
            f"network_name={network_name!r} mac={mac!r} ips={addresses!r}"
        )


if __name__ == "__main__":
    main()
