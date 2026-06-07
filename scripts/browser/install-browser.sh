#!/bin/bash
# Download the Chromium binary Playwright needs (~150 MB). Playwright itself is
# already in the app's venv (works on Python 3.14), so this just fetches the
# browser. Run only when you want to activate browser-use.
#
#   scripts/browser/install-browser.sh            # download Chromium
#   scripts/browser/install-browser.sh --uninstall
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/venv/bin/python"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$HOME/.cache/ms-playwright"
  echo "Removed downloaded Chromium browsers."
  exit 0
fi

if ! "$PY" -c "import playwright" 2>/dev/null; then
  echo "Playwright isn't in the app venv. Install it first:  $PY -m pip install playwright"
  exit 1
fi
echo "Downloading Chromium (~150 MB) for Playwright…"
"$PY" -m playwright install chromium
echo "Done. The 'browser' tool will use it automatically once wired (after HITL)."
