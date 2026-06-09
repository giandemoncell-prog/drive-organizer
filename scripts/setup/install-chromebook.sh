#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.config/drive-organizer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Drive Organizer — installazione Chromebook/Linux ==="

sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv ca-certificates

python3 -m venv "$SCRIPT_DIR/.venv"
"$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip -q
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

mkdir -p "$APP_DIR"
cp "$SCRIPT_DIR/taxonomy_custom.json" "$APP_DIR/" 2>/dev/null || true
[ ! -f "$SCRIPT_DIR/.env" ] && cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"

mkdir -p "$INSTALL_DIR"
WRAPPER="$INSTALL_DIR/drive-organizer"
printf '#!/usr/bin/env bash\nsource "%s/.venv/bin/activate"\npython "%s/main.py" "$@"\n' \
    "$SCRIPT_DIR" "$SCRIPT_DIR" > "$WRAPPER"
chmod +x "$WRAPPER"

for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ] && ! grep -q '.local/bin' "$RC"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    fi
done

echo ""
echo "=== Installazione completata! ==="
echo "1. Copia credentials.json in $SCRIPT_DIR/"
echo "   Su ChromeOS: cp /mnt/chromeos/MyFiles/Downloads/credentials.json $SCRIPT_DIR/"
echo "2. Riapri il terminale (o: source ~/.bashrc)"
echo "3. drive-organizer setup && drive-organizer auth"
