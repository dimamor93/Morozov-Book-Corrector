@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python.exe"

if not exist "%~dp0server.log" type nul > "%~dp0server.log"

powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ^
  "$p = Start-Process -FilePath '%PYTHON%' -ArgumentList 'run_server.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput '%~dp0server.log' -RedirectStandardError '%~dp0server_error.log' -PassThru; Set-Content '%~dp0server.pid' $p.Id"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ok=$false; for($i=0;$i -lt 40;$i++){ try { $r=Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200){$ok=$true;break} } catch {}; Start-Sleep -Milliseconds 250 }; if($ok){Start-Process 'http://127.0.0.1:8000'} else {Start-Process notepad.exe '%~dp0server_error.log'}"

endlocal
