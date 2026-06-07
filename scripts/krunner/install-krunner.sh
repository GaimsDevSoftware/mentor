#!/bin/bash
# Install the Mentor KRunner plugin (keyword: "mentor <prompt>").
#   scripts/krunner/install-krunner.sh            # install
#   scripts/krunner/install-krunner.sh --uninstall
# User-level only (~/.local/share), no sudo. Restart KRunner after install:
#   kquitapp6 krunner 2>/dev/null; (it relaunches on next Alt+Space)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$HERE/mentor_runner.py"
DBUS_DIR="$HOME/.local/share/dbus-1/services"
PLUG_DIR="$HOME/.local/share/krunner/dbusplugins"
ICON="$(cd "$HERE/../.." && pwd)/static/odysseus-icon.svg"
SVC="$DBUS_DIR/org.mentor.krunner.service"
PLUG="$PLUG_DIR/mentor.desktop"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$SVC" "$PLUG"
  echo "Removed Mentor KRunner plugin. Restart KRunner: kquitapp6 krunner"
  exit 0
fi

chmod +x "$RUNNER"
mkdir -p "$DBUS_DIR" "$PLUG_DIR"

# D-Bus activation: KRunner starts the runner on demand (system python3 for gi/dbus).
cat > "$SVC" <<EOF
[D-BUS Service]
Name=org.mentor.krunner
Exec=/usr/bin/python3 $RUNNER
EOF

# KRunner plugin descriptor.
cat > "$PLUG" <<EOF
[Desktop Entry]
Type=Service
Name=Mentor
Comment=Ask Mentor — type "mentor <prompt>" to send it to a Mentor chat
Icon=$ICON
X-KDE-ServiceTypes=Plasma/Runner
X-Plasma-API=DBus
X-Plasma-DBusRunner-Service=org.mentor.krunner
X-Plasma-DBusRunner-Path=/runner
X-Plasma-Runner-Unique-Id=org.mentor.krunner
EOF

echo "Installed Mentor KRunner plugin:"
echo "  $SVC"
echo "  $PLUG"
echo "Restart KRunner to load it:  kquitapp6 krunner   (it relaunches on Alt+Space)"
echo 'Then type:  mentor <your prompt>'
