@echo off
chcp 65001 >nul
echo ============================================
echo  Drive Organizer — Build Windows
echo ============================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato. Installa Python 3.11+ da python.org
    pause
    exit /b 1
)

:: Verifica credentials.json
if not exist "..\credentials.json" (
    echo [ERRORE] credentials.json non trovato nella cartella principale.
    echo Scaricalo da Google Cloud Console e mettilo in Drive Organizer\credentials.json
    pause
    exit /b 1
)

:: Installa dipendenze build
echo Installazione dipendenze...
pip install pyinstaller --quiet
pip install -r ..\requirements.txt --quiet

:: Build
echo.
echo Build in corso (potrebbe richiedere qualche minuto)...
cd ..
pyinstaller drive_organizer.spec --clean --noconfirm
cd build

if errorlevel 1 (
    echo.
    echo [ERRORE] Build fallita. Controlla i messaggi sopra.
    pause
    exit /b 1
)

:: Crea cartella distribuzione
echo.
echo Preparazione pacchetto distribuzione...
if exist "dist_windows" rmdir /s /q "dist_windows"
mkdir "dist_windows"
copy "..\dist\drive-organizer.exe" "dist_windows\"
copy "..\MANUALE.md" "dist_windows\"
copy "..\taxonomy_custom.json" "dist_windows\"
copy "..\assets\icon.ico" "dist_windows\"
copy "..\.env.example" "dist_windows\"

:: Crea LEGGIMI.txt per utenti non tecnici
(
echo ============================================
echo  Drive Organizer — Guida rapida
echo ============================================
echo.
echo PRIMO AVVIO:
echo   1. Fai doppio clic su drive-organizer.exe
echo   2. Si apre il terminale — segui le istruzioni
echo   3. Il browser si aprira' per il login Google
echo.
echo OPPURE apri il Prompt dei comandi in questa cartella e digita:
echo   drive-organizer.exe setup
echo.
echo COMANDI PRINCIPALI:
echo   drive-organizer.exe setup                          — primo avvio guidato
echo   drive-organizer.exe organize --strategy type       — preview per tipo
echo   drive-organizer.exe organize --strategy type --apply  — applica
echo   drive-organizer.exe rollback                       — annulla modifiche
echo.
echo Per il manuale completo apri MANUALE.md
echo ============================================
) > "dist_windows\LEGGIMI.txt"

echo.
echo ============================================
echo  Build completata!
echo  File: build\dist_windows\drive-organizer.exe
echo ============================================
echo.

:: Opzionale: crea installer con Inno Setup se disponibile
where iscc >nul 2>&1
if not errorlevel 1 (
    echo Inno Setup trovato — creazione installer...
    iscc setup.iss
    echo Installer creato: build\DriveOrganizer_Setup.exe
) else (
    echo [INFO] Inno Setup non trovato — solo eseguibile standalone.
    echo Per creare un installer scarica Inno Setup da jrsoftware.org/isinfo.php
)

pause
