#!/bin/bash
# Mentor — desktop app launcher (Linux).
#
# Opens Mentor in its OWN window (chromeless app window, own taskbar entry),
# not a browser tab. SINGLE-INSTANCE: a second click on the dock icon focuses
# the existing window instead of spawning a new one (KDE Plasma Wayland via
# KWin scripting D-Bus; X11 falls back to wmctrl). Ensures the server is up.
#
#   scripts/odysseus-app.sh          # focus existing window OR open the app
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
LOCK_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCK_FILE="${LOCK_DIR}/mentor-app.lock"

# --ask "<text>": open the chat seeded with a prompt (used by the KRunner plugin).
if [ "${1:-}" = "--ask" ] && [ -n "${2:-}" ]; then
  _enc="$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$2" 2>/dev/null || printf '%s' "$2")"
  URL="http://127.0.0.1:${PORT}/?ask=${_enc}"
fi
# --path "/app/office": open a specific path (used by the tray / Plasma widget).
if [ "${1:-}" = "--path" ] && [ -n "${2:-}" ]; then
  URL="http://127.0.0.1:${PORT}${2}"
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

# Detect an already-running Mentor app window by the user-data-dir we always pass
# to Chrome --app. Faster + more accurate than scanning by window class.
running_pid() {
  pgrep -f -- "--user-data-dir=${PROFILE}" 2>/dev/null | head -1 || true
}

# Focus existing Mentor window. KDE Plasma Wayland blocks wmctrl/xdotool, so
# we use KWin scripting via D-Bus to find a window by WM_CLASS and activate it.
focus_existing() {
  # X11 fallback (wmctrl is the simplest, if present).
  if [ "${XDG_SESSION_TYPE:-x11}" = "x11" ] && command -v wmctrl >/dev/null 2>&1; then
    wmctrl -x -a "${WMCLASS}.${WMCLASS}" 2>/dev/null && return 0
    wmctrl -a "$WMCLASS" 2>/dev/null && return 0
  fi
  # KDE Plasma path (Wayland + X11): load a tiny KWin script that activates the
  # matching window. Requires qdbus.
  local qd=""
  for c in qdbus-qt6 qdbus6 qdbus; do
    if command -v "$c" >/dev/null 2>&1; then qd="$c"; break; fi
  done
  [ -z "$qd" ] && return 1
  local script
  script="$(mktemp "${LOCK_DIR}/mentor-focus.XXXXXX.js")" || return 1
  cat > "$script" <<'JS'
// Find the Mentor window by WM_CLASS (resourceClass / resourceName) and activate.
const wins = (typeof workspace.windowList === 'function') ? workspace.windowList()
           : (typeof workspace.clientList === 'function' ? workspace.clientList() : []);
for (const w of wins) {
  const cls  = (w.resourceClass || '').toString().toLowerCase();
  const name = (w.resourceName  || '').toString().toLowerCase();
  const title = (w.caption || '').toString().toLowerCase();
  if (cls === 'mentor' || name === 'mentor' || title.includes('mentor')) {
    if (w.minimized) w.minimized = false;
    try { workspace.activeWindow = w; } catch (e) {}
    try { if (typeof w.requestActivate === 'function') w.requestActivate(); } catch (e) {}
    break;
  }
}
JS
  local id
  id="$("$qd" org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$script" "mentor-focus" 2>/dev/null || true)"
  if [ -n "$id" ]; then
    "$qd" "org.kde.KWin" "/Scripting/Script${id}" "org.kde.kwin.Script.run"  >/dev/null 2>&1 || true
    "$qd" "org.kde.KWin" "/Scripting/Script${id}" "org.kde.kwin.Script.stop" >/dev/null 2>&1 || true
  fi
  rm -f "$script"
  return 0
}

open_app() {
  case "$BROWSER_KIND" in
    chromium)
      # Detach so this launcher process can exit while Chrome lives on.
      # --class sets the window's WM_CLASS / Wayland app_id, which is what KDE
      # Plasma matches against the launcher's StartupWMClass=Mentor. Without it
      # the window gets Chrome's generic app id and shows as a separate "W" icon.
      setsid "$BROWSER_BIN" --app="$URL" --class="Mentor" --title="Mentor" \
        --icon="/home/robert/.local/share/icons/hicolor/256x256/apps/mentor.png" \
        --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
        >/dev/null 2>&1 &
      disown 2>/dev/null || true
      ;;
    epiphany)
      setsid "$BROWSER_BIN" --application-mode "$URL" >/dev/null 2>&1 &
      disown 2>/dev/null || true
      ;;
    firefox)
      # Dedicated profile window (Firefox has no true app mode, but an isolated
      # profile keeps it separate from normal browsing).
      setsid "$BROWSER_BIN" --no-remote -P odysseus-app --new-window "$URL" >/dev/null 2>&1 &
      disown 2>/dev/null || true
      ;;
    *)
      setsid xdg-open "$URL" >/dev/null 2>&1 &
      disown 2>/dev/null || true
      ;;
  esac
}

if [ "${1:-}" = "--check" ]; then
  echo "repo:    $REPO_DIR"
  echo "url:     $URL"
  echo "browser: $BROWSER_KIND ($BROWSER_BIN)"
  echo -n "server:  "; (systemctl --user is-active odysseus-ui 2>/dev/null || echo "inactive")
  echo -n "health:  "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 2 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || echo "unreachable"
  echo -n "running: "; pid="$(running_pid)"; [ -n "$pid" ] && echo "pid=$pid" || echo "no"
  exit 0
fi

# ── single-instance gate ────────────────────────────────────────────────────
# Serialize concurrent launcher invocations (e.g. rapid double-clicks on the
# dock icon) so two windows can never race past the running-pid check.
# Note: `exec N>file` can fail under set -e in detached sessions (no
# controlling terminal). Use a subshell-safe approach instead.
if command -v flock >/dev/null 2>&1; then
  flock -w 5 "$LOCK_FILE" true 2>/dev/null || true
fi

ensure_server

PID="$(running_pid)"
if [ -n "$PID" ]; then
  # Already running — focus, don't spawn a 2nd window. (--ask/--path can't
  # reach the running Chrome --app window's URL bar from outside; the user
  # navigates manually in-app afterward.)
  focus_existing || true
  exit 0
fi

open_app
# Best-effort: bring the brand-new window forward.
sleep 1
focus_existing || true
exit 0
