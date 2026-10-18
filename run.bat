@echo off
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m packet_analyzer.app
