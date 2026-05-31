@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"

echo.
echo ============================================
echo  Drive Organizer -- Installazione
echo ============================================
echo.

:: ─── Python ─────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo Installa Python 3.11+ da https://python.org
    echo Spunta "Add Python to PATH" durante l'installazione.
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python !PY_VER! trovato.

:: Verifica >= 3.11
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    if %%a LSS 3 ( echo [ERRORE] Python 3.11+ richiesto. & pause & exit /b 1 )
    if %%a EQU 3 if %%b LSS 11 ( echo [ERRORE] Python 3.11+ richiesto. & pause & exit /b 1 )
)

:: ─── Ambiente virtuale ──────────────────────
echo.
if not exist "!ROOT!\.venv" (
    echo Creazione ambiente virtuale .venv...
    python -m venv "!ROOT!\.venv"
    if errorlevel 1 ( echo [ERRORE] Creazione .venv fallita. & pause & exit /b 1 )
) else (
    echo Ambiente .venv gia' presente.
)

:: ─── Dipendenze ─────────────────────────────
echo.
echo Installazione dipendenze...
call "!ROOT!\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet --disable-pip-version-check

if exist "!ROOT!\pyproject.toml" (
    python -m pip install -e "!ROOT![dev]" --quiet
) else (
    python -m pip install -r "!ROOT!\requirements.txt" --quiet
)
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita. Controlla la connessione.
    pause & exit /b 1
)
echo Dipendenze installate.

:: ─── File .env ──────────────────────────────
echo.
if not exist "!ROOT!\.env" (
    copy "!ROOT!\.env.example" "!ROOT!\.env" >nul
    echo File .env creato da .env.example.
) else (
    echo File .env gia' presente.
)

:: ─── credentials.json ───────────────────────
echo.
if not exist "!ROOT!\credentials.json" (
    echo [AVVISO] credentials.json non trovato.
    echo.
    echo Per usare Drive Organizer devi configurare Google OAuth:
    echo   1. Vai su https://console.cloud.google.com
    echo   2. Crea un progetto ^> abilita "Google Drive API v3"
    echo   3. Credenziali ^> Crea ^> OAuth 2.0 Client ID ^> App desktop
    echo   4. Scarica il JSON, rinominalo "credentials.json"
    echo   5. Copialo in: !ROOT!
    echo.
) else (
    echo credentials.json trovato.
)

:: ─── Riepilogo ──────────────────────────────
echo.
echo ============================================
echo  Installazione completata!
echo ============================================
echo.
if not exist "!ROOT!\credentials.json" (
    echo  [!] Aggiungi credentials.json ^(vedi sopra^)
)
echo  Prossimi passi:
echo    configure.bat            Imposta le API key AI
echo    launch.bat auth          Autentica Google Drive
echo    launch.bat setup         Wizard primo avvio
echo    launch.bat status        Verifica connessione
echo.

set /p DO_CFG="Configurare le API key ora? (S/N): "
if /i "!DO_CFG!"=="S" (
    echo.
    python "!ROOT!\scripts\configure.py"
)

echo.
pause
endlocal
