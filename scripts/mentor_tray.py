#!/usr/bin/env python3
"""Mentor system-tray applet (KDE/Linux).

Keeps Mentor resident in the system tray: open the app, jump to the Office or
Diagnostics, restart the server, and see at a glance whether it's running.
Uses SYSTEM python3 (gi: Gtk3 + AppIndicator3) — not the app venv.
"""
import os
import subprocess
import urllib.request

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import Gtk, GLib

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LAUNCHER = os.path.join(_REPO, "scripts", "odysseus-app.sh")
_ICON = os.path.join(_REPO, "static", "odysseus-icon.svg")
_PORT = os.environ.get("APP_PORT", "7000")
_SERVICE = "odysseus-ui"


def _open(path=None, ask=None):
    args = ["bash", _LAUNCHER]
    if ask:
        args += ["--ask", ask]
    elif path:
        args += ["--path", path]
    subprocess.Popen(args, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _restart(_w):
    subprocess.Popen(["systemctl", "--user", "restart", _SERVICE],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _running() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/api/health", timeout=2):
            return True
    except Exception:
        return False


class Tray:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new(
            "mentor", _ICON, AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title("Mentor")
        self.status_item = Gtk.MenuItem(label="Checking…")
        self.status_item.set_sensitive(False)
        self.ind.set_menu(self._menu())
        GLib.timeout_add_seconds(15, self._refresh)
        self._refresh()

    def _menu(self):
        m = Gtk.Menu()
        m.append(self.status_item)
        m.append(Gtk.SeparatorMenuItem())
        for label, cb in (
            ("Open Mentor", lambda _w: _open("/app")),
            ("Office (your agents)", lambda _w: _open("/app/office")),
            ("Diagnostics", lambda _w: _open("/manage#diag")),
        ):
            it = Gtk.MenuItem(label=label)
            it.connect("activate", cb)
            m.append(it)
        m.append(Gtk.SeparatorMenuItem())
        r = Gtk.MenuItem(label="Restart server")
        r.connect("activate", _restart)
        m.append(r)
        q = Gtk.MenuItem(label="Quit tray")
        q.connect("activate", lambda _w: Gtk.main_quit())
        m.append(q)
        m.show_all()
        return m

    def _refresh(self):
        up = _running()
        self.status_item.set_label("● Running" if up else "○ Server stopped")
        return True


def main():
    Tray()
    Gtk.main()


if __name__ == "__main__":
    main()
