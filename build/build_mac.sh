#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
VERSION="1.0.0"

echo "============================================"
echo " Drive Organizer v$VERSION — Build macOS"
echo "============================================"
echo

# Verifica Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "[ERRORE] Python3 non trovato."
    echo "Installa con: brew install python  o da https://python.org"
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
DIST="$ROOT/dist_mac"
rm -rf "$DIST"
mkdir -p "$DIST"

cp "$ROOT/dist/drive-organizer"    "$DIST/"
cp "$ROOT/MANUALE.md"              "$DIST/"
cp "$ROOT/taxonomy_custom.json"    "$DIST/"
cp "$ROOT/.env.example"            "$DIST/"
chmod +x "$DIST/drive-organizer"

# Script di avvio user-friendly (doppio clic da Finder)
cat > "$DIST/Avvia Drive Organizer.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./drive-organizer setup
EOF
chmod +x "$DIST/Avvia Drive Organizer.command"

# LEGGIMI
cat > "$DIST/LEGGIMI.txt" << EOF
============================================
 Drive Organizer v$VERSION — Guida rapida macOS
============================================

PRIMO AVVIO:
  Fai doppio clic su "Avvia Drive Organizer.command"
  oppure apri il Terminale e digita:
    cd /percorso/della/cartella
    ./drive-organizer setup

NOTA macOS: al primo avvio potrebbe apparire un avviso di sicurezza.
  Vai in Impostazioni → Privacy e Sicurezza → clicca "Apri comunque".

COMANDI PRINCIPALI:
  ./drive-organizer setup
  ./drive-organizer status
  ./drive-organizer organize -s type
  ./drive-organizer organize -s type --apply
  ./drive-organizer rollback

Per il manuale completo: MANUALE.md
============================================
EOF

# Pacchetto finale
echo
echo "[4/4] Creazione archivio distribuzione..."
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "Drive Organizer $VERSION" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --hide-extension "drive-organizer" \
        "$ROOT/DriveOrganizer_v${VERSION}_macOS.dmg" \
        "$DIST/"
    echo "DMG creato: DriveOrganizer_v${VERSION}_macOS.dmg"
else
    ZIP="$ROOT/DriveOrganizer_v${VERSION}_macOS.zip"
    cd "$ROOT" && zip -r "$ZIP" dist_mac/ && cd "$SCRIPT_DIR"
    echo "[INFO] create-dmg non trovato — ZIP creato: DriveOrganizer_v${VERSION}_macOS.zip"
    echo "Per il DMG: brew install create-dmg"
fi

echo
echo "============================================"
echo " Build completata!"
echo " Pacchetto: dist_mac/"
echo "============================================"
