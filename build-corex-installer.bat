@echo off
REM CoreX — сборка установщика Windows (новый логотип в .exe и ярлыках)
setlocal
cd /d "%~dp0"

echo [CoreX] Full installer pipeline: icons ^> NSIS theme ^> dist:win
call "%~dp0_corex-common.bat" :BuildInstaller
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [CoreX] Installer build failed with code %EXIT_CODE%
  pause
  exit /b %EXIT_CODE%
)

echo.
echo [CoreX] Installer ready in frontend\release\
echo [CoreX] Run CoreX-Setup-*.exe to update desktop shortcut icon.
pause
endlocal
exit /b 0
