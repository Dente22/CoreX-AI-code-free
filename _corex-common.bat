@echo off
REM CoreX — общие шаги запуска/сборки (подключать: call "%~dp0_corex-common.bat" :ИмяМетки)

if /i "%~1"==":EnsureRoot" goto EnsureRoot
if /i "%~1"==":EnsureVenv" goto EnsureVenv
if /i "%~1"==":EnsureAider" goto EnsureAider
if /i "%~1"==":FindAiderPython" goto FindAiderPython
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
    echo [CoreX] Python не найден — установку 3.11 предложит загрузочный экран для Aider.
    exit /b 0
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

:EnsureAider
if not defined COREX_ROOT (
  call "%~dp0_corex-common.bat" :EnsureRoot
)
if exist "%COREX_ROOT%\.venv-aider\Scripts\aider.exe" (
  echo [CoreX] Aider: %COREX_ROOT%\.venv-aider\Scripts\aider.exe
  exit /b 0
)
echo [CoreX] Aider sidecar пока нет — предложение скачать будет на загрузочном экране.
exit /b 0

:FindAiderPython
set "COREX_AIDER_PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "COREX_AIDER_PYTHON=%%I"
  if not defined COREX_AIDER_PYTHON (
    for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "COREX_AIDER_PYTHON=%%I"
  )
  if not defined COREX_AIDER_PYTHON (
    for /f "delims=" %%I in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do set "COREX_AIDER_PYTHON=%%I"
  )
)
if not defined COREX_AIDER_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "COREX_AIDER_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined COREX_AIDER_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "COREX_AIDER_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined COREX_AIDER_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "COREX_AIDER_PYTHON=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined COREX_AIDER_PYTHON if exist "%ProgramFiles%\Python311\python.exe" set "COREX_AIDER_PYTHON=%ProgramFiles%\Python311\python.exe"
if not defined COREX_AIDER_PYTHON if exist "%ProgramFiles%\Python312\python.exe" set "COREX_AIDER_PYTHON=%ProgramFiles%\Python312\python.exe"
if not defined COREX_AIDER_PYTHON if exist "%ProgramFiles%\Python310\python.exe" set "COREX_AIDER_PYTHON=%ProgramFiles%\Python310\python.exe"
if not defined COREX_AIDER_PYTHON if exist "C:\Python311\python.exe" set "COREX_AIDER_PYTHON=C:\Python311\python.exe"
if defined COREX_AIDER_PYTHON if not exist "%COREX_AIDER_PYTHON%" set "COREX_AIDER_PYTHON="
if defined COREX_AIDER_PYTHON exit /b 0
exit /b 1

:OfferPython311
echo.
echo [CoreX] Для Aider нужен отдельный Python 3.11 ^(или 3.12^).
echo [CoreX] Основной .venv CoreX может быть 3.13/3.14 — пакет aider-chat туда не ставится.
echo [CoreX] Сейчас Python 3.11/3.12 не найден.
choice /C YN /N /M "[CoreX] Скачать и установить Python 3.11.9 с python.org? [Y=да / N=нет] "
if errorlevel 2 exit /b 1
call :InstallPython311
if errorlevel 1 exit /b 1
call :FindAiderPython
if defined COREX_AIDER_PYTHON exit /b 0
echo [CoreX] Python 3.11 установлен, но этот терминал его ещё не видит.
echo [CoreX] Закрой окно и снова запусти start-corex.bat.
exit /b 1

:InstallPython311
set "COREX_PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "COREX_PY_SETUP=%TEMP%\corex-python-3.11.9-amd64.exe"
where winget >nul 2>&1
if not errorlevel 1 (
  echo [CoreX] Пробую winget: Python.Python.3.11 ...
  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
  if not errorlevel 1 (
    call :RefreshAiderPythonPath
    call :FindAiderPython
    if defined COREX_AIDER_PYTHON exit /b 0
  )
  echo [CoreX] winget не дал Python 3.11 — качаю установщик.
)
echo [CoreX] Скачиваю Python 3.11.9 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri $env:COREX_PY_URL -OutFile $env:COREX_PY_SETUP -UseBasicParsing } catch { Write-Host $_; exit 1 }"
if errorlevel 1 (
  echo [CoreX] Скачать не удалось. Открываю страницу установки в браузере.
  start "" "https://www.python.org/downloads/release/python-3119/"
  echo [CoreX] Нужен Windows installer 64-bit, галка "Add python.exe to PATH".
  exit /b 1
)
echo [CoreX] Запускаю установщик ^(Add to PATH включён^)...
"%COREX_PY_SETUP%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
  echo [CoreX] Установщик Python вернул ошибку.
  start "" "https://www.python.org/downloads/release/python-3119/"
  exit /b 1
)
call :RefreshAiderPythonPath
exit /b 0

:RefreshAiderPythonPath
set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Launcher;%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;%PATH%"
exit /b 0

:OfferAiderInstall
if exist "%COREX_ROOT%\.venv-aider\Scripts\aider.exe" exit /b 0
echo.
echo [CoreX] Aider не найден ^(нужен sidecar .venv-aider, не основной .venv^).
choice /C YN /N /M "[CoreX] Скачать и поставить aider-chat сейчас? [Y=да / N=нет] "
if errorlevel 2 (
  echo [CoreX] Aider пропущен. В чате можно выбрать движок CoreX.
  echo [CoreX] Позже: scripts\ensure_aider_venv.bat
  exit /b 0
)
echo [CoreX] Ставлю Aider в .venv-aider...
call "%COREX_ROOT%\scripts\ensure_aider_venv.bat"
if errorlevel 1 (
  echo [CoreX] Aider не установился. CoreX запустится, режим Aider пока недоступен.
  exit /b 0
)
if exist "%COREX_ROOT%\.venv-aider\Scripts\aider.exe" (
  echo [CoreX] Aider: %COREX_ROOT%\.venv-aider\Scripts\aider.exe
)
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
