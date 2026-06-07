#!/usr/bin/env python3
"""Mentor KRunner runner (D-Bus, org.kde.krunner1).

Type "mentor <your prompt>" in KRunner → it sends <prompt> straight into a Mentor
chat (opens the app window seeded with it). D-Bus activated, so it only runs when
KRunner queries it. Uses SYSTEM python3 (needs gi + dbus), not the app venv.
"""
import os
import subprocess

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

IFACE = "org.kde.krunner1"
BUSNAME = "org.mentor.krunner"
OBJPATH = "/runner"
KEYWORD = "mentor"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LAUNCHER = os.path.join(_REPO, "scripts", "odysseus-app.sh")
_ICON = os.path.join(_REPO, "static", "odysseus-icon.svg")


class MentorRunner(dbus.service.Object):
    @dbus.service.method(IFACE, in_signature="s", out_signature="a(sssida{sv})")
    def Match(self, query):
        q = (query or "").strip()
        low = q.lower()
        if low != KEYWORD and not low.startswith(KEYWORD + " "):
            return []
        text = q[len(KEYWORD):].strip()
        props = dbus.Dictionary({"subtext": dbus.String("Send to Mentor chat")}, signature="sv")
        if not text:
            return [(" ", "Ask Mentor…  type your prompt after 'mentor'", _ICON, 100, 1.0,
                     dbus.Dictionary({}, signature="sv"))]
        return [(text, "Ask Mentor: " + text, _ICON, 100, 1.0, props)]

    @dbus.service.method(IFACE, out_signature="a(sss)")
    def Actions(self):
        return []

    @dbus.service.method(IFACE, in_signature="ss")
    def Run(self, data, action_id):
        text = (data or "").strip()
        args = ["bash", _LAUNCHER]
        if text:
            args += ["--ask", text]
        try:
            subprocess.Popen(args, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    dbus.service.BusName(BUSNAME, bus)
    MentorRunner(bus, OBJPATH)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
