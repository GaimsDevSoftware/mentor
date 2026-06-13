#!/usr/bin/env python3
"""Mentor KRunner runner (D-Bus, org.kde.krunner1).

Type "mentor <your prompt>" in KRunner → it sends <prompt> straight into a Mentor
chat (opens the app window seeded with it). D-Bus activated, so it only runs when
KRunner queries it. Uses SYSTEM python3 (needs gi + dbus), not the app venv.
"""
import os
import subprocess

import dbus
import dbus.exceptions
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

IFACE = "org.kde.krunner1"
BUSNAME = "org.mentor.krunner"
OBJPATH = "/runner"
KEYWORD = "mentor"

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LAUNCHER = os.path.join(_REPO, "scripts", "odysseus-app.sh")
_ICON = os.path.join(_REPO, "static", "mentor-icon.png")


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
    # Own the bus name exclusively. KRunner re-activates this D-Bus service many
    # times over a long session; with dbus-python's default (queue) each extra
    # activation spawns a resident process that never acquires the name yet never
    # exits — they piled up to ~200 zombie processes (100s of MB) until logout.
    # do_not_queue=True makes a duplicate activation raise here so it exits cleanly,
    # leaving exactly one live instance.
    # Keep strong refs for the process lifetime: if the BusName is garbage-
    # collected the well-known name is released, so the runner would run but own
    # nothing (KRunner could never reach it).
    try:
        name = dbus.service.BusName(BUSNAME, bus, do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        return
    runner = MentorRunner(bus, OBJPATH)
    _keep_alive = (name, runner)  # noqa: F841 — referenced for lifetime
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
