@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

if exist "%ROOT%\.venv\Scripts\python.exe" (
    "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\configure.py"
) else (
    python "%ROOT%\scripts\configure.py"
)

endlocal
