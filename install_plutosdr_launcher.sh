#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${DESKTOP_DIR:-$HOME/.local/share/applications}"
DESKTOP_FILE="$DESKTOP_DIR/urh-plutosdr.desktop"

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=PlutoSDR Protocol Tool
Comment=Учебный PlutoSDR-проект Никиты Гурачевского, ИА-232
Exec=$ROOT_DIR/run_plutosdr.sh
Icon=$ROOT_DIR/data/icons/appicon.png
Terminal=false
Categories=Development;Science;HamRadio;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed launcher: $DESKTOP_FILE"
