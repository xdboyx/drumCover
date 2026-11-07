@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 找不到 .venv，請先照 README 安裝環境。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" tools\editor\server.py --open
if errorlevel 1 pause
