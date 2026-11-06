@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 (
  echo Python com Tkinter nao foi encontrado. Instale o Python e tente novamente.
  pause
  exit /b 1
)
start "" pythonw.exe "%~dp0tools\live\debug_overlay.py"
