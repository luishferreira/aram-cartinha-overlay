@echo off
cd /d "%~dp0"
start "" pythonw.exe "%~dp0tools\live\debug_overlay.py" --demo --seconds 30
