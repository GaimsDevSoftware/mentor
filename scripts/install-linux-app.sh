#!/bin/bash
# Install Mentor as a desktop app on Linux (KDE Plasma / GNOME).
#
#   scripts/install-linux-app.sh
#
# Adds a "Mentor" entry to your application menu that opens the app in its own
# window, with a proper icon installed into your icon theme so Plasma's
# taskmanager picks it up reliably — not just an absolute Icon= path, which the
# Chrome --app window's WM_ICON otherwise overrides with the page favicon.
# User-level (~/.local), no sudo. Uninstall: scripts/install-linux-app.sh --uninstall
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons/hicolor"
DESKTOP="$APPS_DIR/mentor.desktop"
LAUNCHER="$REPO_DIR/scripts/odysseus-app.sh"
ICON_SRC="$REPO_DIR/static/mentor-icon.png"

# Sizes Plasma / GTK actually look up.
ICON_SIZES=(16 22 24 32 48 64 96 128 192 256 512)

refresh_caches() {
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" 2>/dev/null || true
  command -v gtk-update-icon-cache  >/dev/null 2>&1 && gtk-update-icon-cache  -f -t "$ICONS_DIR" 2>/dev/null || true
  # KDE Plasma sycoca rebuild — picks up the new .desktop + icons live.
  command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental 2>/dev/null || true
  command -v kbuildsycoca5 >/dev/null 2>&1 && kbuildsycoca5 --noincremental 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$DESKTOP"
  for s in "${ICON_SIZES[@]}"; do
    rm -f "$ICONS_DIR/${s}x${s}/apps/mentor.png"
  done
  rm -f "$ICONS_DIR/scalable/apps/mentor.png"
  refresh_caches
  echo "Removed Mentor app launcher + icon-theme entries."
  exit 0
fi

if [ ! -f "$ICON_SRC" ]; then
  echo "Icon missing: $ICON_SRC — aborting." >&2
  exit 1
fi

chmod +x "$LAUNCHER"
mkdir -p "$APPS_DIR"

# Install the icon at every common size in the hicolor theme so KDE Plasma can
# look it up by NAME (`Icon=mentor`). Resize with whatever's available.
echo "Installing icon into the hicolor theme…"
if command -v magick >/dev/null 2>&1; then
  resizer() { magick "$ICON_SRC" -resize "${1}x${1}" -strip "$2"; }
elif command -v convert >/dev/null 2>&1; then
  resizer() { convert "$ICON_SRC" -resize "${1}x${1}" -strip "$2"; }
elif "$REPO_DIR/venv/bin/python" -c "import PIL" 2>/dev/null; then
  resizer() {
    "$REPO_DIR/venv/bin/python" - "$ICON_SRC" "$1" "$2" <<'PY'
import sys
from PIL import Image
src, size, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
Image.open(src).resize((size, size), Image.LANCZOS).save(out)
PY
  }
else
  echo "No image resizer (need ImageMagick or app venv with Pillow). Copying 1024 icon for every size — Plasma will downscale."
  resizer() { cp "$ICON_SRC" "$2"; }
fi

for s in "${ICON_SIZES[@]}"; do
  dst_dir="$ICONS_DIR/${s}x${s}/apps"
  mkdir -p "$dst_dir"
  resizer "$s" "$dst_dir/mentor.png" || cp "$ICON_SRC" "$dst_dir/mentor.png"
done
mkdir -p "$ICONS_DIR/scalable/apps"
cp "$ICON_SRC" "$ICONS_DIR/scalable/apps/mentor.png"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Mentor
GenericName=Private AI
Comment=Your private, local-first AI — chat, agents, research
Exec=$LAUNCHER
TryExec=$LAUNCHER
Icon=mentor
Terminal=false
Categories=Utility;Network;
Keywords=AI;assistant;chat;agent;LLM;
StartupWMClass=Mentor
StartupNotify=true
SingleMainWindow=true
EOF

refresh_caches

echo
echo "Installed Mentor app launcher:"
echo "  $DESKTOP                                  (Icon=mentor, WMClass=Mentor)"
echo "  $ICONS_DIR/<size>/apps/mentor.png         (theme entries)"
echo
echo "If the dock still shows the old/no icon for an already-pinned shortcut:"
echo "  • unpin Mentor from the taskbar, then re-pin it from the app menu, OR"
echo "  • log out and back in (safest — reloads the desktop cleanly)."
echo
echo "NB: do NOT run a bare 'plasmashell' or 'kstart plasmashell' to reload —"
echo "plasmashell is single-instance per session; a second one aborts and takes"
echo "the live desktop down with it. A manual restart must quit first, and is a"
echo "USER action in a real terminal, never something a script/agent runs:"
echo "      kquitapp6 plasmashell && (setsid kstart plasmashell &) disown"
