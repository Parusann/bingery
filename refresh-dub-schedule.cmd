@echo off
REM double-click / Task Scheduler wrapper for the Bingery dub refresh.
REM Set BINGERY_ADMIN_SECRET (and optionally BINGERY_URL) first; see the .ps1 header.
powershell -ExecutionPolicy Bypass -File "%~dp0refresh-dub-schedule.ps1" %*
