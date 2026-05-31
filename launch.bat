@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)
python main.py %*
