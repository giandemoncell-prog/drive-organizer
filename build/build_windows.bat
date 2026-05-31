@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: Cartella radice del progetto (una sopra rispetto a build\)
set "ROOT=%~dp0.."
set "VERSION=1.0.0"

echo ============================================
echo  Drive Organizer v%VERSION% — Build Windows
echo ============================================
echo.

:: Verifica Python 3.11+
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo Installa Python 3.11+ da https://python.org e riprova.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python rilevato: %PY_VER%

:: Verifica credentials.json
if not exist "%ROOT%\credentials.json" (
    echo.
    echo [ERRORE] credentials.json non trovato.
    echo Scaricalo da Google Cloud Console ^> OAuth 2.0 ^> App Desktop
    echo e salvalo in: %ROOT%\credentials.json
    pause
    exit /b 1
)

:: Installa dipendenze
echo.
echo [1/4] Installazione dipendenze Python...
if exist "%ROOT%\pyproject.toml" (
    python -m pip install -e "%ROOT%[dev]" --quiet
) else (
    python -m pip install pyinstaller --quiet --upgrade
    python -m pip install -r "%ROOT%\requirements.txt" --quiet
)
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause
    exit /b 1
)

:: Build PyInstaller
echo.
echo [2/4] Build eseguibile con PyInstaller...
cd /d "%ROOT%"
python -m PyInstaller drive_organizer.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERRORE] Build PyInstaller fallita. Controlla i messaggi sopra.
    cd /d "%~dp0"
    pause
    exit /b 1
)
cd /d "%~dp0"

:: Verifica che l'exe sia stato creato
if not exist "%ROOT%\dist\drive-organizer.exe" (
    echo [ERRORE] drive-organizer.exe non trovato in dist\ dopo la build.
    pause
    exit /b 1
)

:: Pacchetto distribuzione
echo.
echo [3/4] Preparazione pacchetto distribuzione...
set "DIST=%ROOT%\dist_windows"
if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"

copy "%ROOT%\dist\drive-organizer.exe"  "%DIST%\" >nul
copy "%ROOT%\MANUALE.md"               "%DIST%\" >nul
copy "%ROOT%\taxonomy_custom.json"     "%DIST%\" >nul
copy "%ROOT%\assets\icon.ico"          "%DIST%\" >nul
copy "%ROOT%\.env.example"             "%DIST%\" >nul

:: LEGGIMI.txt per utenti non tecnici
(
echo ============================================
echo  Drive Organizer v%VERSION% — Guida rapida
echo ============================================
echo.
echo PRIMO AVVIO:
echo   Fai doppio clic su drive-organizer.exe
echo   oppure apri il Prompt dei comandi qui e digita:
echo     drive-organizer.exe setup
echo.
echo COMANDI PRINCIPALI:
echo   drive-organizer.exe setup                            Prima configurazione guidata
echo   drive-organizer.exe status                           Stato Drive e AI
echo   drive-organizer.exe organize -s type                 Preview organizzazione per tipo
echo   drive-organizer.exe organize -s type --apply         Applica organizzazione
echo   drive-organizer.exe organize -s custom -t taxonomy_custom.json
echo   drive-organizer.exe rename                           Rinomina con AI locale
echo   drive-organizer.exe duplicates                       Trova duplicati
echo   drive-organizer.exe rollback                         Annulla ultima operazione
echo.
echo Per il manuale completo apri MANUALE.md
echo ============================================
) > "%DIST%\LEGGIMI.txt"

:: Installer Inno Setup (opzionale)
echo.
echo [4/4] Creazione installer...
where iscc >nul 2>&1
if not errorlevel 1 (
    iscc "%~dp0setup.iss"
    if not errorlevel 1 (
        echo Installer creato: build\DriveOrganizer_Setup.exe
    ) else (
        echo [AVVISO] Inno Setup ha riportato un errore. Controlla setup.iss.
    )
) else (
    echo [INFO] Inno Setup non trovato — viene prodotto solo il pacchetto zip.
    echo Per il vero installer: https://jrsoftware.org/isinfo.php
    powershell -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%ROOT%\DriveOrganizer_v%VERSION%_Windows.zip' -Force"
    echo ZIP creato: DriveOrganizer_v%VERSION%_Windows.zip
)

echo.
echo ============================================
echo  Build completata!
echo  Pacchetto: dist_windows\
echo  EXE:       dist_windows\drive-organizer.exe
echo ============================================
echo.
pause
endlocal
