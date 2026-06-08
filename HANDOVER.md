# Mentor — Handover (2026-06-08)

> **For the next assistant taking over this codebase.** Read the "Don't touch
> without thinking" block before changing anything model/budget-related.
> The single-file project log lives at
> `/home/robert/.claude/projects/-home-robert-odysseus/memory/mentor-rebrand-cohesion.md`
> and the wider memory index at `/home/robert/.claude/projects/-home-robert-odysseus/memory/MEMORY.md`.

Branch: **`feat/self-improvement-stack`** · HEAD: `f3574df` · 49 commits this session.
Worktree: `/home/robert/odysseus/.claude/worktrees/brave-jemison-fe1f2c` (project root: `/home/robert/odysseus`).

---

## ⚠ Don't touch without thinking

1. **Claude OAuth is OFF by design.** The user's Claude Max subscription was
   burned through in 2 days because the background improvement loop drained
   `run_claude_research()` (24-turn / 15-min runs). Fail-closed in 3 places:
   - `settings.claude_oauth_enabled` default **False**
   - `settings.improve_loop_enabled` default **False**
   - `src/improvement_loop._teacher_spec()` returns `""` when the configured
     teacher spec contains `claude` / `8750` AND `claude_oauth_enabled=False`
   - `src/claude_research.run_claude_research()` refuses to invoke unless
     `claude_oauth_enabled=True`
   - `do_trigger_research(engine='claude')` falls back to default engine

   **Do not re-enable any of these without an explicit user instruction.** Even
   the `Claude Code (OAuth)` endpoint in the DB is disabled. Backup of pre-scrub
   settings: `data/settings.json.bak-claude-scrub-*`.

2. **`integrations/claude-proxy/`** still exists as code (ban-safe, OAuth via
   official CLI — never token-scraping). Keep it intact; do not delete.
   `integrations/codex-proxy/` is the ChatGPT/Codex twin (same principle).

3. **Long-horizon agent uses `plan_task`** — `src/agent_plan.py` is a tiny
   in-memory store keyed by session_id. The agent loop auto-injects the live
   plan into every round and replans on context-compaction + stall. Don't
   replace it with persistent storage without thinking about isolation.

4. **The screen-share screenshot path requires consent every capture** (browser
   `getDisplayMedia()` enforces the OS-level picker). Don't try to bypass.

5. **The Odysseus persona preset is intentional character content**, not
   leftover branding. The whole app rebranded Odysseus → Mentor, but
   `static/js/presets.js`'s "Odysseus, king of Ithaca" preset stays.

---

## What Mentor is

A local-first, private AI workspace (a fork of "Odysseus", rebranded). Two
pillars, modelled on Claude Desktop's Cowork + Code:

- **Cowork** = chat + Office (a team of user-created AI agents — see
  `_OFFICE` in `routes/app_routes.py`, `src/agent_orchestrator.py`,
  `src/agents_store.py`)
- **Code** = a real vibe-code workspace (`_CODE` in `routes/app_routes.py`,
  `src/code_edit.py`, `routes/code_routes.py`) backed by Aider; can scaffold
  a new app (`POST /api/code/new-project`) and edit a real git repo with
  live diff.

Plus: **Cookbook** (Hugging Face / serve, `_COOKBOOK`), **Workspace** (tile
multiple Mentor surfaces as iframes, `_WORKSPACE`), and **Admin** at `/manage`.

The shell is entirely in the "Mentor" design — brass + cyan + void; the SPA
chat at `/` has been folded into the same shell. The `_SETUP` wizard at
`/app/setup` walks new users through everything.

---

## The model picture (right now)

User config (`data/settings.json`):
- `teacher_model: llama-3.3-70b-versatile@Groq` (free)
- `improve_teacher_model: ''`
- `default_model`: whatever the user set in setup
- `improve_loop_enabled: False`
- `claude_oauth_enabled: False`

Enabled endpoints (live in DB):
- Local Ollama (qwen2.5-coder:32b)
- OpenCode (Zen + Go subscription)
- Mistral (free key)
- Ollama Cloud (subscription)
- Groq (free key) ← current teacher
- (image: stable-diffusion-xl-1.0-inpainting-0.1)

Disabled in DB (do not re-enable silently):
- `Claude Code (OAuth)` (port 8750)

Tier classification (`routes/models_catalog_routes.classify()` + mirror in
`src/recommend._tier_of()`):
- **local**: localhost/127.0.0.1 endpoints
- **free**: Groq, Cerebras, Mistral, Gemini, OpenRouter `:free`, Zen-free pool
- **subscription**: OpenCode Go pool (GLM/Kimi/Qwen3.x/DeepSeek/MiniMax/MiMo),
  ChatGPT/Codex/Claude OAuth proxies, Ollama Cloud
- **paid**: Anthropic API direct, OpenAI direct, Zen `claude-*`/`gpt-5.x`/
  `gpt-4`/`gemini-*`/`grok-*`

This drives the tier-chip filters in `/manage` "Your models" and
`/app/cookbook` "Recommend roles".

---

## The agent loop in plain words

`src/agent_loop.py` `stream_agent_loop`:
- Hard cap **60 rounds** (was 20), real budget is token-based + the loop-breaker
- **plan_task** tool (in `src/agent_plan.py`): the agent's own scratch plan;
  actions `draft/revise/complete/block/add/in_progress/show`
- Every round auto-injects the current plan render as a system message when it
  changes (`_last_plan_render` dedup)
- After context-compaction, if a plan exists, injects "context compacted —
  call plan_task show and revise if needed"
- Stall detector: when stuck and a plan exists, first nudge is "revise your
  plan" (one chance); only force-answer at 6+ stuck rounds
- Emits `plan_update` SSE event on every plan_task; chat.js renders a sticky
  in-chat plan card with status icons (○ ◐ ● ⊘) + revision counter + glow
  pulse on each update

**HITL gate** (`src/hitl.py`): `hitl_mode` setting `off|risky|all`. When on,
pauses before risky tools, emits `approval_required` SSE, awaits user
Approve/Deny card in chat; 5-min auto-deny.

---

## The setup concierge

Two assistant surfaces sharing the same conversation via
`localStorage('mentor-asst-chat')`:
- **Embedded** in `/app/setup` (`_SETUP` template)
- **Floating widget** on every other `/app*` + `/manage` page
  (`static/js/concierge.js`) — minimize/close/drag, sticky bottom-right.
  Self-guards on `/app/setup` and inside Workspace iframes.

Backend: `POST /api/setup/assistant` runs on `teacher_model` with an action
protocol; frontend executes `detect_system / install_ollama / setup_free_helper /
recommend_local / serve_local / set_role / auto_roles / open_concierge / done`.
Authoritative `done`-gate: server overrides any "done" the model claims unless
an enabled endpoint + a `default_model` are real.

**Hardening**:
- Scope-locked system prompt: only setup; refuses prompt-injection ("ignore
  previous instructions", role-play, "you are now…")
- "Your turn" glow on input when waiting for the user
- Urgent amber glow + auto-open when a critical role (default, vision) is empty
  (`/api/setup/role-status`)
- Context-aware multi-source advice (matrix in the prompt — only urges
  multi-source when actually useful for the user's tier mix)
- Screen-share opt-in: when widget opens, offers "Vil du dele skjermen?" →
  `getDisplayMedia()` → vision_model description fed in as context
- After first `done`, suppresses repeated "You're all set" bubbles; shows a
  small `● Mentor is ready` pill in the header instead

---

## Office (Cowork)

`_OFFICE` in `routes/app_routes.py` + `src/agent_orchestrator.py`:
- Pixel-art animated office canvas (`#office`) — one desk + character per
  agent (agent-colour shirt, idle bob, blink), monitor glows green=working
  / amber=needs-input, star window + brass guide-star (Mentor motif)
- Team message: **live per-agent placeholders** with spinner + 1s elapsed
  ticker ("thinking · 12s" → "working · 25s" → "still working · 50s") + a
  brass hint line after 8s
- Capacity pill shows real team cap from `/api/agents/capacity.budget`

**Known limit:** `/api/agents/say` is still a single blocking POST — replies
all land at once. Real streaming per agent would need SSE refactor. The UI no
longer feels dead, but it's not yet truly per-agent live.

---

## Code (Code pillar)

`_CODE` in `routes/app_routes.py` + `routes/code_routes.py` + `src/code_edit.py`:
- Repo PICKER (auto-discovered git repos) + coder-model PICKER (local Ollama)
- **New project** scaffolder: GTK / Qt / Flask / CLI / empty starter; creates
  a git repo under `~/mentor-projects`
- Live per-stage spinner + colour-coded git diff + collapsible Aider log
- All edits on a feature branch, **never committed** — user reviews
- One-click Aider install (`POST /api/manage/install-aider`)
- Chat's `code_edit` tool delegates to the same `src.code_edit.run_edit`

---

## Recent commits (last 49) — newest first

```
f3574df feat(office): live per-agent feedback in the room — no more silent dead air
4df862f fix(concierge): stop repeating 'You're all set' — small header badge instead
4d6694b feat(concierge): opt-in screen-share gives the assistant visual context
cf3b5dd fix(models): correct tier classification for subscription proxies + free providers
72343cd feat(models): split OpenCode into Zen-free / Go-subscription / paid
46ce6d7 feat(launcher): single-instance Mentor — second click focuses, doesn't spawn
25f489f fix(claude): hard kill switch for OAuth/subscription use; default OFF
2aac3b7 feat(chat): live plan panel — see the agent's plan + revisions as they happen
068c23c feat(agent): long-horizon plan_task + replan signals + 60-round cap
624ba2d feat(concierge): context-aware multi-source reasoning, not blanket urging
09834ab feat(cookbook): Recommend roles with tier preference + actionable rows
91ece35 feat(setup): smart fallbacks across different sources + multi-source / node guidance
07ce2f0 fix(linux): proper KDE Plasma dock icon (hicolor theme + Icon=mentor)
69b1a00 design: prettier dock/app icon — polished squircle, glowing guide-star
7a9dacf feat(tools): readable Tools & Data + bulk select for tools and models
3965b03 fix(ui): toggle width bug + urgently prompt to fill missing model roles
80f9913 feat(models): your-models catalog with tier filters + per-model visibility
ae4d33d feat(office): pixel-art animated virtual office
a7f4cfa feat(setup): sticky Next + AI auto-fills all model roles (incl. vision)
eb2362f fix(concierge): server-side gate — only honor 'done' when a work model is real
... (29 more — `git log --oneline -50` for the rest)
```

---

## Open / next-obvious

- **Cowork pending refactor** (user opened Cowork to do this): rewrite the
  Claude-OAuth-specific code in `src/improvement_loop.py`, `src/claude_research.py`,
  related so it uses `teacher_model` (any OpenAI-compatible) instead of being
  Claude-coded. Cowork was given a precise prompt for this — see the most-recent
  chat turn. The kill-switch keeps it safe regardless.

- **Real per-agent SSE** in Office room (currently blocking POST + UI placeholder).
  Would require: `say` endpoint → SSE stream, orchestrator emits per-agent
  `agent_start / agent_tool / agent_reply` events, frontend replaces placeholders
  as each lands.

- **Setup-wizard "ready only" filter** depends on cookbook providers actually
  setting the `ready` field on catalog entries. If users complain that
  everything always shows as ready (or never), patch the providers.

- **A real "Add Ollama node" flow** in Cookbook for multi-machine fleets (the
  concierge currently just explains + points; node setup is still manual).

- **Mac `.app` shortcut**: the Linux/KDE icon path is sorted. Mac was raised
  earlier but the user clarified they are on Linux/Fedora/KDE, so no work
  needed there.

---

## Quick verification commands

```bash
cd /home/robert/odysseus

# App health
curl -s -o /dev/null -w 'health %{http_code}\n' http://127.0.0.1:7000/api/health

# Restart server
systemctl --user restart odysseus-ui; sleep 10

# Confirm Claude is fully gated
./venv/bin/python -c "
import asyncio
from src.claude_research import run_claude_research
print(asyncio.run(run_claude_research('test')))
"
# Expected: {'ok': False, 'reason': 'Claude OAuth use is disabled (settings.claude_oauth_enabled = false)...'}

# Plan store smoke test
./venv/bin/python -c "
from src import agent_plan
agent_plan.handle_plan_action('s','{\"action\":\"draft\",\"goal\":\"x\",\"steps\":[\"a\",\"b\"]}')
agent_plan.handle_plan_action('s','{\"action\":\"complete\",\"step\":1}')
print(agent_plan.render_for_context('s'))
"

# Endpoint inventory
./venv/bin/python -c "
from core.database import SessionLocal, ModelEndpoint
db = SessionLocal()
for e in db.query(ModelEndpoint).all():
    print(('✓' if e.is_enabled else '✗'), e.name, e.base_url)
db.close()
"

# Tier classifier smoke (18 cases)
./venv/bin/python -c "
from routes.models_catalog_routes import classify
print(classify('Groq','https://api.groq.com/openai/v1','llama-3.3-70b'))
# expect ('cloud', 'free')
"

# Single-instance launcher
scripts/odysseus-app.sh --check
```

---

## Key files

| Concern | File |
|---|---|
| Streaming agent loop | `src/agent_loop.py` |
| Plan store / plan_task tool | `src/agent_plan.py` |
| Tool registry (allow-list) | `src/agent_tools.py` |
| Tool dispatch | `src/tool_execution.py` |
| Tool descriptions (RAG-fed) | `src/tool_index.py` |
| Settings defaults | `src/settings.py` |
| HITL gate | `src/hitl.py` |
| Code-edit engine | `src/code_edit.py` |
| Improvement loop (Claude-gated) | `src/improvement_loop.py` |
| Claude research (Claude-gated) | `src/claude_research.py` |
| Concierge AI backend | `routes/manage_routes.py` (`setup_assistant`, `/api/setup/*`) |
| Concierge widget (frontend) | `static/js/concierge.js` |
| Setup wizard page | `routes/app_routes.py` (`_SETUP`) |
| Office page + pixel art | `routes/app_routes.py` (`_OFFICE`) |
| Code page | `routes/app_routes.py` (`_CODE`) |
| Cookbook page | `routes/app_routes.py` (`_COOKBOOK`) |
| Workspace (tile iframes) | `routes/app_routes.py` (`_WORKSPACE`) |
| /manage admin shell | `routes/manage_routes.py` |
| Model catalog + tier classifier | `routes/models_catalog_routes.py` |
| Role-aware recommender | `src/recommend.py` + `routes/debug_routes.py` |
| Codex / Claude OAuth proxies | `integrations/codex-proxy/` + `integrations/claude-proxy/` |
| Linux desktop launcher | `scripts/odysseus-app.sh` + `scripts/install-linux-app.sh` |

---

## Workflow rules the user keeps

- **Commit after each phase** — granular commits, never bundled.
- **Never push** unless explicitly asked.
- **Honesty over niceness** — say what's missing/broken, don't paper over it.
- **Plain Norwegian** in conversation when the user writes Norwegian; English
  in code + memory.
- **Branch:** `feat/self-improvement-stack` is the active line.
