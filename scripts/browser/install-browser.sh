#!/bin/bash
# Install Mentor's browser-automation engine in an ISOLATED Python 3.12 env
# (the app runs 3.14, which Playwright doesn't support yet). Mirrors how Aider is
# installed. Downloads Chromium (~150 MB) — only run when you want browser-use.
#
#   scripts/browser/install-browser.sh            # install
#   scripts/browser/install-browser.sh --uninstall
set -euo pipefail
ENV_DIR="$HOME/.mentor-browser"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$ENV_DIR"
  echo "Removed $ENV_DIR (browser engine)."
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required (it provides an isolated Python 3.12). Install uv first:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "[1/3] creating isolated Python 3.12 env at $ENV_DIR …"
uv venv --python 3.12 "$ENV_DIR"
echo "[2/3] installing playwright …"
"$ENV_DIR/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
uv pip install --python "$ENV_DIR/bin/python" playwright
echo "[3/3] downloading Chromium (~150 MB) …"
"$ENV_DIR/bin/python" -m playwright install chromium
echo "Done. Browser engine ready at $ENV_DIR/bin/python."
echo "The app's 'browser' tool will use it automatically once wired (after HITL)."
