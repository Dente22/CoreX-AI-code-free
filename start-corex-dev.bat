@echo off
REM CoreX dev launcher — hot-reload (Vite + Electron), sync branding before UI dev
setlocal
cd /d "%~dp0"

call "%~dp0_corex-common.bat" :EnsureRoot
if errorlevel 1 exit /b 1

set "COREX_PYTHON=%COREX_ROOT%\.venv\Scripts\python.exe"
if exist "%COREX_PYTHON%" (
  echo [CoreX] Python: %COREX_PYTHON%
) else (
  echo [CoreX] Warning: .venv not found, using system Python
)

call "%~dp0_corex-common.bat" :EnsureFrontendDeps
if errorlevel 1 exit /b 1

call "%~dp0_corex-common.bat" :EnsureAider

set COREX_OPEN_DEVTOOLS=1
echo [CoreX] Dev mode: Vite HMR + Electron...
pushd "%COREX_ROOT%\frontend"
call npm run dev:app
set "EXIT_CODE=%ERRORLEVEL%"
popd
endlocal
exit /b %EXIT_CODE%
