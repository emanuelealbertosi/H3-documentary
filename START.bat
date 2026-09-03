@echo off
setlocal
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "H3_RESULT=%ERRORLEVEL%"
if not "%H3_RESULT%"=="0" if not defined H3_NO_PAUSE pause
exit /b %H3_RESULT%
