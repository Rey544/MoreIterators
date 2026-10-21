@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0editor\launch_studio.ps1" -Page appearance
if errorlevel 1 pause
endlocal
