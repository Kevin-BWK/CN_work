"""Main window for the local network traffic analyzer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time

import psutil
import pyqtgraph as pg
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..capture import InterfaceInfo, discover_interfaces
from ..models import PacketRecord
from ..session import CaptureSession, analyze_pcapng
from ..statistics import StatsSnapshot


pg.setConfigOptions(antialias=True, background="#ffffff", foreground="#475569")


def format_uptime(seconds: float) -> str:
    total = int(max(0, seconds))
    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    prefix = f"{days}天 " if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"


def format_bytes(value: int | float) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class PacketTableModel(QAbstractTableModel):
    HEADERS = (
        "序号",
        "时间",
        "源 MAC",
        "目的 MAC",
        "类型",
        "源 IP",
        "目的 IP",
        "协议",
        "长度",
        "概要",
    )

    def __init__(self) -> None:
        super().__init__()
        self._records: list[PacketRecord] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        record = self._records[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                str(record.index),
                datetime.fromtimestamp(record.timestamp).strftime(
                    "%H:%M:%S.%f"
                )[:-3],
                record.src_mac or "",
                record.dst_mac or "",
                record.ether_type_label,
                record.src_ip or "",
                record.dst_ip or "",
                record.protocol_label,
                record.length_label,
                record.summary,
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return record.summary
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in (0, 8):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and record.parse_error:
            return QColor("#b91c1c")
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def set_records(
        self,
        records: tuple[PacketRecord, ...] | list[PacketRecord],
        force_reset: bool = False,
    ) -> None:
        incoming = list(records)
        reset = (
            force_reset
            or not self._records
            or not incoming
            or incoming[0].index != self._records[0].index
        )
        if reset:
            self.beginResetModel()
            self._records = incoming
            self.endResetModel()
            return

        last_index = self._records[-1].index
        additions = [record for record in incoming if record.index > last_index]
        if additions:
            start = len(self._records)
            self.beginInsertRows(QModelIndex(), start, start + len(additions) - 1)
            self._records.extend(additions)
            self.endInsertRows()

    def record_at(self, row: int) -> PacketRecord | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class DetailTree(QTreeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setHeaderLabels(["字段", "值"])
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def _add(
        parent: QTreeWidgetItem,
        name: str,
        value: object | None,
    ) -> None:
        QTreeWidgetItem(parent, [name, "N/A" if value is None else str(value)])

    def show_record(self, record: PacketRecord | None) -> None:
        self.clear()
        if record is None:
            return

        frame = QTreeWidgetItem([f"Frame {record.index}", ""])
        self.addTopLevelItem(frame)
        self._add(
            frame,
            "捕获时间",
            datetime.fromtimestamp(record.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3],
        )
        self._add(frame, "帧长度", f"{record.frame_length} 字节")
        self._add(frame, "线上长度", f"{record.wire_length} 字节")
        if record.parse_error:
            self._add(frame, "解析错误", record.parse_error)

        ethernet = QTreeWidgetItem(["Ethernet II", ""])
        self.addTopLevelItem(ethernet)
        self._add(ethernet, "源 MAC", record.src_mac)
        self._add(ethernet, "目的 MAC", record.dst_mac)
        self._add(ethernet, "以太网类型", record.ether_type_label)
        if record.vlan_id is not None:
            self._add(ethernet, "VLAN ID", record.vlan_id)

        if record.ip_version in (4, 6):
            network = QTreeWidgetItem(
                [f"IPv{record.ip_version}", ""]
            )
            self.addTopLevelItem(network)
            self._add(network, "版本", record.ip_version)
            self._add(network, "源 IP", record.src_ip)
            self._add(network, "目的 IP", record.dst_ip)
            self._add(
                network,
                "Hop Limit" if record.ip_version == 6 else "TTL",
                record.ttl,
            )
            self._add(network, "协议号", record.protocol_number)
            self._add(network, "IP 总长度", record.ip_length)

        if record.transport_protocol in ("TCP", "UDP"):
            transport = QTreeWidgetItem([record.transport_protocol, ""])
            self.addTopLevelItem(transport)
            self._add(transport, "源端口", record.src_port)
            self._add(transport, "目的端口", record.dst_port)
            if record.transport_protocol == "TCP":
                self._add(transport, "SYN", "是" if record.tcp_syn else "否")
                self._add(transport, "ACK", "是" if record.tcp_ack else "否")
                self._add(transport, "FIN", "是" if record.tcp_fin else "否")
                self._add(transport, "RST", "是" if record.tcp_rst else "否")
        elif record.ip_version in (4, 6):
            transport = QTreeWidgetItem(["传输层", ""])
            self.addTopLevelItem(transport)
            self._add(transport, "端口", "N/A（分片或非 TCP/UDP）")

        self.expandToDepth(1)


class SummaryPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("会话概览")
        self.setMaximumWidth(290)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)
        self.values: dict[str, QLabel] = {}
        for key, label in (
            ("total", "报文总数"),
            ("parsed", "解析成功"),
            ("errors", "解析错误"),
            ("ipv4", "IPv4"),
            ("ipv6", "IPv6"),
            ("other", "其它数据"),
            ("bytes", "累计字节"),
            ("rate", "当前速率"),
            ("cpu", "进程 CPU"),
            ("memory", "进程内存"),
        ):
            value = QLabel("--")
            value.setObjectName("metricValue")
            form.addRow(label, value)
            self.values[key] = value

    def update_stats(self, stats: StatsSnapshot) -> None:
        self.values["total"].setText(f"{stats.total_packets:,}")
        self.values["parsed"].setText(f"{stats.parsed_packets:,}")
        self.values["errors"].setText(f"{stats.parse_errors:,}")
        self.values["ipv4"].setText(f"{stats.ipv4_packets:,}")
        self.values["ipv6"].setText(f"{stats.ipv6_packets:,}")
        self.values["other"].setText(f"{stats.other_packets:,}")
        self.values["bytes"].setText(format_bytes(stats.total_bytes))
        self.values["rate"].setText(f"{stats.packets_per_second:.1f} pkt/s")

    def update_resources(self, cpu_percent: float, rss_mb: float) -> None:
        self.values["cpu"].setText(f"{cpu_percent:.1f}%")
        self.values["memory"].setText(f"{rss_mb:.1f} MB")


class ChartsPanel(QTabWidget):
    def __init__(self) -> None:
        super().__init__()
        self.length_plot = pg.PlotWidget(title="IP 分组长度频次")
        self.length_plot.setLabel("bottom", "IP 分组长度（字节）")
        self.length_plot.setLabel("left", "报文数量")
        self.length_plot.showGrid(x=True, y=True, alpha=0.18)
        self.length_plot.setXRange(0, 1600, padding=0.01)
        self.length_curve = self.length_plot.plot(
            [], [], pen=pg.mkPen("#2563eb", width=2)
        )
        self.length_tab = QWidget()
        length_layout = QVBoxLayout(self.length_tab)
        length_layout.setContentsMargins(8, 8, 8, 8)
        self.full_range = QCheckBox("显示完整长度范围")
        length_layout.addWidget(self.full_range)
        length_layout.addWidget(self.length_plot, 1)

        self.bucket_plot = pg.PlotWidget(title="分组长度分段")
        self.bucket_plot.setLabel("left", "报文数量")
        self.bucket_plot.showGrid(x=True, y=True, alpha=0.18)
        self.bucket_plot.getAxis("bottom").setTicks(
            [[(0, "<=46"), (1, "47-1499"), (2, ">=1500")]]
        )
        self.bucket_tab = QWidget()
        bucket_layout = QVBoxLayout(self.bucket_tab)
        bucket_layout.setContentsMargins(8, 8, 8, 8)
        bucket_layout.addWidget(self.bucket_plot, 1)

        self.protocol_plot = pg.PlotWidget(title="IP 版本与其它数据")
        self.protocol_plot.setLabel("left", "报文数量")
        self.protocol_plot.showGrid(x=True, y=True, alpha=0.18)
        self.protocol_plot.getAxis("bottom").setTicks(
            [[(0, "IPv4"), (1, "IPv6"), (2, "其它")]]
        )
        self.protocol_tab = QWidget()
        protocol_layout = QVBoxLayout(self.protocol_tab)
        protocol_layout.setContentsMargins(8, 8, 8, 8)
        protocol_layout.addWidget(self.protocol_plot, 1)

        self.addTab(self.length_tab, "长度折线图")
        self.addTab(self.bucket_tab, "长度分段")
        self.addTab(self.protocol_tab, "协议分类")

        self.full_range.toggled.connect(self._refresh_length_range)
        self._last_max_length = 1600

    def _refresh_length_range(self) -> None:
        if self.full_range.isChecked():
            self.length_plot.setXRange(
                0, max(1600, self._last_max_length), padding=0.01
            )
        else:
            self.length_plot.setXRange(0, 1600, padding=0.01)

    def update_stats(self, stats: StatsSnapshot) -> None:
        length_map = dict(stats.length_counts)
        self._last_max_length = max(length_map, default=1600)
        dense_lengths = list(range(0, min(self._last_max_length, 65_535) + 1))
        dense_counts = [length_map.get(length, 0) for length in dense_lengths]
        self.length_curve.setData(dense_lengths, dense_counts)
        self._refresh_length_range()

        bucket_values = dict(stats.bucket_counts)
        bucket_heights = [
            bucket_values.get("<=46", 0),
            bucket_values.get("47-1499", 0),
            bucket_values.get(">=1500", 0),
        ]
        self.bucket_plot.clear()
        self.bucket_plot.addItem(
            pg.BarGraphItem(
                x=[0, 1, 2],
                height=bucket_heights,
                width=0.62,
                brush="#0ea5e9",
                pen=pg.mkPen("#0369a1"),
            )
        )
        self.bucket_plot.setYRange(0, max(1, max(bucket_heights) * 1.15))

        protocol_values = [
            stats.ipv4_packets,
            stats.ipv6_packets,
            stats.other_packets,
        ]
        self.protocol_plot.clear()
        self.protocol_plot.addItem(
            pg.BarGraphItem(
                x=[0, 1, 2],
                height=protocol_values,
                width=0.62,
                brush="#22c55e",
                pen=pg.mkPen("#15803d"),
            )
        )
        self.protocol_plot.setYRange(0, max(1, max(protocol_values) * 1.15))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._configure_font()
        self.setWindowTitle("网络流量分析系统 - 计网课程设计")
        self.resize(1380, 860)
        self.setMinimumSize(1080, 700)
        self._session: CaptureSession | None = None
        self._interfaces: list[InterfaceInfo] = []
        self._process = psutil.Process()
        self._process.cpu_percent(None)

        self.table_model = PacketTableModel()
        self.table = QTableView()
        self.details = DetailTree()
        self.summary = SummaryPanel()
        self.charts = ChartsPanel()
        self.interface_combo = QComboBox()
        self.filter_edit = QLineEdit()
        self.start_button = QPushButton("开始抓包")
        self.stop_button = QPushButton("停止")
        self.open_button = QPushButton("打开文件")
        self.export_button = QPushButton("导出 pcapng")
        self.start_button.setObjectName("primary")
        self.stop_button.setObjectName("danger")
        self.uptime_label = QLabel("00:00:00")
        self.status_text = QLabel("就绪")
        self.record_text = QLabel("未开始")
        self.packet_count_label = QLabel("0 条")

        self._build_ui()
        self._apply_style()
        self._load_interfaces()
        self._connect_signals()

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._poll_session)
        self.timer.start()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 8)
        root.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("网卡"))
        self.interface_combo.setMinimumWidth(300)
        controls.addWidget(self.interface_combo, 2)
        controls.addSpacing(8)
        controls.addWidget(QLabel("BPF 过滤"))
        self.filter_edit.setPlaceholderText("可留空，例如 tcp port 443")
        self.filter_edit.setMinimumWidth(210)
        controls.addWidget(self.filter_edit, 1)
        controls.addSpacing(8)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.open_button)
        controls.addWidget(self.export_button)
        controls.addStretch(1)
        controls.addWidget(QLabel("运行时长"))
        self.uptime_label.setObjectName("uptime")
        controls.addWidget(self.uptime_label)
        root.addLayout(controls)

        main_splitter = QSplitter(Qt.Orientation.Vertical)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        table_container = QGroupBox("实时报文")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("最近捕获的报文"))
        table_header.addStretch(1)
        self.packet_count_label.setObjectName("muted")
        table_header.addWidget(self.packet_count_label)
        table_layout.addLayout(table_header)
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table, 1)
        top_splitter.addWidget(table_container)
        top_splitter.addWidget(self.summary)
        top_splitter.setSizes([1050, 270])
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 0)

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        details_group = QGroupBox("字段详情")
        details_layout = QVBoxLayout(details_group)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.addWidget(self.details)
        bottom_splitter.addWidget(details_group)
        bottom_splitter.addWidget(self.charts)
        bottom_splitter.setSizes([430, 850])
        bottom_splitter.setStretchFactor(0, 0)
        bottom_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setSizes([350, 410])
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 1)
        root.addWidget(main_splitter, 1)
        self.setCentralWidget(central)

        self.status_text.setObjectName("statusText")
        self.record_text.setObjectName("muted")
        self.statusBar().addWidget(self.status_text, 1)
        self.statusBar().addPermanentWidget(self.record_text)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f4f7fb; color: #1e293b; }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dbe4ef;
                border-radius: 7px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                min-height: 20px;
            }
            QPushButton:hover { background: #f1f5f9; }
            QPushButton:disabled { color: #94a3b8; background: #f8fafc; }
            QPushButton#primary {
                background: #2563eb; color: white; border-color: #2563eb;
                font-weight: 600;
            }
            QPushButton#primary:hover { background: #1d4ed8; }
            QPushButton#danger {
                background: #dc2626; color: white; border-color: #dc2626;
                font-weight: 600;
            }
            QPushButton#danger:hover { background: #b91c1c; }
            QLineEdit, QComboBox {
                background: white; border: 1px solid #cbd5e1;
                border-radius: 6px; padding: 6px 8px; min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #60a5fa; }
            QTableView, QTreeWidget {
                background: white; alternate-background-color: #f8fafc;
                border: 1px solid #e2e8f0; border-radius: 4px;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
                gridline-color: #eef2f7;
            }
            QHeaderView::section {
                background: #eef4fb; color: #334155; border: none;
                border-right: 1px solid #e2e8f0;
                border-bottom: 1px solid #dbe4ef;
                padding: 6px; font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #dbe4ef; background: white;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #e8eef7; border: 1px solid #dbe4ef;
                padding: 7px 14px; margin-right: 2px;
                border-top-left-radius: 5px; border-top-right-radius: 5px;
            }
            QTabBar::tab:selected { background: white; color: #1d4ed8; }
            QStatusBar { background: #eaf0f7; border-top: 1px solid #dbe4ef; }
            QLabel#muted { color: #64748b; }
            QLabel#uptime {
                font-family: Consolas, "Microsoft YaHei UI";
                font-size: 16px; font-weight: 700; color: #1d4ed8;
                padding: 0 6px;
            }
            QLabel#metricValue { color: #0f172a; font-weight: 600; }
            QLabel#statusText { color: #334155; }
            """
        )
    @staticmethod
    def _configure_font() -> None:
        font_family = "Microsoft YaHei UI"
        font_path = Path("C:/Windows/Fonts/msyh.ttc")
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                font_family = families[0]
        font = QFont(font_family, 9)
        QApplication.instance().setFont(font)

    def _load_interfaces(self) -> None:
        self.interface_combo.clear()
        try:
            self._interfaces = discover_interfaces()
        except Exception as exc:
            self._interfaces = []
            self.status_text.setText(f"网卡枚举失败: {exc}")

        for interface in self._interfaces:
            self.interface_combo.addItem(interface.label, interface)
            self.interface_combo.setItemData(
                self.interface_combo.count() - 1,
                interface.description,
                Qt.ItemDataRole.ToolTipRole,
            )

        preferred = next(
            (
                index
                for index, interface in enumerate(self._interfaces)
                if interface.name == "WLAN" and interface.is_up
            ),
            None,
        )
        if preferred is None:
            preferred = next(
                (
                    index
                    for index, interface in enumerate(self._interfaces)
                    if interface.is_up and interface.addresses
                ),
                0,
            )
        if self._interfaces:
            self.interface_combo.setCurrentIndex(preferred)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button.clicked.connect(self.stop_capture)
        self.open_button.clicked.connect(self.open_file)
        self.export_button.clicked.connect(self.export_recording)
        self.table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(False)

    def start_capture(self) -> None:
        interface = self.interface_combo.currentData()
        if not isinstance(interface, InterfaceInfo):
            QMessageBox.warning(self, "无法开始", "没有可用的网卡。")
            return

        if self._session is not None and self._session.running:
            return

        record_dir = (
            Path("data")
            / "sessions"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        session = CaptureSession()
        try:
            session.start(
                interface,
                bpf_filter=self.filter_edit.text().strip(),
                record_dir=record_dir,
            )
        except Exception as exc:
            QMessageBox.critical(self, "抓包失败", str(exc))
            return

        self._session = session
        self.table_model.set_records([], force_reset=True)
        self.details.show_record(None)
        self.charts.update_stats(
            session.snapshot(recent_limit=0).stats
        )
        self.interface_combo.setEnabled(False)
        self.filter_edit.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.export_button.setEnabled(False)
        self.status_text.setText(f"正在抓包：{interface.name}")
        self.record_text.setText(f"记录目录：{record_dir}")
        self.uptime_label.setText("00:00:00")

    def stop_capture(self) -> None:
        if self._session is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._session.stop()
        finally:
            QApplication.restoreOverrideCursor()

        snapshot = self._session.snapshot()
        self._apply_snapshot(snapshot.stats, snapshot.recent)
        self.interface_combo.setEnabled(True)
        self.filter_edit.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(bool(snapshot.segments))
        self.status_text.setText("抓包已停止")
        self.record_text.setText(
            f"{len(snapshot.segments)} 个 pcapng 分段"
            if snapshot.segments
            else "未记录原始报文"
        )

    def _poll_session(self) -> None:
        if self._session is None:
            return
        snapshot = self._session.snapshot()
        self._apply_snapshot(snapshot.stats, snapshot.recent)
        self.uptime_label.setText(format_uptime(snapshot.uptime_seconds))
        self.packet_count_label.setText(f"{snapshot.stats.total_packets:,} 条")
        if snapshot.running:
            self.record_text.setText(
                f"记录中 · 队列 {snapshot.queue_depth:,} · 丢包 "
                f"{snapshot.queue_dropped + snapshot.record_dropped:,}"
            )
        else:
            self.record_text.setText(
                f"{len(snapshot.segments)} 个 pcapng 分段"
                if snapshot.segments
                else "未记录原始报文"
            )
        if snapshot.last_error:
            self.status_text.setText(snapshot.last_error)

    def _apply_snapshot(
        self,
        stats: StatsSnapshot,
        records: tuple[PacketRecord, ...] | list[PacketRecord],
    ) -> None:
        self.table_model.set_records(records)
        self.summary.update_stats(stats)
        self.charts.update_stats(stats)
        cpu = self._process.cpu_percent(None)
        rss_mb = self._process.memory_info().rss / (1024 * 1024)
        self.summary.update_resources(cpu, rss_mb)
        self.packet_count_label.setText(f"{stats.total_packets:,} 条")
        if (
            not self.table.currentIndex().isValid()
            and self.table_model.rowCount() > 0
        ):
            self.table.selectRow(self.table_model.rowCount() - 1)

    def _on_current_row_changed(
        self,
        current: QModelIndex,
        previous: QModelIndex,
    ) -> None:
        del previous
        self.details.show_record(self.table_model.record_at(current.row()))

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开抓包文件",
            str(Path("data")),
            "Capture files (*.pcapng *.pcap);;All files (*)",
        )
        if not path:
            return
        if self._session is not None and self._session.running:
            self.stop_capture()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            stats, records = analyze_pcapng(path, max_recent=50_000)
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._session = None
        self.table_model.set_records(records, force_reset=True)
        if records:
            self.table.selectRow(0)
        else:
            self.details.show_record(None)
        self.summary.update_stats(stats)
        self.charts.update_stats(stats)
        self.packet_count_label.setText(f"{stats.total_packets:,} 条")
        self.status_text.setText(f"已加载：{path}")
        self.record_text.setText("文件回放模式")
        duration = 0.0
        if stats.first_timestamp is not None and stats.last_timestamp is not None:
            duration = max(0.0, stats.last_timestamp - stats.first_timestamp)
        self.uptime_label.setText(format_uptime(duration))
        self.export_button.setEnabled(False)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def export_recording(self) -> None:
        if self._session is None:
            QMessageBox.information(self, "无法导出", "当前没有抓包会话。")
            return
        snapshot = self._session.snapshot(recent_limit=0)
        if not snapshot.segments:
            QMessageBox.information(self, "无法导出", "当前会话没有记录数据。")
            return

        default_path = (
            Path("data")
            / "exports"
            / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pcapng"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为单个 pcapng",
            str(default_path),
            "pcapng (*.pcapng)",
        )
        if not path:
            return
        try:
            exported = self._session.export_recording(path, overwrite=True)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.status_text.setText(f"已导出：{exported}")

    def closeEvent(self, event) -> None:
        if self._session is not None and self._session.running:
            self._session.stop()
        event.accept()
