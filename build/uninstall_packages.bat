@echo off
echo ============================================
echo  Drive Organizer -- Disinstallazione pacchetti
echo ============================================
echo.
echo Questo script rimuove tutti i pacchetti Python
echo installati da requirements.txt.
echo.
set /p CONFIRM="Procedere? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo Annullato.
    pause
    exit /b
)
echo.
echo Disinstallazione in corso...
pip uninstall -y ^
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
    httpx
echo.
echo Pacchetti rimossi.
echo Per reinstallare: pip install -r requirements.txt
pause
