"""Plugin file watcher — keeps registry in sync with filesystem.

Monitors plugins/ directory for changes (new plugins, modified plugin.json,
deleted plugins) and automatically regenerates plugins-registry.json.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PluginWatcher:
    """Watch plugins/ directory and maintain plugins-registry.json."""

    def __init__(self, plugins_dir: str = "plugins", registry_path: str = "data/plugins-registry.json"):
        self.plugins_dir = Path(plugins_dir)
        self.registry_path = Path(registry_path)
        self._last_modified: Dict[str, float] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _regenerate_registry(self) -> None:
        """Scan plugins/ and write registry."""
        try:
            registry = {"plugins": [], "generated_at": None, "version": "1.0"}

            if self.plugins_dir.exists():
                for plugin_dir in sorted(self.plugins_dir.glob("*")):
                    if not plugin_dir.is_dir():
                        continue

                    plugin_json = plugin_dir / "plugin.json"
                    if plugin_json.exists():
                        try:
                            with open(plugin_json, encoding="utf-8") as f:
                                config = json.load(f)

                            entry_py = plugin_dir / (config.get("entry", "plugin") + ".py")
                            entry_exists = entry_py.exists()

                            registry["plugins"].append({
                                "name": config.get("name"),
                                "version": config.get("version"),
                                "description": config.get("description"),
                                "enabled": config.get("enabled", True),
                                "entry": config.get("entry", "plugin"),
                                "entry_exists": entry_exists,
                                "permissions": config.get("permissions", []),
                                "path": str(plugin_dir),
                            })
                        except Exception as e:
                            logger.warning("Failed to read plugin.json for %s: %s", plugin_dir.name, e)

            # Write registry
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry["generated_at"] = datetime.now().isoformat()
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)

            logger.debug("regenerated plugin registry with %d plugins", len(registry["plugins"]))
        except Exception as e:
            logger.error("Failed to regenerate registry: %s", e)

    def _check_for_changes(self) -> bool:
        """Check if any plugin files have changed. Returns True if changes detected."""
        if not self.plugins_dir.exists():
            return False

        changed = False
        for plugin_dir in self.plugins_dir.glob("*"):
            if not plugin_dir.is_dir():
                continue

            # Check plugin.json modification time
            plugin_json = plugin_dir / "plugin.json"
            if plugin_json.exists():
                mtime = plugin_json.stat().st_mtime
                key = str(plugin_json)
                old_mtime = self._last_modified.get(key)

                if old_mtime is None or mtime > old_mtime:
                    self._last_modified[key] = mtime
                    changed = True

        return changed

    def run_once(self) -> None:
        """Run a single check and regenerate if needed."""
        if self._check_for_changes():
            logger.info("Plugin changes detected, regenerating registry")
            self._regenerate_registry()

    def start(self) -> None:
        """Start background watcher thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Plugin watcher started")

    def stop(self) -> None:
        """Stop background watcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Plugin watcher stopped")

    def _watch_loop(self) -> None:
        """Background loop that checks for changes every 30 seconds."""
        while self._running:
            try:
                self.run_once()
            except Exception as e:
                logger.debug("Error in watcher loop: %s", e)
            time.sleep(30)


# Global instance
_watcher: Optional[PluginWatcher] = None


def start_watcher(plugins_dir: str = "plugins", registry_path: str = "data/plugins-registry.json") -> None:
    """Start the plugin watcher."""
    global _watcher
    if _watcher is None:
        _watcher = PluginWatcher(plugins_dir, registry_path)
    _watcher.start()


def stop_watcher() -> None:
    """Stop the plugin watcher."""
    global _watcher
    if _watcher:
        _watcher.stop()


def check_now() -> None:
    """Force an immediate check."""
    global _watcher
    if _watcher:
        _watcher.run_once()
    else:
        # One-off check
        watcher = PluginWatcher()
        watcher.run_once()
