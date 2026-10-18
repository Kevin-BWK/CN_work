"""pcapng recording, segmented writing and streamed reading."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Iterator

from scapy.utils import PcapNgReader, PcapNgWriter, PcapReader

from .models import RawPacket


def read_capture(path: str | Path) -> Iterator[RawPacket]:
    """Yield raw Ethernet frames from a pcap/pcapng file without loading it all."""

    reader_class = PcapNgReader if Path(path).suffix.lower() == ".pcapng" else PcapReader
    with reader_class(str(path)) as reader:
        for packet in reader:
            raw = bytes(packet)
            wire_length = int(getattr(packet, "wirelen", len(raw)) or len(raw))
            yield RawPacket(
                timestamp=float(packet.time),
                data=raw,
                wire_length=wire_length,
            )


read_pcapng = read_capture


class PcapNgRecorder:
    """Write captured frames to one or more pcapng segments.

    The writer is intended to be used by a single recorder thread. Segment
    rotation prevents an unbounded file from exhausting the disk during a long
    capture session.
    """

    def __init__(
        self,
        output_dir: str | Path,
        prefix: str = "capture",
        max_segment_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        if max_segment_bytes < 1024 * 1024:
            raise ValueError("max_segment_bytes must be at least 1 MiB")
        self.output_dir = Path(output_dir)
        self.prefix = prefix
        self.max_segment_bytes = max_segment_bytes
        self.segment_paths: list[Path] = []
        self._writer: PcapNgWriter | None = None
        self._segment_bytes = 0
        self._segment_number = 0

    def start(self) -> None:
        if self._writer is not None:
            raise RuntimeError("recorder is already started")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._open_segment()

    def _open_segment(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._segment_number += 1
        path = self.output_dir / (
            f"{self.prefix}_{stamp}_{self._segment_number:04d}.pcapng"
        )
        self._writer = PcapNgWriter(str(path))
        # Explicitly select Ethernet so raw bytes can be written without
        # re-dissecting each frame in the recorder thread.
        self._writer.linktype = 1
        self._writer.write_header(None)
        self.segment_paths.append(path)
        self._segment_bytes = 0

    def write(self, packet: RawPacket) -> None:
        if self._writer is None:
            raise RuntimeError("recorder is not started")
        self._writer.write_packet(
            packet.data,
            sec=packet.timestamp,
            caplen=len(packet.data),
            wirelen=packet.wire_length,
        )
        self._segment_bytes += len(packet.data) + 64
        if self._segment_bytes >= self.max_segment_bytes:
            self._rotate()

    def _rotate(self) -> None:
        if self._writer is not None:
            self._writer.close()
        self._open_segment()

    def stop(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def export_single(
        self,
        destination: str | Path,
        overwrite: bool = False,
    ) -> Path:
        """Merge all segments into one pcapng file."""

        destination = Path(destination)
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if not self.segment_paths:
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            writer = PcapNgWriter(str(temporary))
            writer.linktype = 1
            writer.write_header(None)
            writer.close()
            temporary.replace(destination)
            return destination

        if len(self.segment_paths) == 1:
            shutil.copy2(self.segment_paths[0], destination)
            return destination

        temporary = destination.with_suffix(destination.suffix + ".tmp")
        writer = PcapNgWriter(str(temporary))
        writer.linktype = 1
        writer.write_header(None)
        try:
            for segment in self.segment_paths:
                for packet in read_pcapng(segment):
                    writer.write_packet(
                        packet.data,
                        sec=packet.timestamp,
                        caplen=len(packet.data),
                        wirelen=packet.wire_length,
                    )
        finally:
            writer.close()
        temporary.replace(destination)
        return destination
