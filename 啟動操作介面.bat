@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 找不到 .venv，請先照 README 安裝環境。
  pause
  exit /b 1
)
if not exist "tools\editor\web\dist\index.html" (
  echo 第一次使用：建置前端介面（需要幾分鐘）...
  where npm >nul 2>nul
  if errorlevel 1 (
    echo 找不到 npm，請先安裝 Node.js（https://nodejs.org），安裝後重新執行這個檔案。
    pause
    exit /b 1
  )
  pushd "tools\editor\web"
  call npm install
  if errorlevel 1 goto buildfail
  call npm run build
  if errorlevel 1 goto buildfail
  popd
)
".venv\Scripts\python.exe" tools\editor\server.py --open
if errorlevel 1 pause
exit /b 0

:buildfail
popd
echo 前端建置失敗，請看上面的錯誤訊息。
pause
exit /b 1
