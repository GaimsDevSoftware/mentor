#!/usr/bin/env python3
"""Mentor browser runner — drives a real Chromium via Playwright for agent
"computer/browser use". Runs in an ISOLATED Python 3.12 env (the app is 3.14,
which Playwright doesn't support yet) — see scripts/browser/install-browser.sh.

Invoked as a subprocess by the app's `browser` tool. Reads ONE JSON command on
argv[1] (or stdin) and prints ONE JSON result. Headless by default. Inert until
the isolated env + Chromium are installed.

Command: {"action": "...", ...}
  goto      {url}                  → {title, url, text}      (open + readable text)
  extract   {url?, selector?}      → {text}                  (text of page or selector)
  click     {url?, selector}       → {ok, title}
  type      {url?, selector, text} → {ok}
  screenshot{url?, path?}          → {path}
Safety: blocks file:// and localhost/loopback/private targets (SSRF), bounded
timeouts, text output truncated.
"""
import json
import sys
import re

_MAX_TEXT = 6000
_NAV_TIMEOUT_MS = 20000

_BLOCK = re.compile(r"^(file:|data:|about:|chrome:)", re.I)
_PRIVATE_HOST = re.compile(
    r"^(localhost|127\.|0\.0\.0\.0|::1|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)", re.I)


def _out(d):
    print(json.dumps(d)); sys.exit(0)


def _safe_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u
    if _BLOCK.match(u):
        _out({"ok": False, "error": "blocked URL scheme"})
    try:
        from urllib.parse import urlparse
        host = (urlparse(u).hostname or "")
        if _PRIVATE_HOST.match(host) or host.endswith(".local"):
            _out({"ok": False, "error": "blocked private/loopback address"})
    except Exception:
        pass
    return u


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    try:
        cmd = json.loads(raw)
    except Exception as e:
        _out({"ok": False, "error": f"bad command json: {e}"})
    action = str(cmd.get("action", "")).lower()
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        _out({"ok": False, "error": "browser engine not installed (run scripts/browser/install-browser.sh)"})

    url = _safe_url(cmd.get("url", "")) if cmd.get("url") else ""
    sel = cmd.get("selector")
    text = cmd.get("text", "")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if url:
                page.goto(url, timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            if action in ("goto", "extract"):
                target = page.locator(sel) if sel else page
                body = (target.inner_text() if sel else page.inner_text("body"))[:_MAX_TEXT]
                _out({"ok": True, "title": page.title(), "url": page.url, "text": body})
            elif action == "click":
                page.click(sel, timeout=_NAV_TIMEOUT_MS)
                _out({"ok": True, "title": page.title(), "url": page.url})
            elif action == "type":
                page.fill(sel, text, timeout=_NAV_TIMEOUT_MS)
                _out({"ok": True})
            elif action == "screenshot":
                path = cmd.get("path") or "/tmp/mentor-browser.png"
                page.screenshot(path=path, full_page=False)
                _out({"ok": True, "path": path})
            else:
                _out({"ok": False, "error": f"unknown action {action!r}"})
    except Exception as e:
        _out({"ok": False, "error": f"browser action failed: {e}"})


if __name__ == "__main__":
    main()
