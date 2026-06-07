#!/bin/bash
# Install Odysseus as a desktop app on Linux (KDE/GNOME).
#
#   scripts/install-linux-app.sh
#
# Adds an "Odysseus" entry to your application menu that opens the app in its own
# window. User-level only (~/.local/share) — no sudo, fully reversible with
# scripts/install-linux-app.sh --uninstall.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP="$APPS_DIR/odysseus.desktop"
LAUNCHER="$REPO_DIR/scripts/odysseus-app.sh"
ICON="$REPO_DIR/static/odysseus-icon.svg"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$DESKTOP"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" 2>/dev/null || true
  echo "Removed $DESKTOP"
  exit 0
fi

chmod +x "$LAUNCHER"
mkdir -p "$APPS_DIR"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Odysseus
GenericName=Private AI
Comment=Your private, local-first AI — chat, agents, research
Exec=$LAUNCHER
Icon=$ICON
Terminal=false
Categories=Utility;
Keywords=AI;assistant;chat;agent;LLM;
StartupWMClass=Odysseus
StartupNotify=true
EOF

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "Installed Odysseus app launcher:"
echo "  $DESKTOP"
echo "  → launches: $LAUNCHER"
echo "Find 'Odysseus' in your application menu (or pin it to the taskbar)."
