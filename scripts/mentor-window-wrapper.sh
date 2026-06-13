#!/bin/bash
# Window class wrapper for Mentor Chrome app
# This script starts Chrome and then corrects its window class so KDE recognizes it

URL="${1:-http://127.0.0.1:7000/app}"
PROFILE="${2:-$HOME/.local/share/odysseus-app}"
ICON_PATH="/home/robert/.local/share/icons/hicolor/256x256/apps/mentor.png"

# Start Chrome in app mode
google-chrome \
  --app="$URL" \
  --title="Mentor" \
  --icon="$ICON_PATH" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check &

CHROME_PID=$!

# Wait for window to appear, then fix WM_CLASS
sleep 2

# Use xdotool to set WM_CLASS (requires xdotool installed)
if command -v xdotool >/dev/null 2>&1; then
  WINDOW_ID=$(xdotool search --name "Mentor" --class "google-chrome" | head -1)
  if [ -n "$WINDOW_ID" ]; then
    xdotool windowkill "$WINDOW_ID" 2>/dev/null || true
  fi
fi

wait $CHROME_PID
