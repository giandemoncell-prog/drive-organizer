#!/bin/bash
set -e

echo "============================================"
echo " Drive Organizer — Build macOS"
echo "============================================"
echo

# Verifica Python
if ! command -v python3 &>/dev/null; then
    echo "[ERRORE] Python3 non trovato. Installa da python.org o con: brew install python"
    exit 1
fi

# Verifica credentials.json
if [ ! -f "../credentials.json" ]; then
    echo "[ERRORE] credentials.json non trovato."
    echo "Scaricalo da Google Cloud Console e mettilo in Drive_Organizer/credentials.json"
    exit 1
fi

# Dipendenze build
echo "Installazione dipendenze..."
pip3 install pyinstaller --quiet
pip3 install -r ../requirements.txt --quiet

# Build
echo
echo "Build in corso..."
cd ..
pyinstaller drive_organizer.spec --clean --noconfirm
cd build

# Pacchetto distribuzione
echo
echo "Preparazione pacchetto..."
rm -rf dist_mac
mkdir dist_mac
cp ../dist/drive-organizer dist_mac/
cp ../MANUALE.md dist_mac/
cp ../taxonomy_custom.json dist_mac/
chmod +x dist_mac/drive-organizer

# Script di avvio user-friendly
cat > dist_mac/Avvia\ Drive\ Organizer.command << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./drive-organizer setup
EOF
chmod +x "dist_mac/Avvia Drive Organizer.command"

# LEGGIMI
cat > dist_mac/LEGGIMI.txt << 'EOF'
============================================
 Drive Organizer — Guida rapida macOS
============================================

PRIMO AVVIO:
  Fai doppio clic su "Avvia Drive Organizer.command"
  oppure apri il Terminale e digita:
    cd /percorso/della/cartella
    ./drive-organizer setup

COMANDI PRINCIPALI:
  ./drive-organizer setup                           — primo avvio guidato
  ./drive-organizer organize --strategy type        — preview per tipo
  ./drive-organizer organize --strategy type --apply — applica
  ./drive-organizer rollback                        — annulla modifiche

NOTA macOS: al primo avvio potrebbe apparire un avviso di sicurezza.
  Vai in Preferenze di Sistema > Privacy e Sicurezza e clicca "Apri comunque".

Per il manuale completo apri MANUALE.md
============================================
EOF

# Crea DMG se create-dmg è disponibile
if command -v create-dmg &>/dev/null; then
    echo "Creazione DMG..."
    create-dmg \
        --volname "Drive Organizer" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --hide-extension "drive-organizer" \
        "DriveOrganizer.dmg" \
        "dist_mac/"
    echo "DMG creato: build/DriveOrganizer.dmg"
else
    echo "[INFO] create-dmg non trovato — solo cartella dist_mac/."
    echo "Installa con: brew install create-dmg"
    # Crea ZIP come alternativa
    zip -r DriveOrganizer_mac.zip dist_mac/
    echo "Archivio creato: build/DriveOrganizer_mac.zip"
fi

echo
echo "============================================"
echo " Build completata!"
echo " File: build/dist_mac/drive-organizer"
echo "============================================"
