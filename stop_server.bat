@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0server.pid" (
  for /f "usebackq delims=" %%P in ("%~dp0server.pid") do taskkill /PID %%P /T /F >nul 2>&1
  del "%~dp0server.pid" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_server.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

endlocal
