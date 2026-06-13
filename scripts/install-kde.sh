#!/bin/bash
# Install Mentor's KDE Plasma integration: a system-tray applet (resident) and a
# Plasma widget. User-level only, no sudo. Reversible with --uninstall.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
LAUNCHER="$REPO/scripts/odysseus-app.sh"
ICON="$REPO/static/mentor-icon.png"
TRAY="$REPO/scripts/mentor_tray.py"
UNIT="$HOME/.config/systemd/user/mentor-tray.service"

if [ "${1:-}" = "--uninstall" ]; then
  systemctl --user disable --now mentor-tray.service 2>/dev/null || true
  rm -f "$UNIT"; systemctl --user daemon-reload 2>/dev/null || true
  kpackagetool6 --type Plasma/Applet --remove org.mentor.widget 2>/dev/null || true
  echo "Removed Mentor tray service + Plasma widget."
  exit 0
fi

chmod +x "$LAUNCHER" "$TRAY"

# ── system-tray applet as a user service (gets the graphical-session env) ──
mkdir -p "$(dirname "$UNIT")"
cat > "$UNIT" <<EOF
[Unit]
Description=Mentor tray applet
PartOf=graphical-session.target
# Order after plasmashell so the compositor + XWayland (:0) are actually ready.
# Without this the GTK tray races session startup and dies with
# "Error reading events from display: Broken pipe" before recovering.
After=graphical-session.target plasma-plasmashell.service
Wants=plasma-plasmashell.service
# Never give up on transient early-session display hiccups.
StartLimitIntervalSec=120
StartLimitBurst=20

[Service]
Type=simple
# Small settle margin for XWayland on a cold session; harmless if already up.
ExecStartPre=/usr/bin/sleep 2
ExecStart=/usr/bin/python3 $TRAY
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now mentor-tray.service 2>/dev/null || true

# ── Plasma widget (placeholders → real paths, then install/upgrade) ──
TMP="$(mktemp -d)"
cp -r "$HERE/plasmoid/package" "$TMP/pkg"
sed -i "s#__LAUNCHER__#$LAUNCHER#g; s#__ICON__#$ICON#g" \
    "$TMP/pkg/contents/ui/main.qml" "$TMP/pkg/metadata.json"
if kpackagetool6 --type Plasma/Applet --list 2>/dev/null | grep -q org.mentor.widget; then
  kpackagetool6 --type Plasma/Applet --upgrade "$TMP/pkg" || true
else
  kpackagetool6 --type Plasma/Applet --install "$TMP/pkg" || true
fi
rm -rf "$TMP"

echo "Installed:"
echo "  • Tray applet  → systemctl --user status mentor-tray"
echo "  • Plasma widget → add 'Mentor' via 'Add Widgets…' (right-click desktop/panel)"
