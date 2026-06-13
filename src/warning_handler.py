"""Warning detection and tracking system.

Monitors diagnostics for warnings and suggests/applies fixes when safe.
Complements autoheal which handles errors and setting fixes.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def track_and_handle_warnings(diagnostics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze diagnostics and track warnings, suggesting fixes for safe ones.

    Returns list of warnings with actions taken.
    """
    handled = []

    try:
        for area, items in (diagnostics.get("groups") or {}).items():
            for finding in items:
                if finding.get("status") != "warn":
                    continue

                name = finding.get("name", "?")
                detail = finding.get("detail", "")

                # Track the warning
                await _log_warning(area, name, detail)

                # Handle specific safe warnings
                if area == "plugins" and "disabled in manifest" in detail:
                    # Safe to enable: just update plugin.json
                    result = await _enable_disabled_plugin(name)
                    if result:
                        handled.append(result)

                elif area == "serving" and "OLLAMA_FLASH_ATTENTION" in name:
                    # Safe to set env var
                    result = await _suggest_ollama_setting(name, detail)
                    if result:
                        handled.append(result)

    except Exception as e:
        logger.debug("Warning handler error: %s", e)

    return handled


async def _log_warning(area: str, name: str, detail: str) -> None:
    """Log warning to persistent file for tracking."""
    try:
        log_file = Path(__file__).parent.parent / "data" / "warnings.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now().isoformat(),
            "area": area,
            "name": name,
            "detail": detail,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("Failed to log warning: %s", e)


async def _enable_disabled_plugin(plugin_name: str) -> Optional[Dict[str, Any]]:
    """Enable a disabled plugin by setting enabled=true in plugin.json."""
    try:
        plugins_dir = Path(__file__).parent.parent / "plugins" / plugin_name
        manifest = plugins_dir / "plugin.json"

        if not manifest.exists():
            return None

        with open(manifest, encoding="utf-8") as f:
            config = json.load(f)

        if config.get("enabled") == False:
            config["enabled"] = True
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info("warning_handler: enabled plugin %s", plugin_name)
            return {
                "area": "plugins",
                "name": plugin_name,
                "action": "enabled in manifest",
            }
    except Exception as e:
        logger.debug("Failed to enable plugin %s: %s", plugin_name, e)

    return None


async def _suggest_ollama_setting(setting_name: str, detail: str) -> Optional[Dict[str, Any]]:
    """Suggest Ollama performance settings."""
    # These would require updating .env or systemd service
    # For now, just log the suggestion
    logger.info("warning_handler: Ollama setting suggestion for %s: %s", setting_name, detail)

    return {
        "area": "serving",
        "name": setting_name,
        "action": "suggested in logs (requires manual .env update)",
    }


async def get_warning_summary() -> Dict[str, Any]:
    """Get summary of recent warnings."""
    try:
        log_file = Path(__file__).parent.parent / "data" / "warnings.jsonl"

        if not log_file.exists():
            return {"total": 0, "by_area": {}}

        warnings = []
        by_area: Dict[str, int] = {}

        with open(log_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    w = json.loads(line)
                    warnings.append(w)
                    area = w.get("area", "unknown")
                    by_area[area] = by_area.get(area, 0) + 1

        return {
            "total": len(warnings),
            "by_area": by_area,
            "recent": warnings[-10:] if warnings else [],  # Last 10
        }
    except Exception as e:
        logger.debug("Failed to get warning summary: %s", e)
        return {"total": 0, "by_area": {}}
