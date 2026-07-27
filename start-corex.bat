@echo off

REM CoreX — основной запуск (splash сразу, backend после анимации)

setlocal

cd /d "%~dp0"



call "%~dp0_corex-common.bat" :EnsureRoot

if errorlevel 1 goto Fail

set "COREX_ROOT=%CD%"



call "%~dp0_corex-common.bat" :EnsureVenv

if errorlevel 1 goto FailPause



call "%~dp0_corex-common.bat" :EnsureFrontendDeps

if errorlevel 1 goto FailPause



echo [CoreX] Starting CoreX...

echo [CoreX] Root: %COREX_ROOT%

pushd "%COREX_ROOT%\frontend"



if not exist "dist\index.html" (

  echo [CoreX] First run: building UI...

  call npm run icons

  if errorlevel 1 (

    echo [CoreX] Warning: icons step failed, continuing with build...

  )

  call npm run build

  if errorlevel 1 goto FailPausePopd

)



call npm run start:dev

set "EXIT_CODE=%ERRORLEVEL%"

popd



if not "%EXIT_CODE%"=="0" goto FailPause

endlocal

exit /b 0



:FailPausePopd

popd

goto FailPause



:FailPause

echo [CoreX] Launch failed.

pause

exit /b 1



:Fail

exit /b 1

