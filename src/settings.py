# src/settings.py
"""Centralized settings and features management.

Single source of truth for reading/writing data/settings.json and data/features.json.
All modules should import from here instead of accessing files directly.
"""

import json
import time
import logging
from typing import Any

from src.constants import SETTINGS_FILE, FEATURES_FILE

logger = logging.getLogger(__name__)

# Tiny TTL cache for settings/features. get_setting() is called on hot paths
# (every chat, every preprocess); without this it re-parses the JSON each call.
# Picks up edits within _CACHE_TTL seconds, which is fine for human-edited config.
_CACHE_TTL = 2.0
_settings_cache: tuple[float, dict] | None = None
_features_cache: tuple[float, dict] | None = None

def _invalidate_caches():
    global _settings_cache, _features_cache
    _settings_cache = None
    _features_cache = None

# ── Default values ──

DEFAULT_SETTINGS = {
    "image_gen_enabled": True,
    "image_model": "",
    "image_quality": "medium",
    "vision_model": "",
    "vision_enabled": True,
    # Ordered fallback chain for the Vision model (image analysis, OCR, tagging).
    "vision_model_fallbacks": [],
    # Public base URL used to build clickable deep-links in outgoing alerts
    # (e.g., urgency alert email). Example: "https://chat.example.com"
    "app_public_url": "",
    "tts_enabled": True,
    "tts_provider": "disabled",
    "tts_model": "tts-1",
    "tts_voice": "alloy",
    "tts_speed": "1",
    "stt_enabled": False,
    "stt_provider": "disabled",
    "stt_model": "base",
    "stt_language": "",
    "search_provider": "searxng",
    # Default fallback chain — when the primary provider fails or
    # rate-limits, we try DuckDuckGo next. Free, no API key required, so
    # safe to ship on by default for every user.
    "search_fallback_chain": ["duckduckgo"],
    "search_url": "",
    "search_result_count": 5,
    # SafeSearch level applied to every provider that exposes one.
    # "strict"   — block adult / explicit results (default; matches what users
    #              expect from a research tool and avoids unrelated NSFW URLs
    #              bleeding in via provider "related" / spam recommendations)
    # "moderate" — provider-default behavior (filter explicit but allow
    #              suggestive content)
    # "off"      — disable filtering entirely (advanced users only)
    #
    # Providers that honor this setting (translated to each provider's native
    # param in src/search/providers.py:_safesearch_for):
    #     SearXNG       safesearch=0/1/2 (JSON API, HTML scrape, news fallback)
    #     Brave Search  safesearch=off/moderate/strict
    #     DuckDuckGo    safesearch=off/moderate/on (library + HTML kp param)
    #     Google PSE    safe=active (omitted for "off"; PSE has no middle tier)
    #     Serper.dev    safe=active (omitted for "off"; proxies Google's `safe`)
    # Providers NOT touched: Tavily (no SafeSearch knob; filters at index time)
    # and any custom backend reached via search_url — they keep whatever the
    # backend itself decides, so operators stay in control of self-hosted /
    # niche search instances.
    "search_safesearch": "strict",
    "brave_api_key": "",
    "google_pse_key": "",
    "google_pse_cx": "",
    "tavily_api_key": "",
    "serper_api_key": "",
    "research_endpoint_id": "",
    "research_model": "",
    "research_search_provider": "",
    "research_max_tokens": 16384,
    "research_extraction_timeout_seconds": 90,
    "research_extraction_concurrency": 3,
    # Hard wall-clock cap on a single deep-research run. The previous 600s
    # (10 min) default cut off slow local / edge LLMs mid-synthesis; 1800s
    # (30 min) is comfortable for most local setups while still bounding
    # runaway jobs. Set to 0 to disable the cap entirely (unlimited) — only
    # for very long deep-research runs, since a stalled job then runs an
    # unbounded model/API bill. Other values are bounded to [60, 86400].
    # Tune via Settings or by editing data/settings.json.
    "research_run_timeout_seconds": 1800,
    "agent_max_tool_calls": 0,
    "agent_input_token_budget": 6000,
    # Ceiling on the *auto-derived* input budget that #1230 introduced. Has
    # no effect when `agent_input_token_budget` is explicitly set (the user's
    # value is honoured regardless). Default matches
    # `src.context_budget.DEFAULT_HARD_MAX`; lower this for cost-paranoid
    # setups, raise it on premium APIs with very large windows that you
    # want to actually use (e.g. 900_000 to fill a 1M-context model). See
    # `compute_input_token_budget` in src/context_budget.py.
    "agent_input_token_hard_max": 200_000,
    "agent_stream_timeout_seconds": 300,
    # Extra directory roots that read_file / write_file may access, in
    # addition to the built-in project data/ and system temp dirs. Each
    # entry is an absolute path. Sensitive subpaths (.ssh, .gnupg, shell
    # rc files, SSH key files) are always blocked regardless of roots.
    "tool_path_extra_roots": [],
    "task_endpoint_id": "",
    "task_model": "",
    "default_endpoint_id": "",
    "default_model": "",
    # Ordered fallback chain for the default chat model. Each entry is
    # {"endpoint_id": "...", "model": "..."}. If the primary model fails
    # before producing output (endpoint offline / errors), the chat
    # dispatch retries the next entry in order.
    "default_model_fallbacks": [],
    "utility_endpoint_id": "",
    "utility_model": "",
    # Ordered fallback chain for the Utility model (summarization, naming,
    # tidy actions, etc.).
    "utility_model_fallbacks": [],
    "teacher_model": "",
    "teacher_enabled": False,
    # Skills: minimum self-reported confidence for an auto-written (LLM-authored)
    # DRAFT skill to be injected into the agent prompt. Published skills always
    # qualify. Keeps low-confidence auto-skills out of context until they're
    # vetted/published. 0 disables the gate.
    "skill_autosave_min_confidence": 0.85,
    # Max relevant skills injected into the prompt for one request. The skills
    # library can grow beyond this; cleanup/retirement is an explicit review flow.
    "skill_max_injected": 3,
    # ── Autonomous self-improvement loop (src/improvement_loop.py) ──
    # Proactive background engine: the teacher model reviews real turns, fills
    # skill-coverage gaps, and prepares for the user's standing interests —
    # writing skills + house rules (regelverk) automatically.
    # DEFAULT OFF: this used to fire Claude OAuth research in the background and
    # could exhaust a Max subscription in days. Enable only with a non-Claude
    # teacher model, or with claude_oauth_enabled=True if you know what you're
    # doing.
    "improve_loop_enabled": False,
    # Seconds between proactive cycles (floored at 300 to protect rate limits).
    "improve_interval_seconds": 1800,
    # Max teacher calls per cycle — the main rate-limit lever.
    "improve_max_per_cycle": 3,
    # Items at/above this self-reported confidence are auto-applied; below it
    # they are queued as drafts for review. Falls back to skill_autosave value.
    "improve_min_confidence": 0.85,
    # Which input sources feed each cycle.
    "improve_sources": ["reflection", "gaps", "proactive"],
    # Dedicated teacher for the proactive loop. Empty → use teacher_model.
    "improve_teacher_model": "",
    # ── Skill quality gates (replay-verify + divergence filter) ──
    # Mint every candidate as a DRAFT, then publish (inject as authoritative)
    # only after a cheap LOCAL replay confirms the student can follow it and it
    # no longer trips failure patterns. Speculative gap/proactive skills stay
    # draft until used/reviewed. Set False to restore confidence-only publish.
    "improve_verify_replay": True,
    # Drop skills born of pure STYLE divergence (Claude would phrase it
    # differently, not better) or that the small student cannot execute.
    "improve_filter_divergence": True,
    # Allow non-replayable (gap/proactive) skills to publish on confidence alone.
    "improve_publish_unverified": False,
    # Intake throttle: fraction of SUCCESSFUL turns admitted to the review queue
    # (detected failures are ALWAYS admitted). Keeps a busy day from flooding the
    # queue faster than the coach budget can drain it. 1.0 = admit everything.
    "improve_success_sample_rate": 0.25,
    # Max active house rules (regelverk) injected into every agent prompt.
    "regelverk_max_injected": 12,
    # ── Thinking-model truncation guard (self-hosted qwen3/deepseek-r in agent) ──
    # Reasoning models put output in a <think> block first; if the token budget
    # is spent there the answer comes back empty/truncated. Append `/no_think`
    # and floor num_predict so the answer always has room. Set False to restore
    # full chain-of-thought reasoning (at the risk of truncated answers).
    "agent_local_no_think": True,
    "agent_local_min_predict": 8192,
    # Reasoning models (qwen3/deepseek-r/qwq/gpt-oss/…) spend output budget on a
    # <think> block first, so they get extra num_predict headroom for the answer.
    "agent_local_reasoning_predict": 12288,
    # Anti-truncation continuation in the live chat: if a reply is cut off
    # (finish_reason "length") with no tool call, automatically continue the same
    # answer instead of stopping mid-message. Bounded by agent_max_continuations.
    "agent_continue_on_truncation": True,
    "agent_max_continuations": 3,
    # ── Plugin builder (setup_copilot / plugin_forge) ──
    # "auto" uses Aider (free, git-aware, BYO local model) if installed + aider_model
    # set, else the teacher model. "aider"/"teacher" force one. aider_model e.g.
    # "ollama/qwen3-coder" or "openrouter/<free-model>:free" — a FREE coder.
    "plugin_builder_backend": "auto",
    "aider_model": "",
    # ── Ollama serving (set on the OLLAMA SERVER, not the app) ──
    # KV-cache quantization fits longer context in much less VRAM (q8_0 ≈ ½ the
    # KV memory of fp16, tiny quality loss) — needs Flash Attention. Less VRAM
    # pressure = far fewer mid-generation evictions/stalls on a 24GB daily-driver.
    # The debugger checks these and shows the exact env to export.
    "ollama_flash_attention": True,        # → OLLAMA_FLASH_ATTENTION=1
    "ollama_kv_cache_type": "q8_0",        # → OLLAMA_KV_CACHE_TYPE=q8_0 (or q4_0)
    # ── History RAG (long-range recall on small windows) ──
    # Index every turn in the vector store and retrieve the relevant earlier ones
    # into context, so a detail from early in a long chat survives a small window
    # (complements compaction). Needs ChromaDB + an embedding model.
    "history_rag_enabled": True,
    # ── Telegram bridge (plugins/telegram, disabled by default) ──
    # Mobile chat front-end. Token from @BotFather; allowlist your numeric
    # Telegram id (from @userinfobot) — an EMPTY allowlist answers nobody.
    "telegram_bot_token": "",
    "telegram_allowed_user_ids": [],
    "telegram_owner": "admin",          # whose model/data the bot uses
    "telegram_mode": "agent",           # "agent" (tools) | "chat" (model only)
    # ── Claude usage budget (windowed — protects the Max subscription) ──
    # Caps are PER TIME WINDOW, not per day, so capacity is spread evenly and is
    # never all spent early. Unused allowance does not roll over.
    "improve_coach_per_window": 3,       # teacher coaching/reflection calls
    "improve_coach_window_hours": 2,
    # MASTER KILL SWITCH for Claude subscription / OAuth use. Default OFF: the
    # Claude Code CLI proxy + claude_research engine are a fast way to burn a
    # Max subscription if anything calls them in a loop (the improvement loop
    # was caught doing exactly that). Set to True only if you explicitly want
    # Mentor to tap your Claude Code subscription, and watch the budget.
    "claude_oauth_enabled": False,
    "claude_research_per_window": 0,     # default 0 — gated by claude_oauth_enabled too
    "claude_research_window_hours": 2,
    # Backlog drain ("free coins") — a SEPARATE allowance so clearing the
    # research queue never spends the normal research budget above.
    "claude_research_queue_per_window": 0,
    "claude_research_queue_window_hours": 2,
    # ── Claude web-research engine (src/claude_research.py) ──
    "claude_research_model": "sonnet",   # sonnet | opus | haiku
    "claude_research_max_turns": 24,     # browsing depth cap (4..60)
    "claude_research_timeout_seconds": 900,
    "claude_research_owner": "admin",    # Library owner for automated runs
    # Auto-rerun a weak local answer with Claude web-research + store it.
    "improve_rerun_weak_answers": True,
    # Allow the proactive loop to deposit research on the user's interests.
    "improve_research_proactive": True,
    # ── Aegis runtime tool-call firewall (src/aegis_firewall.py) ──
    # "off" = no-op (default). "audit" = score+log every tool call, never block
    # (run this first to see what it would do). "enforce" = block calls scoring
    # at/above aegis_block_threshold before they execute. Audit log:
    # data/aegis_audit.jsonl. Fully reversible (set back to "off").
    "aegis_mode": "off",
    # HITL: pause before tools run and ask the user. off | risky (code/system
    # tools only) | all (every tool). See src/hitl.py.
    "hitl_mode": "off",
    "aegis_block_threshold": 80,   # enforce: block at/above this risk (0..100)
    "aegis_warn_threshold": 60,    # log as "warn" at/above this (no block)
    # ── Plugin system (src/plugin_system.py) ──
    # In-process, manifest-gated plugins under plugins/<name>/. Each declares the
    # surfaces it touches (tools/hooks/cookbook/services/routes); tool calls still
    # flow through Aegis + the normal gates. Set False to load no plugins.
    "plugins_enabled": True,
    # ── Fleet mode (single machine vs multi-machine) ──
    # "auto" (single unless LLM_HOSTS lists extra hosts), "single", or "fleet".
    # Single mode makes topology, recommendations and onboarding treat THIS one
    # machine as the whole system — the app works excellently on its own.
    "fleet_mode": "auto",
    # ── Copilot model recommendations ──
    # Which models Copilot considers when recommending roles: "local" (our fleet),
    # "sources" (plugin/source models like OpenCode Zen / OpenRouter), or "both".
    "recommend_scope": "both",
    # Auto-heal: opt-in background loop that applies only safe, reversible setting
    # fixes from diagnostics (default off). Interval in seconds (min 300).
    "autoheal_enabled": False,
    "autoheal_interval_seconds": 1800,
    # Which model tier runs multi-step web search (follows the multi-step-web-search skill):
    # "app" = the app's configured AI (default/research), "local" = a local model, "cloud" = a cloud model.
    "search_model_mode": "app",
    # ── opencode (OpenCode Zen) plugin ──
    # By default only the FREE Zen models + the models included with the Go
    # subscription are surfaced. Set True to ALSO use per-request PAID models
    # (Claude, GPT-5.5, Gemini…) via the opencode API. `opencode_paid_patterns`
    # defines which model-id families count as paid (id substring match).
    "opencode_include_paid": False,
    "opencode_paid_patterns": ["claude-", "gpt-5.5", "gpt-5.4", "gpt-4", "gemini-", "grok-"],
    # ── openrouter plugin (disabled by default) ──
    # Which OpenRouter tier to surface: "free" (only :free models), "paid", or "both".
    "openrouter_tier": "free",
    # ── Caveman plugin (token compression — plugins/caveman) ──
    # Compresses bulky tool output (web/search dumps) before it enters the
    # context window — preserving code, URLs, numbers, quotes. Big, safe token
    # savings under pressure. Levels: minimal | structural | aggressive.
    "caveman_enabled": True,
    "caveman_level": "aggressive",        # curated filler removal is meaning-preserving
    "caveman_min_chars": 600,             # only compress fields larger than this
    "caveman_compress_tools": ["web_search", "trigger_research", "manage_research"],
    "caveman_compress_system_prompt": False,  # opt-in; uses safe 'minimal' level
    # ── Embedding model (RAG + memory vectors) ──
    # Switched from all-MiniLM (English-centric, 384-dim) to jina-embeddings-v3
    # (multilingual, 1024-dim) for better Norwegian retrieval. Served locally via
    # fastembed (ONNX, downloads ~2GB on first use). Changing this REQUIRES a
    # Chroma reindex (dim change) — run scripts/reindex_embeddings.py --apply.
    # Proven 1024-dim fallback if jina misbehaves: intfloat/multilingual-e5-large
    # (note: e5 needs query:/passage: prefixes we don't add — prefer jina).
    "embedding_fastembed_model": "jinaai/jina-embeddings-v3",
    # Reminders
    "reminder_channel": "browser",   # "browser" | "email" | "ntfy"
    "reminder_llm_synthesis": False,
    "reminder_ntfy_topic": "Reminders",
    "reminder_email_to": "",
    # Email triage scanner rules. Running/paused state and schedule live in
    # Tasks via the built-in `check_email_urgency` task.
    "urgent_email_prompt": (
        "Flag as urgent: explicit deadlines, time-sensitive requests, "
        "work-blocking issues, messages from people I report to, or anything "
        "where a delayed reply costs money/trust. Someone waiting outside, "
        "at the door, locked out, or unable to get in is urgent now. "
        "Newsletters, marketing, automated digests, and FYI-only updates are "
        "NOT urgent."
    ),
    # Keyboard shortcuts (action: key combination)
    "keybinds": {
        "search": "ctrl+k",
        "toggle_sidebar": "ctrl+b",
        "new_session": "ctrl+alt+n",
        "star_session": "ctrl+alt+s",
        "delete_session": "ctrl+alt+d",
        "admin_panel": "ctrl+shift+u",
        "cancel": "escape",
    },
}

DEFAULT_FEATURES = {
    "web_search": True,
    "web_fetch": True,
    "deep_research": False,
    "memory": True,
    "document_editor": True,
    "rag": True,
    "sensitive_filter": True,
    "gallery": True,
}


# ── Settings (data/settings.json) ──

def load_settings() -> dict:
    """Load settings merged with defaults. Always returns a complete dict."""
    global _settings_cache
    now = time.monotonic()
    if _settings_cache and (now - _settings_cache[0]) < _CACHE_TTL:
        return _settings_cache[1]
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if not isinstance(saved, dict):
            raise ValueError("settings must be an object")
        merged = {**DEFAULT_SETTINGS, **saved}
    except (FileNotFoundError, PermissionError, json.JSONDecodeError, ValueError):
        merged = dict(DEFAULT_SETTINGS)
    _settings_cache = (now, merged)
    return merged


def save_settings(settings: dict):
    """Persist settings to disk (atomic; see core.atomic_io)."""
    from core.atomic_io import atomic_write_json
    atomic_write_json(SETTINGS_FILE, settings, indent=2)
    _invalidate_caches()


def get_setting(key: str, default: Any = None) -> Any:
    """Read a single setting value."""
    return load_settings().get(key, default)


def is_setting_overridden(key: str) -> bool:
    """True if ``key`` is explicitly present in the saved settings file.

    ``load_settings`` merges DEFAULT_SETTINGS with the saved file, so a value
    equal to its default is indistinguishable from "never set" via get_setting.
    Callers that need to treat an explicit user choice differently from the
    default (e.g. adaptive budgets) use this to read the raw saved file.
    """
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return isinstance(saved, dict) and key in saved
    except (FileNotFoundError, json.JSONDecodeError):
        return False


# Per-user settings (user prefs override the global admin default). Used for
# keys that a user is allowed to choose individually — currently the vision
# model + image-generation model. The owner argument is the authed username
# resolved by FastAPI deps; an empty/None owner falls through to the global.
_PER_USER_KEYS = {
    "vision_model", "vision_enabled", "vision_model_fallbacks",
    "image_model", "image_gen_enabled", "image_quality",
    # Default chat endpoint / model — without per-user resolution every new
    # account inherited whatever the most-recent admin picked, which then
    # got injected into the chat composer on first open.
    "default_endpoint_id", "default_model", "default_model_fallbacks",
    "utility_endpoint_id", "utility_model", "utility_model_fallbacks",
    "research_endpoint_id", "research_model",
}


def get_user_setting(key: str, owner: str = "", default: Any = None) -> Any:
    """Resolve `key` from the caller's per-user prefs first, falling back to
    the global setting. Only the small whitelist in `_PER_USER_KEYS` is
    eligible — for any other key this is equivalent to `get_setting(key)`.

    Falls back gracefully if the prefs module can't be imported (cycle/early
    boot) — admin-global settings keep working.
    """
    if owner and key in _PER_USER_KEYS:
        try:
            from routes.prefs_routes import _load_for_user
            prefs = _load_for_user(owner) or {}
            if key in prefs and prefs[key] not in (None, ""):
                return prefs[key]
        except Exception:
            pass
    return get_setting(key, default)


# ── Features (data/features.json) ──

def load_features() -> dict:
    """Load feature flags merged with defaults."""
    global _features_cache
    now = time.monotonic()
    if _features_cache and (now - _features_cache[0]) < _CACHE_TTL:
        return _features_cache[1]
    try:
        with open(FEATURES_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if not isinstance(saved, dict):
            raise ValueError("features must be an object")
        merged = {**DEFAULT_FEATURES, **saved}
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        merged = dict(DEFAULT_FEATURES)
    _features_cache = (now, merged)
    return merged


def save_features(features: dict):
    """Persist feature flags to disk (atomic)."""
    from core.atomic_io import atomic_write_json
    atomic_write_json(FEATURES_FILE, features, indent=2)
    _invalidate_caches()
