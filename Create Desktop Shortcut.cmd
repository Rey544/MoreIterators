@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0editor\launch_studio.ps1" -Page appearance -CreateShortcut
if errorlevel 1 pause
endlocal
