@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"

echo.
echo ============================================
echo  Drive Organizer -- Disinstallazione
echo ============================================
echo.
echo Rimuove l'ambiente locale. Non tocca Python
echo ne' i file sorgente del progetto.
echo.

:: ─── Inventario ─────────────────────────────
set HAS_VENV=0
set HAS_TOKENS=0
set HAS_LOGS=0
set HAS_ENV=0

if exist "!ROOT!\.venv"   set HAS_VENV=1
if exist "!ROOT!\tokens"  set HAS_TOKENS=1
if exist "!ROOT!\logs"    set HAS_LOGS=1
if exist "!ROOT!\.env"    set HAS_ENV=1

if !HAS_VENV!==0 if !HAS_TOKENS!==0 if !HAS_LOGS!==0 if !HAS_ENV!==0 (
    echo Niente da rimuovere.
    pause & exit /b 0
)

echo Componenti presenti:
if !HAS_VENV!==1    echo   .venv\    (ambiente virtuale Python)
if !HAS_TOKENS!==1  echo   tokens\   (token autenticazione Google)
if !HAS_LOGS!==1    echo   logs\     (log operazioni e rollback)
if !HAS_ENV!==1     echo   .env      (configurazione API key)
echo.

:: ─── Selezione ──────────────────────────────
set REMOVE_VENV=N
set REMOVE_TOKENS=N
set REMOVE_LOGS=N
set REMOVE_ENV=N

if !HAS_VENV!==1    set /p REMOVE_VENV="Rimuovere .venv\? (S/N): "
if !HAS_TOKENS!==1  set /p REMOVE_TOKENS="Rimuovere tokens\? (S/N): "
if !HAS_LOGS!==1    set /p REMOVE_LOGS="Rimuovere logs\? (S/N): "
if !HAS_ENV!==1     set /p REMOVE_ENV="Rimuovere .env? (S/N): "
echo.

:: ─── Rimozione ──────────────────────────────
set REMOVED=0

if /i "!REMOVE_VENV!"=="S" (
    if exist "!ROOT!\.venv" (
        rmdir /s /q "!ROOT!\.venv"
        echo Rimosso: .venv\
        set REMOVED=1
    )
)
if /i "!REMOVE_TOKENS!"=="S" (
    if exist "!ROOT!\tokens" (
        rmdir /s /q "!ROOT!\tokens"
        echo Rimosso: tokens\
        set REMOVED=1
    )
)
if /i "!REMOVE_LOGS!"=="S" (
    if exist "!ROOT!\logs" (
        rmdir /s /q "!ROOT!\logs"
        echo Rimosso: logs\
        set REMOVED=1
    )
)
if /i "!REMOVE_ENV!"=="S" (
    if exist "!ROOT!\.env" (
        del /q "!ROOT!\.env"
        echo Rimosso: .env
        set REMOVED=1
    )
)

echo.
if !REMOVED!==1 (
    echo Fatto. Per reinstallare: install.bat
) else (
    echo Nessuna modifica effettuata.
)
echo.
pause
endlocal
