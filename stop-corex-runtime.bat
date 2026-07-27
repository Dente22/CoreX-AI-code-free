@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Stop CoreX Runtime

cd /d "%~dp0"
set "COREX_ROOT=%CD%"

echo [CoreX] Stopping local runtime...
echo [CoreX] Root: %COREX_ROOT%

rem 1) Stop listeners on CoreX port (11435) with child processes.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":11435 .*LISTENING"') do (
  if not "%%P"=="0" (
    echo [CoreX] Killing PID on 11435: %%P
    taskkill /PID %%P /T /F >nul 2>&1
  )
)

rem 2) Stop CoreX app/python processes launched from this workspace.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = '%COREX_ROOT%';" ^
  "$procs = Get-CimInstance Win32_Process | Where-Object {" ^
  "  (($_.Name -match 'CoreX.exe|electron.exe|python.exe') -and ($_.CommandLine -like ('*' + $root + '*'))) -or" ^
  "  (($_.Name -ieq 'ollama.exe') -and ($_.CommandLine -like '*127.0.0.1:11435*')) -or" ^
  "  (($_.Name -ieq 'llama-server.exe') -and ($_.CommandLine -like ('*' + $root + '*')))" ^
  "};" ^
  "foreach ($p in $procs) {" ^
  "  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Host ('[CoreX] Killed ' + $p.Name + ' PID=' + $p.ProcessId) } catch {}" ^
  "}"

rem 3) Best-effort cleanup of remaining orphan llama-server processes.
taskkill /IM llama-server.exe /F >nul 2>&1

echo [CoreX] Done. Start again: start-corex.bat ^| start-corex-dev.bat
endlocal
