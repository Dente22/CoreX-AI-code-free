@echo off
setlocal
cd /d "%~dp0.."
set "VENV=%CD%\.venv-aider"
set "REQ=%CD%\backend\requirements-aider.txt"

if not defined COREX_AIDER_PYTHON (
  call "%~dp0..\_corex-common.bat" :FindAiderPython
)

if not defined COREX_AIDER_PYTHON (
  echo [CoreX] Нужен Python 3.11 или 3.12 для Aider ^(не 3.13/3.14^).
  echo [CoreX] Запусти start-corex.bat — предложит скачать Python 3.11.
  echo [CoreX] Или вручную: https://www.python.org/downloads/release/python-3119/
  exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
  echo [CoreX] Создаю .venv-aider: %COREX_AIDER_PYTHON%
  "%COREX_AIDER_PYTHON%" -m venv "%VENV%"
  if errorlevel 1 (
    echo [CoreX] Не удалось создать .venv-aider
    exit /b 1
  )
)

echo [CoreX] Ставлю aider-chat в .venv-aider...
"%VENV%\Scripts\python.exe" -m pip install -U pip
"%VENV%\Scripts\python.exe" -m pip install -r "%REQ%"
if errorlevel 1 exit /b 1
echo [CoreX] Aider готов: "%VENV%\Scripts\aider.exe"
exit /b 0
