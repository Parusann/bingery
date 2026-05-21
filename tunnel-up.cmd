@echo off
setlocal
title Bingery Tunnel - Starting
cd /d "%~dp0"
echo === Bingery Tunnel: Start ===
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tunnel.ps1"
echo.
echo === Done ===
pause
