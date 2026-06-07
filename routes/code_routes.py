"""Code workspace API — a first-class Code pillar that does NOT depend on the
aider_code plugin being enabled. Project picker, model picker, and async edits
with live progress, all backed by src/code_edit.py.
"""
import asyncio
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from core.middleware import require_admin

_jobs: Dict[str, Dict] = {}


def _get(key, default=""):
    from src.settings import get_setting
    return get_setting(key, default)


def _set(key, value):
    from src.settings import load_settings, save_settings
    s = load_settings()
    s[key] = value
    save_settings(s)


def setup_code_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/code/status")
    async def status(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.plugin_forge import aider_bin
        return {
            "aider_installed": bool(aider_bin()),
            "project": _get("aider_code_project", ""),
            "model": _get("aider_model", ""),
            "auto_branch": bool(_get("aider_code_auto_branch", True)),
        }

    @router.get("/api/code/projects")
    async def projects(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.code_edit import find_git_repos
        repos = await asyncio.to_thread(find_git_repos)
        return {"projects": repos, "current": _get("aider_code_project", "")}

    @router.get("/api/code/models")
    async def models(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
        from src.code_edit import list_local_models
        return {"models": await list_local_models(), "current": _get("aider_model", "")}

    @router.post("/api/code/new-project")
    async def new_project(payload: Dict[str, Any] = Body(...), _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        """Scaffold a fresh git repo so the user can vibe-code a whole app from
        nothing — a real starting point for Aider to build on."""
        import os
        import re
        import subprocess
        name = re.sub(r"[^a-z0-9_-]+", "-", str(payload.get("name", "")).strip().lower()).strip("-")
        kind = str(payload.get("kind", "empty")).strip()
        if not name:
            return {"ok": False, "error": "Give the project a name."}
        base = os.path.expanduser("~/mentor-projects")
        path = os.path.join(base, name)
        if os.path.exists(path):
            return {"ok": False, "error": "A project with that name already exists."}
        SCAFFOLDS = {
            "gtk": {"app.py": (
                "import gi\ngi.require_version('Gtk', '4.0')\nfrom gi.repository import Gtk\n\n"
                "class App(Gtk.Application):\n    def __init__(self):\n        super().__init__(application_id='org.mentor.%s')\n"
                "    def do_activate(self):\n        win = Gtk.ApplicationWindow(application=self, title='%s')\n"
                "        win.set_default_size(640, 440)\n        win.set_child(Gtk.Label(label='Hello from %s — start vibe-coding!'))\n        win.present()\n\n"
                "App().run()\n") % (name.replace("-", "_"), name, name),
                "requirements.txt": "PyGObject\n",
                "README.md": "# %s\n\nA GTK4 Linux desktop app. Run: `python app.py`\n" % name},
            "qt": {"app.py": (
                "from PySide6.QtWidgets import QApplication, QMainWindow, QLabel\n\n"
                "app = QApplication([])\nwin = QMainWindow()\nwin.setWindowTitle('%s')\nwin.resize(640, 440)\n"
                "win.setCentralWidget(QLabel('Hello from %s — start vibe-coding!'))\nwin.show()\napp.exec()\n") % (name, name),
                "requirements.txt": "PySide6\n",
                "README.md": "# %s\n\nA Qt (PySide6) Linux desktop app. Run: `python app.py`\n" % name},
            "flask": {"app.py": (
                "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return '<h1>%s</h1><p>Start vibe-coding!</p>'\n\n"
                "if __name__ == '__main__':\n    app.run(debug=True, port=5000)\n") % name,
                "requirements.txt": "flask\n",
                "README.md": "# %s\n\nA Flask web app. Run: `python app.py` then open http://localhost:5000\n" % name},
            "cli": {"main.py": (
                "import argparse\n\ndef main():\n    p = argparse.ArgumentParser(description='%s')\n    p.add_argument('--name', default='world')\n"
                "    a = p.parse_args()\n    print(f'Hello, {a.name}!')\n\nif __name__ == '__main__':\n    main()\n") % name,
                "README.md": "# %s\n\nA command-line tool. Run: `python main.py --help`\n" % name},
            "empty": {"README.md": "# %s\n\nDescribe what you want in the Code page and let Mentor build it.\n" % name},
        }
        files = SCAFFOLDS.get(kind, SCAFFOLDS["empty"])
        try:
            os.makedirs(path, exist_ok=False)
            for fn, content in files.items():
                with open(os.path.join(path, fn), "w", encoding="utf-8") as f:
                    f.write(content)
            with open(os.path.join(path, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("__pycache__/\n*.pyc\n.venv/\nvenv/\n")
            subprocess.run(["git", "-C", path, "init", "-q"], timeout=10, check=False)
            subprocess.run(["git", "-C", path, "add", "-A"], timeout=10, check=False)
            subprocess.run(["git", "-C", path, "-c", "user.email=mentor@local",
                            "-c", "user.name=Mentor", "commit", "-q", "-m", "scaffold: " + name],
                           timeout=15, check=False)
        except Exception as e:
            return {"ok": False, "error": f"Could not create project: {e}"}
        _set("aider_code_project", path)
        return {"ok": True, "path": path}

    async def _run_job(job_id, instruction, files, project, model):
        job = _jobs[job_id]
        job["status"] = "running"
        job["stage"] = "starting…"

        def _cb(stage):
            job["stage"] = stage

        try:
            from src.code_edit import run_edit
            auto_branch = bool(_get("aider_code_auto_branch", True))
            result = await run_edit(instruction, files, project, model,
                                    auto_branch=auto_branch, progress_cb=_cb)
            job["result"] = result
            job["status"] = "done" if result.get("exit_code") == 0 else "failed"
            if result.get("error"):
                job["stage"] = result["error"]
        except Exception as e:
            job["status"] = "failed"
            job["result"] = {"error": str(e), "exit_code": 1}
            job["stage"] = str(e)
        job["finished_at"] = time.time()
        # keep last 20 jobs
        if len(_jobs) > 20:
            for k in sorted(_jobs, key=lambda k: _jobs[k].get("started_at", 0))[:-20]:
                _jobs.pop(k, None)

    @router.post("/api/code/edit")
    async def edit(payload: Dict[str, Any] = Body(...), _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        instruction = (payload.get("instruction") or "").strip()
        files = payload.get("files") or []
        project = (payload.get("project") or _get("aider_code_project", "")).strip()
        model = (payload.get("model") or _get("aider_model", "")).strip()
        if not instruction:
            return {"ok": False, "error": "Describe the change first."}
        if not project:
            return {"ok": False, "error": "Pick a repository first."}
        if not model:
            return {"ok": False, "error": "Pick a coder model first."}
        # Remember the choices so chat's code_edit tool + next visit reuse them.
        if project != _get("aider_code_project", ""):
            _set("aider_code_project", project)
        if model != _get("aider_model", ""):
            _set("aider_model", model)
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "status": "queued", "stage": "queued",
                         "instruction": instruction, "started_at": time.time()}
        asyncio.create_task(_run_job(job_id, instruction, files, project, model))
        return {"ok": True, "job_id": job_id}

    @router.get("/api/code/jobs/{job_id}")
    async def job(job_id: str, _admin: str = Depends(require_admin)) -> Dict[str, Any]:
        return _jobs.get(job_id) or {"error": "no such job"}

    return router
