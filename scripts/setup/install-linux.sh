#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="$HOME/.local/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/drive-organizer" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/drive-organizer"

mkdir -p "$HOME/.config/drive-organizer"
cp "$SCRIPT_DIR/taxonomy_custom.json" "$HOME/.config/drive-organizer/" 2>/dev/null || true

for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ] && ! grep -q '.local/bin' "$RC"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    fi
done

echo "Fatto! Riapri il terminale e digita: drive-organizer setup"
