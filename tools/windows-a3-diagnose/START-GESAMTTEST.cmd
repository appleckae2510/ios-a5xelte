@echo off
setlocal
cd /d "%~dp0"
title Galaxy A3 SM-A320FL - Gesamttest v0.8
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Diagnose\A3-Diagnose.ps1" -Combined
set "A3_BOOTCHECK_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %A3_BOOTCHECK_RESULT%
