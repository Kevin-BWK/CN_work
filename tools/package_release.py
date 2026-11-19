"""Assemble the DOC/SRC/BIN submission package.

Run after the report and manual are built and the EXE is rebuilt:
    python tools/package_release.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "网络工程_第19组_A"
REPORT_NAME = f"{NAME}_设计报告.docx"
PACKAGE = ROOT / "build" / "提交包" / NAME
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")

IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".pytest_cache", "*.egg-info", "data", "dist", "build"
)

SRC_FILES = [
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    "build.bat",
    "run.bat",
    "run_console.bat",
    "run_exe.bat",
    "test.bat",
    ".gitignore",
]


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        print(f"missing, skipped: {source}")
        return
    shutil.copytree(source, target, ignore=IGNORE, dirs_exist_ok=True)


def main() -> None:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    for folder in ("DOC", "SRC", "BIN"):
        (PACKAGE / folder).mkdir(parents=True)

    report = ROOT / "docs" / "FlowLens课程设计报告.docx"
    manual = ROOT / "docs" / "FlowLens使用手册.docx"
    if report.exists():
        shutil.copy2(report, PACKAGE / "DOC" / REPORT_NAME)
    else:
        print(f"missing document: {report}")
    if manual.exists():
        shutil.copy2(manual, PACKAGE / "DOC" / manual.name)
    else:
        print(f"missing document: {manual}")

    copy_tree(ROOT / "src", PACKAGE / "SRC" / "src")
    copy_tree(ROOT / "tests", PACKAGE / "SRC" / "tests")
    copy_tree(ROOT / "tools", PACKAGE / "SRC" / "tools")
    (PACKAGE / "SRC" / "docs").mkdir(exist_ok=True)
    for figure in (ROOT / "docs" / "figures").glob("*.drawio"):
        shutil.copy2(figure, PACKAGE / "SRC" / "docs" / figure.name)
    for name in SRC_FILES:
        path = ROOT / name
        if path.exists():
            shutil.copy2(path, PACKAGE / "SRC" / name)

    dist = ROOT / "dist" / "FlowLens"
    if dist.exists():
        shutil.copytree(dist, PACKAGE / "BIN" / "FlowLens", dirs_exist_ok=True)
    else:
        print("missing dist/FlowLens; build first")

    (PACKAGE / "提交说明.txt").write_text(
        "网络工程 第19组（组长：A）\nFlowLens 流镜——网络流量分析系统\n"
        "\n"
        "DOC：课程设计报告、使用手册\n"
        "SRC：源码、测试、构建与运行脚本、draw.io 图源文件\n"
        "BIN：FlowLens 可执行程序目录（需整体复制，另需安装 Npcap）\n"
        "\n"
        "运行：BIN/FlowLens/FlowLens.exe\n"
        "环境：Windows 10/11 64 位 + Npcap 1.10+\n",
        encoding="utf-8",
    )

    archive = PACKAGE.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    if SEVEN_ZIP.exists():
        subprocess.run(
            [str(SEVEN_ZIP), "a", "-tzip", "-mx=5", str(archive), str(PACKAGE)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    else:
        archive = Path(shutil.make_archive(str(PACKAGE), "zip", PACKAGE))

    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"package: {PACKAGE}")
    print(f"archive: {archive} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
