@echo off
REM Silent launcher for the Bingery Tunnel GUI. Double-click this file
REM (or pin it to your taskbar / Start menu) to open the control panel.
REM
REM The "start """ + -WindowStyle Hidden combo prevents the PowerShell
REM host console from appearing alongside the WinForms window.

start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tunnel-gui.ps1"
