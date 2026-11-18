@echo off
setlocal
cd /d "%~dp0"
title Galaxy A3 2017 - Diagnose v1.1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Diagnose\A3-Diagnose.ps1"
set "A3_DIAG_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %A3_DIAG_RESULT%
