#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rm -f "$HOME/.local/bin/drive-organizer"
rm -rf "$SCRIPT_DIR/.venv"
rm -rf "$HOME/.config/drive-organizer"
echo "Drive Organizer rimosso."
