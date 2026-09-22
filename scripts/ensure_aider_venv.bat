@echo off
setlocal
cd /d "%~dp0.."
set "VENV=%CD%\.venv-aider"
set "REQ=%CD%\backend\requirements-aider.txt"

where py >nul 2>&1
if errorlevel 1 (
  echo [CoreX] Нужен launcher py и Python 3.11 или 3.12 для Aider.
  exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
  echo [CoreX] Создаю .venv-aider на Python 3.11...
  py -3.11 -m venv "%VENV%" 2>nul
  if errorlevel 1 (
    echo [CoreX] Пробую Python 3.12...
    py -3.12 -m venv "%VENV%" 2>nul
  )
  if errorlevel 1 (
    echo [CoreX] Не найден Python 3.11/3.12. Поставь с python.org ^(3.11^) и повтори.
    exit /b 1
  )
)

echo [CoreX] Ставлю aider-chat в .venv-aider...
"%VENV%\Scripts\python.exe" -m pip install -U pip
"%VENV%\Scripts\python.exe" -m pip install -r "%REQ%"
if errorlevel 1 exit /b 1
echo [CoreX] Aider готов: "%VENV%\Scripts\aider.exe"
exit /b 0
