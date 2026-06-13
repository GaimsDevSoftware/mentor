"""Auto-heal — opt-in self-healing for the app's own health.

When enabled, periodically runs the diagnostics engine and auto-applies ONLY the
safe, reversible **setting** fixes (via copilot_fix, which whitelists them). It
also auto-fixes common plugin issues:
  • Missing __init__.py in package directories
  • Missing dependencies from pyproject.toml
  • Re-enables disabled plugins when diagnostic suggests it

Default OFF. This turns the health badge from a passive indicator
into something that quietly keeps the app healthy.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Plugin repair helpers ───────────────────────────────────────────────────

async def _fix_missing_init_files() -> List[Dict[str, Any]]:
    """Create missing __init__.py files in plugin package directories."""
    fixed = []
    try:
        plugins_dir = Path(__file__).parent.parent / "plugins"
        if not plugins_dir.exists():
            return fixed

        for plugin_dir in plugins_dir.glob("*"):
            if not plugin_dir.is_dir():
                continue
            # Check common package subdirs
            for subdir in ["src", "lib", "package"]:
                pkg_dir = plugin_dir / subdir
                if pkg_dir.exists() and pkg_dir.is_dir():
                    init_file = pkg_dir / "__init__.py"
                    if not init_file.exists():
                        init_file.write_text('"""Package."""\n')
                        fixed.append({
                            "plugin": plugin_dir.name,
                            "fix": f"created {subdir}/__init__.py",
                        })
                        logger.info("autoheal: created %s/__init__.py", pkg_dir)
    except Exception as e:
        logger.debug("autoheal: failed to check/create __init__.py: %s", e)
    return fixed


async def _fix_missing_dependencies() -> List[Dict[str, Any]]:
    """Install missing dependencies listed in plugin pyproject.toml files."""
    fixed = []
    try:
        plugins_dir = Path(__file__).parent.parent / "plugins"
        if not plugins_dir.exists():
            return fixed

        # Find venv python
        venv_python = Path(__file__).parent.parent / "venv" / "bin" / "python3"
        if not venv_python.exists():
            return fixed

        for plugin_dir in plugins_dir.glob("*"):
            if not plugin_dir.is_dir():
                continue
            pyproject = plugin_dir / "pyproject.toml"
            if not pyproject.exists():
                continue

            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    continue

            try:
                with open(pyproject, "rb") as f:
                    config = tomllib.load(f)
                deps = config.get("project", {}).get("dependencies", [])
                if not deps:
                    continue

                for dep in deps:
                    # Extract package name (e.g., "androidtvremote2>=0.3.1" -> "androidtvremote2")
                    pkg_name = dep.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
                    try:
                        # Try to import to see if already installed
                        __import__(pkg_name.replace("-", "_"))
                    except ImportError:
                        # Not installed, try to install
                        try:
                            result = subprocess.run(
                                [str(venv_python), "-m", "pip", "install", "-q", dep],
                                timeout=60,
                                capture_output=True,
                            )
                            if result.returncode == 0:
                                fixed.append({
                                    "plugin": plugin_dir.name,
                                    "fix": f"installed {dep}",
                                })
                                logger.info("autoheal: installed %s for plugin %s", dep, plugin_dir.name)
                        except Exception as e:
                            logger.debug("autoheal: failed to install %s: %s", dep, e)
            except Exception as e:
                logger.debug("autoheal: failed to parse %s/pyproject.toml: %s", plugin_dir.name, e)

    except Exception as e:
        logger.debug("autoheal: failed to check/install dependencies: %s", e)
    return fixed


async def tick(owner: Optional[str] = None) -> Dict[str, Any]:
    """One pass: diagnose, apply safe fixes, handle warnings. Returns what changed."""
    try:
        from src import debugger, copilot_fix, warning_handler
    except Exception as e:
        return {"ok": False, "detail": f"unavailable: {e}", "fixed": []}
    try:
        data = await asyncio.to_thread(debugger.run_all, only_failures=True)
    except Exception as e:
        return {"ok": False, "detail": f"diagnostics failed: {e}", "fixed": []}

    applied: List[Dict[str, Any]] = []

    # ── Apply safe setting fixes ──
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for _area, items in (data.get("groups") or {}).items():
        for f in items:
            fx = f.get("fix")
            if isinstance(fx, dict) and fx.get("kind") == "setting":
                candidates.append((f.get("name", "?"), fx))

    for name, fx in candidates:
        try:
            r = await copilot_fix.apply_fix(fx, owner=owner)
            if r.get("ok"):
                applied.append({"name": name, "detail": r.get("detail", "")})
                logger.info("autoheal applied %s: %s", name, r.get("detail", ""))
        except Exception as e:
            logger.debug("autoheal fix %s failed: %s", name, e)

    # ── Apply plugin repairs (safe, reversible) ──
    restart_needed = False
    try:
        # Fix missing __init__.py files
        init_fixes = await _fix_missing_init_files()
        applied.extend(init_fixes)

        # Install missing dependencies
        dep_fixes = await _fix_missing_dependencies()
        applied.extend(dep_fixes)

        # If any plugin fixes were applied, mark for restart
        if init_fixes or dep_fixes:
            restart_needed = True
    except Exception as e:
        logger.debug("autoheal: plugin repair cycle failed: %s", e)

    # ── Track and handle warnings ──
    try:
        warning_actions = await warning_handler.track_and_handle_warnings(data)
        applied.extend(warning_actions)
        if any(w.get("action") == "enabled in manifest" for w in warning_actions):
            restart_needed = True
    except Exception as e:
        logger.debug("autoheal: warning handler failed: %s", e)

    # ── Restart if needed ──
    if restart_needed:
        logger.info("autoheal: restarting odysseus-ui to reload plugins/settings")
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", "odysseus-ui"],
                timeout=10,
            )
            await asyncio.sleep(3)  # Give it time to come back up
        except Exception as e:
            logger.debug("autoheal: failed to restart odysseus-ui: %s", e)

    return {"ok": True, "fixed": applied, "counts": data.get("counts", {})}
