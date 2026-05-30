@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo  Drive Organizer — Setup Ambiente di Sviluppo
echo ============================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo Installa Python 3.11+ da https://python.org
    echo Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python rilevato: %PY_VER%

:: Crea venv se non esiste
if not exist ".venv" (
    echo.
    echo Creazione ambiente virtuale .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRORE] Creazione venv fallita.
        pause
        exit /b 1
    )
    echo Ambiente virtuale creato.
) else (
    echo Ambiente virtuale .venv gia' presente.
)

:: Attiva venv e installa dipendenze
echo.
echo Installazione dipendenze in .venv...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause
    exit /b 1
)

:: Copia .env se non esiste
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo File .env creato da .env.example — aggiorna le API key se necessario.
)

echo.
echo ============================================
echo  Setup completato!
echo ============================================
echo.
echo Per avviare Drive Organizer in ambiente di sviluppo:
echo   .venv\Scripts\activate
echo   python main.py setup
echo.
echo Per il build EXE Windows:
echo   build\build_windows.bat
echo.
pause
endlocal
