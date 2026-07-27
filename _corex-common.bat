@echo off
REM CoreX — общие шаги запуска/сборки (подключать: call "%~dp0_corex-common.bat" :ИмяМетки)

if /i "%~1"==":EnsureRoot" goto EnsureRoot
if /i "%~1"==":EnsureVenv" goto EnsureVenv
if /i "%~1"==":EnsureFrontendDeps" goto EnsureFrontendDeps
if /i "%~1"==":SyncBranding" goto SyncBranding
if /i "%~1"==":WarmupOllama" goto WarmupOllama
if /i "%~1"==":BuildInstaller" goto BuildInstaller
exit /b 1

:EnsureRoot
cd /d "%~dp0"
set "COREX_ROOT=%~dp0"
if "%COREX_ROOT:~-1%"=="\" set "COREX_ROOT=%COREX_ROOT:~0,-1%"
exit /b 0

:EnsureVenv
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)

REM Prefer .venv, then legacy .venv-1
set "COREX_PYTHON=%COREX_ROOT%\.venv\Scripts\python.exe"
if exist "%COREX_PYTHON%" (
  echo [CoreX] Python: %COREX_PYTHON%
  exit /b 0
)

set "COREX_PYTHON=%COREX_ROOT%\.venv-1\Scripts\python.exe"
if exist "%COREX_PYTHON%" (
  echo [CoreX] Python: %COREX_PYTHON% ^(legacy .venv-1^)
  exit /b 0
)

echo [CoreX] Virtual environment not found.
echo [CoreX] Creating .venv and installing backend dependencies...

where py >nul 2>&1
if not errorlevel 1 (
  py -3.13 -m venv "%COREX_ROOT%\.venv"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [CoreX] Python not found. Install Python 3.13+ and retry.
    exit /b 1
  )
  python -m venv "%COREX_ROOT%\.venv"
)
if errorlevel 1 (
  echo [CoreX] Failed to create .venv
  exit /b 1
)

set "COREX_PYTHON=%COREX_ROOT%\.venv\Scripts\python.exe"
if not exist "%COREX_PYTHON%" (
  echo [CoreX] .venv created but python.exe missing: %COREX_PYTHON%
  exit /b 1
)

"%COREX_PYTHON%" -m pip install --upgrade pip
if exist "%COREX_ROOT%\backend\requirements.txt" (
  "%COREX_PYTHON%" -m pip install -r "%COREX_ROOT%\backend\requirements.txt"
)
if exist "%COREX_ROOT%\backend\requirements-dev.txt" (
  "%COREX_PYTHON%" -m pip install -r "%COREX_ROOT%\backend\requirements-dev.txt"
)
if errorlevel 1 (
  echo [CoreX] Dependency install failed.
  exit /b 1
)

echo [CoreX] Python: %COREX_PYTHON%
exit /b 0

:EnsureFrontendDeps
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)
if exist "%COREX_ROOT%\frontend\node_modules\" exit /b 0
echo [CoreX] Installing frontend dependencies...
pushd "%COREX_ROOT%\frontend"
call npm install
set "NPM_CODE=%ERRORLEVEL%"
popd
exit /b %NPM_CODE%

:SyncBranding
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)
echo [CoreX] Neural Forge — sync logo SVG/PNG and Windows .ico...
pushd "%COREX_ROOT%\frontend"
call npm run icons
set "ICON_CODE=%ERRORLEVEL%"
popd
if not "%ICON_CODE%"=="0" (
  echo [CoreX] Icon sync failed with code %ICON_CODE%
  exit /b %ICON_CODE%
)
echo [CoreX] Branding ready: public\corex-logo.*, build\icon.ico
exit /b 0

:WarmupOllama
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)
if not defined COREX_PYTHON (
  call "%~dp0_corex-common.bat" :EnsureVenv
  if errorlevel 1 exit /b 1
)
echo [CoreX] Warming up Ollama server for local AI...
pushd "%COREX_ROOT%\backend"
"%COREX_PYTHON%" scripts\warmup_ollama_server.py
set "OLLAMA_CODE=%ERRORLEVEL%"
popd
if not "%OLLAMA_CODE%"=="0" (
  echo [CoreX] Warning: Ollama warmup failed. Install Ollama from https://ollama.com
)
exit /b 0

:BuildInstaller
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)
call "%~dp0_corex-common.bat" :EnsureVenv
if errorlevel 1 exit /b 1
call "%~dp0_corex-common.bat" :EnsureFrontendDeps
if errorlevel 1 exit /b 1
call "%~dp0_corex-common.bat" :SyncBranding
if errorlevel 1 exit /b 1
echo [CoreX] Preparing NSIS installer theme...
pushd "%COREX_ROOT%\frontend"
call npm run nsis-theme
set "NSIS_CODE=%ERRORLEVEL%"
if not "%NSIS_CODE%"=="0" (
  popd
  exit /b %NSIS_CODE%
)
echo [CoreX] Building Windows installer (dist:win)...
call npm run dist:win
set "DIST_CODE=%ERRORLEVEL%"
popd
exit /b %DIST_CODE%
