@echo off
cd /d "%~dp0"
".venv\Scripts\pyinstaller.exe" --noconfirm --windowed --name FlowLens --paths src src\packet_analyzer\app.py
