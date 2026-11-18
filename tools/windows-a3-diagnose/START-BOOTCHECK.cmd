@echo off
setlocal
cd /d "%~dp0"
title Galaxy A3 SM-A320FL - BOOT-Check
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Diagnose\A3-Diagnose.ps1" -BootCheck
set "A3_BOOTCHECK_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %A3_BOOTCHECK_RESULT%
