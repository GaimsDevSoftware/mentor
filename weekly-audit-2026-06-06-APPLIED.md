# Audit changes APPLIED — 2026-06-06

All changes below are live. Backups for one-command revert:
- `data/_audit_backup_20260606150254/` (regelverk.json, memory.json, settings.json, skills/)
- `src/improvement_loop.py.bak-audit-20260606151059`

## Level 1 — dedup

**Skills deleted (21 → 13)** — via `SkillsManager.delete_skill` (dir + usage cleaned):
- `bildelagring-med-automatisk-sletting`, `midlertidig-bildehåndtering` (Norwegian twins of `clipboard-image-storage-with-auto-deletion`)
- `automatisk-model-routing-for-bildespesifikke-oppgaver` (Norwegian twin of `qwen3-vl-model-routing`)
- `safe-write-file`, `edit-document-exact-match`, `update-document-safely`, `fix-response-truncation`, `handle-local-endpoint-outage` (thin, 0-use, each merely restated an existing house rule)

**Rules** — `regelverk.set_status` / `delete_rule`:
- Retired duplicates: `1119675d0bfd` (empty-response), `fd237ea2402d` (language), `05e874dd423a` (ask-Claude), plus two the loop minted mid-session: `5eaffce1c498` (statement→ack twin), `9ab59a44dc43` (don't-fabricate twin)
- Deleted never-promoted draft duplicate: `443bcff8e835`
- Promoted sound drafts → active: `d1a910926109` (read before update_document), `c009f0e8da79` (image prompt style+lighting)

**App memory.json (13 → 10):**
- Consolidated hardware/OS triplicate into `fc01d60e…` (dropped subsets `89debd17…`, `9e11a24c…`)
- Removed two malformed+unused research entries (body text was in the `category` field): `b0c3314f…`, `25bc5d9b…`; replaced with one clean source-diversity entry

## Level 2 — auto-memory reconciliations (verified vs live system)
- `odysseus-vllm-backend.md`: added STATUS banner — vLLM package installed but UNUSED (HF models deleted, pure-Ollama). Verified: `vllm 0.22.0` imports; `~/.cache/huggingface` ≈ 320K.
- `odysseus-local-ai-stack.md`: corrected default — resident `qwen3-vl:8b` (verified in settings.json), `qwen3.6:35b` reframed as on-demand.
- `odysseus-self-improvement-loop.md`: `claude_research_per_window` 1 → 2 (live value).

## Level 3 — anti-bloat fix (root cause)
Patched `src/improvement_loop.py` and **restarted `odysseus-ui.service`** (live):
- Added a **DEDUP DISCIPLINE** block to the teacher's response contract: author everything in **English only**; check the inventory first; never create a near-duplicate, translation, or a skill that just restates a rule; prefer teaching nothing over a duplicate.
- Added `_inventory_block()` and injected the **live skill + rule inventory** into all three teacher prompts (reflection / gap / proactive) — previously the teacher judged each turn blind, which is why it minted Norwegian/English twins and reworded rules.

## Level 3b — self-limiting loop (APPLIED, restarted)
Backups: `src/regelverk.py.bak-audit-*`, `src/improvement_loop.py.bak-audit2-*`.

- **`hits` counter wired** (`src/regelverk.py`): `render_rules_block(record=True)` now calls new `bump_hits()` for every rule it injects, so `hits` is a real usage signal (was stuck at 0 — only counted dedup collisions). Verified: a live injection bumped 12 active rules.
- **Review-queue dedup** (`record_turn_for_review`): a turn whose request is ≥0.85 Jaccard to one already queued is skipped, so the loop stops re-reflecting on the same incident. Toggle: `improve_queue_dedup` (default true).
- **Janitor** (`_run_janitor`, runs at the start of every cycle): retires (reversibly, status→`retired`, never deletes; never touches user-authored skills) draft rules with 0 hits and draft skills with 0 uses that are older than `improve_janitor_max_age_days` (default 14). Toggle: `improve_janitor_enabled`. Verified: retires nothing today (all drafts are recent).
- New settings registered in `data/settings.json`: `improve_queue_dedup=true`, `improve_janitor_enabled=true`, `improve_janitor_max_age_days=14`.

## Still optional (your call)
- **Coach budget**: raise `improve_coach_per_window` (now 3/2h) only after watching that the dedup discipline holds — it's a Claude-usage tradeoff. The 50-item backlog will now also shrink on its own as the janitor + queue-dedup reduce churn.
