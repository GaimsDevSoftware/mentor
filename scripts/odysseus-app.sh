#!/bin/bash
# Odysseus — desktop app launcher (Linux).
#
# Opens Odysseus in its OWN window (chromeless app window, own taskbar entry),
# not a browser tab. Ensures the local server is running first.
#
#   scripts/odysseus-app.sh          # start server if needed + open the app window
#   scripts/odysseus-app.sh --check  # print what it WOULD do, don't open a window
#
# Server runs as the `odysseus-ui` systemd user service. Port from .env (APP_PORT)
# or 7000. Uses Chrome/Chromium "--app" mode for a real app window; falls back to
# other browsers if none is present.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Port: prefer APP_PORT from .env, else 7000.
PORT="7000"
if [ -f "$REPO_DIR/.env" ]; then
  _p="$(grep -E '^APP_PORT=' "$REPO_DIR/.env" 2>/dev/null | tail -1 | cut -d= -f2 | tr -d ' "'"'"'' || true)"
  [ -n "${_p:-}" ] && PORT="$_p"
fi
URL="http://127.0.0.1:${PORT}/app"
PROFILE="$HOME/.local/share/odysseus-app"
WMCLASS="Mentor"

# --ask "<text>": open the chat seeded with a prompt (used by the KRunner plugin).
if [ "${1:-}" = "--ask" ] && [ -n "${2:-}" ]; then
  _enc="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$2" 2>/dev/null || printf '%s' "$2")"
  URL="http://127.0.0.1:${PORT}/?ask=${_enc}"
fi

# Pick a browser that supports a real app window.
pick_browser() {
  for b in google-chrome google-chrome-stable chromium chromium-browser brave brave-browser microsoft-edge vivaldi-stable; do
    if command -v "$b" >/dev/null 2>&1; then echo "chromium:$b"; return; fi
  done
  if command -v epiphany >/dev/null 2>&1; then echo "epiphany:epiphany"; return; fi
  if command -v firefox >/dev/null 2>&1; then echo "firefox:firefox"; return; fi
  echo "xdg:xdg-open"
}
BROWSER_SPEC="$(pick_browser)"
BROWSER_KIND="${BROWSER_SPEC%%:*}"
BROWSER_BIN="${BROWSER_SPEC##*:}"

ensure_server() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user is-active --quiet odysseus-ui 2>/dev/null || systemctl --user start odysseus-ui 2>/dev/null || true
  fi
  for _ in $(seq 1 40); do
    if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  return 0  # open anyway; the page shows its own login/health
}

open_app() {
  case "$BROWSER_KIND" in
    chromium)
      exec "$BROWSER_BIN" --app="$URL" --class="$WMCLASS" \
        --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check >/dev/null 2>&1 ;;
    epiphany)
      exec "$BROWSER_BIN" --application-mode "$URL" >/dev/null 2>&1 ;;
    firefox)
      # Dedicated profile window (Firefox has no true app mode, but an isolated
      # profile keeps it separate from normal browsing).
      exec "$BROWSER_BIN" --no-remote -P odysseus-app --new-window "$URL" >/dev/null 2>&1 ;;
    *)
      exec xdg-open "$URL" >/dev/null 2>&1 ;;
  esac
}

if [ "${1:-}" = "--check" ]; then
  echo "repo:    $REPO_DIR"
  echo "url:     $URL"
  echo "browser: $BROWSER_KIND ($BROWSER_BIN)"
  echo -n "server:  "; (systemctl --user is-active odysseus-ui 2>/dev/null || echo "inactive")
  echo -n "health:  "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 2 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || echo "unreachable"
  exit 0
fi

ensure_server
open_app
