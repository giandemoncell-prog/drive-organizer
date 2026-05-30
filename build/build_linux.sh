#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
VERSION="1.0.0"

echo "============================================"
echo " Drive Organizer v$VERSION — Build Linux / Chrome OS"
echo "============================================"
echo

# Verifica Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "[ERRORE] Python3 non trovato."
    echo "Installa con: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo "Python rilevato: $PY_VER"

# Verifica credentials.json
if [ ! -f "$ROOT/credentials.json" ]; then
    echo
    echo "[ERRORE] credentials.json non trovato in: $ROOT"
    echo "Scaricalo da Google Cloud Console → OAuth 2.0 → App Desktop"
    exit 1
fi

# Dipendenze
echo
echo "[1/4] Installazione dipendenze Python..."
python3 -m pip install pyinstaller --quiet --upgrade
python3 -m pip install -r "$ROOT/requirements.txt" --quiet

# Build
echo
echo "[2/4] Build eseguibile con PyInstaller..."
cd "$ROOT"
python3 -m PyInstaller drive_organizer.spec --clean --noconfirm
cd "$SCRIPT_DIR"

if [ ! -f "$ROOT/dist/drive-organizer" ]; then
    echo "[ERRORE] Eseguibile non trovato dopo la build."
    exit 1
fi

# Pacchetto distribuzione
echo
echo "[3/4] Preparazione pacchetto distribuzione..."
DIST="$ROOT/dist_linux"
rm -rf "$DIST"
mkdir -p "$DIST"

cp "$ROOT/dist/drive-organizer"  "$DIST/"
cp "$ROOT/MANUALE.md"            "$DIST/"
cp "$ROOT/taxonomy_custom.json"  "$DIST/"
cp "$ROOT/.env.example"          "$DIST/"
chmod +x "$DIST/drive-organizer"

# Script di installazione sistema
cat > "$DIST/install.sh" << 'INSTALL_EOF'
#!/bin/bash
set -euo pipefail
INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.config/drive-organizer"

echo "============================================"
echo " Drive Organizer — Installazione"
echo "============================================"
echo

mkdir -p "$INSTALL_DIR" "$APP_DIR"

cp drive-organizer "$INSTALL_DIR/"
cp taxonomy_custom.json "$APP_DIR/" 2>/dev/null || true
cp MANUALE.md "$APP_DIR/" 2>/dev/null || true
cp .env.example "$APP_DIR/.env.example" 2>/dev/null || true

# Aggiunge ~/.local/bin al PATH se mancante
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ] && ! grep -q '$HOME/.local/bin' "$RC"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    fi
done

echo
echo "Installazione completata!"
echo
echo "Riapri il terminale e digita:"
echo "  drive-organizer setup"
echo
echo "File di configurazione: $APP_DIR/"
echo "============================================"
INSTALL_EOF
chmod +x "$DIST/install.sh"

# Script di disinstallazione
cat > "$DIST/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
echo "Rimozione Drive Organizer..."
rm -f "$HOME/.local/bin/drive-organizer"
rm -rf "$HOME/.config/drive-organizer"
echo "Drive Organizer rimosso."
UNINSTALL_EOF
chmod +x "$DIST/uninstall.sh"

# LEGGIMI
cat > "$DIST/LEGGIMI.txt" << EOF
============================================
 Drive Organizer v$VERSION — Guida rapida Linux
============================================

INSTALLAZIONE (consigliata):
  Apri il terminale in questa cartella e digita:
    chmod +x install.sh && ./install.sh
  Poi riapri il terminale:
    drive-organizer setup

SENZA INSTALLAZIONE (esegui direttamente):
  ./drive-organizer setup

CHROME OS (Crostini):
  Impostazioni → Sviluppatori → Ambiente Linux → Attiva
  Poi segui le istruzioni di installazione sopra.

COMANDI PRINCIPALI:
  drive-organizer setup
  drive-organizer status
  drive-organizer organize -s type
  drive-organizer organize -s type --apply
  drive-organizer rollback

DISINSTALLAZIONE:
  ./uninstall.sh

Per il manuale completo: MANUALE.md
============================================
EOF

# Pacchetto finale
echo
echo "[4/4] Creazione archivio distribuzione..."
TAR="$ROOT/DriveOrganizer_v${VERSION}_Linux.tar.gz"
tar -czf "$TAR" -C "$DIST" .
echo "Archivio creato: DriveOrganizer_v${VERSION}_Linux.tar.gz"

# AppImage (opzionale)
if command -v appimagetool &>/dev/null; then
    echo "Creazione AppImage..."
    APPDIR="$ROOT/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    cp "$DIST/drive-organizer" "$APPDIR/usr/bin/"

    cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
exec "$APPDIR/usr/bin/drive-organizer" "$@"
APPRUN
    chmod +x "$APPDIR/AppRun"

    cat > "$APPDIR/drive-organizer.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Drive Organizer
Exec=drive-organizer
Type=Application
Categories=Utility;
DESKTOP

    ARCH=$(uname -m) appimagetool "$APPDIR" "$ROOT/DriveOrganizer_v${VERSION}_Linux.AppImage"
    rm -rf "$APPDIR"
    echo "AppImage creata: DriveOrganizer_v${VERSION}_Linux.AppImage"
fi

echo
echo "============================================"
echo " Build completata!"
echo " Pacchetto: dist_linux/"
echo " Archivio:  DriveOrganizer_v${VERSION}_Linux.tar.gz"
echo "============================================"
