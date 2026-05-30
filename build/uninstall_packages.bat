@echo off
chcp 65001 >nul
echo ============================================
echo  Drive Organizer -- Disinstallazione pacchetti Python
echo ============================================
echo.
echo Questo script rimuove tutti i pacchetti installati
echo da requirements.txt (ambiente di sviluppo).
echo.
echo ATTENZIONE: rimuove solo i pacchetti runtime, non Python stesso.
echo.
set /p CONFIRM="Procedere con la disinstallazione? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo Operazione annullata.
    pause
    exit /b
)
echo.
echo Disinstallazione in corso...
python -m pip uninstall -y ^
    google-api-python-client ^
    google-auth ^
    google-auth-oauthlib ^
    google-auth-httplib2 ^
    anthropic ^
    google-genai ^
    ollama ^
    rich ^
    click ^
    pydantic ^
    pydantic-settings ^
    python-dotenv ^
    requests ^
    httpx ^
    pyinstaller
echo.
echo Pacchetti rimossi.
echo Per reinstallare: python -m pip install -r requirements.txt
echo.
pause
