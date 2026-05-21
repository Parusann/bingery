@echo off
setlocal
title Bingery Tunnel - Stopping
cd /d "%~dp0"
echo === Bingery Tunnel: Stop ===
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1" -Stop
echo.
echo === Done ===
pause
