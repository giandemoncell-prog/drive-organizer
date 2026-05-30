#!/bin/bash
set -e

echo "============================================"
echo " Drive Organizer — Build Linux / Chrome OS"
echo "============================================"
echo

# Verifica Python
if ! command -v python3 &>/dev/null; then
    echo "[ERRORE] Python3 non trovato."
    echo "Installa con: sudo apt install python3 python3-pip"
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
rm -rf dist_linux
mkdir dist_linux
cp ../dist/drive-organizer dist_linux/
cp ../MANUALE.md dist_linux/
cp ../taxonomy_custom.json dist_linux/
chmod +x dist_linux/drive-organizer

# Script di installazione sistema
cat > dist_linux/install.sh << 'INSTALL_EOF'
#!/bin/bash
set -e
INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.drive-organizer"

mkdir -p "$INSTALL_DIR"
mkdir -p "$APP_DIR"

cp drive-organizer "$INSTALL_DIR/"
cp taxonomy_custom.json "$APP_DIR/"
cp MANUALE.md "$APP_DIR/"

# Aggiungi ~/.local/bin al PATH se non c'è
if ! grep -q '$HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
if ! grep -q '$HOME/.local/bin' "$HOME/.zshrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc" 2>/dev/null || true
fi

echo
echo "============================================"
echo " Drive Organizer installato!"
echo "============================================"
echo
echo "Riapri il terminale e digita:"
echo "  drive-organizer setup"
echo
echo "Per il manuale: $APP_DIR/MANUALE.md"
echo "============================================"
INSTALL_EOF
chmod +x dist_linux/install.sh

# LEGGIMI
cat > dist_linux/LEGGIMI.txt << 'EOF'
============================================
 Drive Organizer — Guida rapida Linux
============================================

INSTALLAZIONE:
  Apri il terminale in questa cartella e digita:
    chmod +x install.sh
    ./install.sh
  Poi riapri il terminale e digita:
    drive-organizer setup

SENZA INSTALLAZIONE (esegui direttamente):
  ./drive-organizer setup

CHROME OS (Linux via Crostini):
  Abilita Linux in Impostazioni > Sviluppatori > Ambiente Linux
  Poi segui le istruzioni sopra dal terminale Linux

COMANDI PRINCIPALI:
  drive-organizer setup                           — primo avvio guidato
  drive-organizer organize --strategy type        — preview per tipo
  drive-organizer organize --strategy type --apply — applica
  drive-organizer rollback                        — annulla modifiche

Per il manuale completo apri MANUALE.md
============================================
EOF

# Crea tar.gz distribuzione
tar -czf DriveOrganizer_linux.tar.gz -C dist_linux .
echo "Archivio creato: build/DriveOrganizer_linux.tar.gz"

# AppImage se appimagetool disponibile
if command -v appimagetool &>/dev/null; then
    echo "Creazione AppImage..."
    mkdir -p AppDir/usr/bin
    cp dist_linux/drive-organizer AppDir/usr/bin/
    cat > AppDir/AppRun << 'APPRUN'
#!/bin/bash
exec "$APPDIR/usr/bin/drive-organizer" "$@"
APPRUN
    chmod +x AppDir/AppRun
    cat > AppDir/drive-organizer.desktop << 'DESKTOP'
[Desktop Entry]
Name=Drive Organizer
Exec=drive-organizer
Type=Application
Categories=Utility;
DESKTOP
    appimagetool AppDir DriveOrganizer.AppImage
    echo "AppImage creata: build/DriveOrganizer.AppImage"
fi

echo
echo "============================================"
echo " Build completata!"
echo " File: build/DriveOrganizer_linux.tar.gz"
echo "============================================"
