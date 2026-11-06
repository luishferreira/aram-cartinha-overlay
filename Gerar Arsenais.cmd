@echo off
cd /d "%~dp0"
python -m tools.items.cli export
pause
