@echo off
setlocal
cd /d "%~dp0"
title Galaxy A3 2017 - Hardware-Firmware
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Diagnose\A3-Diagnose.ps1" -Hardware
set "A3_DIAG_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %A3_DIAG_RESULT%
