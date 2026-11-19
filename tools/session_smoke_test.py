"""End-to-end capture, parse, record and reload smoke test."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packet_analyzer.capture import discover_interfaces
from packet_analyzer.session import CaptureSession, analyze_pcapng


def main() -> None:
    interfaces = discover_interfaces()
    interface = next((item for item in interfaces if item.name == "WLAN"), None)
    if interface is None:
        raise SystemExit("WLAN interface was not found.")

    output = Path("data") / "smoke" / datetime.now().strftime("%Y%m%d_%H%M%S")
    session = CaptureSession()
    session.start(interface, record_dir=output)
    try:
        subprocess.run(
            ["ping", "-n", "4", "10.195.116.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(2)
        snapshot = session.snapshot()
        print(
            f"live: packets={snapshot.stats.total_packets} "
            f"ipv4={snapshot.stats.ipv4_packets} "
            f"ipv6={snapshot.stats.ipv6_packets} "
            f"other={snapshot.stats.other_packets} "
            f"errors={snapshot.stats.parse_errors}"
        )
    finally:
        session.stop()

    snapshot = session.snapshot()
    if not snapshot.segments:
        raise SystemExit("No pcapng segment was created.")

    exported = session.export_recording(output / "session.pcapng")
    loaded, _ = analyze_pcapng(exported)
    print(
        f"reloaded: packets={loaded.total_packets} "
        f"ipv4={loaded.ipv4_packets} "
        f"ipv6={loaded.ipv6_packets} "
        f"other={loaded.other_packets} "
        f"errors={loaded.parse_errors}"
    )
    print(f"segments: {len(snapshot.segments)}")
    print(f"exported: {exported}")

    if loaded.total_packets != snapshot.stats.total_packets:
        raise SystemExit("Reloaded packet count does not match live count.")


if __name__ == "__main__":
    main()
