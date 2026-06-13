# Weekly self-improvement audit — 2026-06-07 (PROPOSE-ONLY)

No changes were made. Every item below is a suggestion for you to approve or reject and apply yourself. Ranked within each group by my confidence that the change helps.

Inventory reviewed (all read-only): regelverk.json (43 rules), data/skills (16 auto-skills), improvement_log.jsonl (64 cycles) + improvement_queue.jsonl (31 queued), memory.json (10 app memories), and my own auto-memory (MEMORY.md + 3 files). Live-verified OS/GPU before calling anything stale.

---

## DELETE / RETIRE (superseded / exact duplicates — highest confidence)

1. **Skill `send-image-to-ollama-vision-api`** (vision, draft) — near-identical to published `send-vision-request-to-ollama`, created 4 min later and strictly better (adds file-location + non-empty verification steps). → *Delete the draft; keep `send-vision-request-to-ollama`.*
2. **Rule `a3ebc217fd3c`** (escalation, draft 0.82, "teacher mode/lærermodus → escalate") — duplicate of active `855aa30301e0`, which says the same thing and is already promoted. → *Retire/delete `a3ebc217fd3c`.*
3. **Rule `a86b12a032dc`** (honesty, draft 0.75, "cite the memory entry when referencing a past mistake") — lowest-confidence draft, never promoted, narrow, no observed use. → *Retire.* (Low stakes; could also just leave.)

## MERGE (overlapping rules — the "clutter" the task flagged)

4. **Empty-response family.** Canonical = `87a17e53c9e0` (robustness, 0.97). `9ce3cd2c2b3b` (after tool calls) restates it. → *Merge `9ce3cd2c2b3b` into `87a17e53c9e0`.* Keep `8848e7f1df57` (502/transport-error) separate — it adds concrete recovery steps, not just "don't be empty." (Note: the older empty-response dupes `1119675d0bfd` + `fd237ea2402d` are already retired — good.)
5. **Low-intent-input family.** Three active rules all say "if the message isn't a real task, acknowledge briefly and ask, don't go run tools": `a61d9f5d02ec` (declarative statement), `de63f985c715` (empty/punctuation), `59e6a7b48212` (confirm a task exists before planning tool calls). → *Merge all three into one rule* (keep `a61d9f5d02ec` as the base, it has the broadest phrasing).
6. **"Model stopped / capability broken" diagnostics.** Three drafts overlap each other and the `diagnose-and-fix-ollama-response-truncation` skill: `4bed8ec82abb` ("stopped again"), `5e7021757320` (Ollama no-content → `ollama ps`), `1789a5d6f3f3` (capability broken → scan skills). → *Merge the three drafts into one diagnostic rule that points at the skill;* keep active `aaafab6d880f` (truncation complaint → invoke skill) as the trigger.
7. **Linux-version detection skills.** `auto-detect-linux-distribution-version` (draft 0.85) and `auto-detect-and-persist-fedora-version-in-memory` (draft 0.90) overlap; the only delta is the "persist to memory" step. → *Fold the persist step into the general skill, delete the Fedora-specific one.* Note: Fedora 44 is already durably stored in both app `memory.json` and my memory, so both skills are now low-value regardless.
8. **Ambiguous-fragment clarification.** `37dcf175c72e` ("ask about what the user wrote, don't import system-prompt concepts") is a corollary of `ee628e49ce64` ("single ambiguous word → ask one question"). → *Merge `37dcf175c72e` into `ee628e49ce64`.*
9. **App memory — small-context strategy.** `8eb42bb2…` ("save technical context automatically") is a subset of `4a06aaf3…` (the fuller small-context strategy, uses 38). → *Merge `8eb42bb2` into `4a06aaf3`.*
10. **App memory — research preference.** `879be6982…` (source-diversity protocol, uses 0, added right after the last audit) overlaps `6fcaa759…` ("consider deeper web research", uses 42) and the deep-research skill. → *Merge `879be6982` into `6fcaa759`.*

## PROMOTE (clean drafts lingering — but route through replay-verify, not my say-so)

11. **Rule `ec9e479d4033`** (formatting, draft 0.82) — "answer ALL explicit sub-questions in a multi-part message." Generally correct, no overlap, no downside. → *Promote to active.*
12. **Rule `8a09dfb28099`** (efficiency, draft 0.80) — "stop after two independent test results." Already surfaced for review in the 2026-06-07 cycle. → *Promote* (or keep draft if you want more evidence).
    Caveat: per your own hardening (replay-verification gate), gap/proactive drafts are *meant* to stay draft until a clean replay. So treat 11–12 as "run the replay and promote if clean," not blind promotion.

## KEEP-AS-IS (checked, and worth keeping)

- **Hardware/OS facts** — `memory.json` `fc01d60e` (Fedora 44, RTX 4090 24 GB, i9-11900F, 32 GB) and my `project-odysseus-fork` memory: **live-verified accurate today** (`/etc/fedora-release` = 44; `nvidia-smi` = RTX 4090, 24564 MiB). Not stale.
- **Rule `c63f50a328f9`** (measure live VRAM/RAM before hardware advice) — validated this week: on 2026-06-06 the local model wrongly claimed the GPU "ran 70B models" and you corrected it (queue `93f27e680503`). This rule directly targets that failure. Keep.
- **Core shell/filesystem/llm rules** (`ff7767ecf91a`, `bc2660650c91`, `daef9137914c`, etc.) and the `bash-safe-composition`, `deep-investigative-web-research`, `escalate-to-claude` skills — real usage, no redundancy. Keep.
- **My 4 auto-memory files** — coherent, cross-linked, current; "open Fedora truncation issue" in the index is still accurate (truncation complaints recur in this week's queue). Keep.

---

## Health summary

**Counts:** 43 rules (29 active / 9 draft / 5 already-retired) · 16 auto-skills (4 published, rest draft) · 10 app memories · 4 personal memories · 31 items queued for review. **Duplication:** roughly 6 rule clusters + 2 skill pairs + 2 memory pairs are near-duplicates — concentrated almost entirely in the "empty response / low-intent input / model-stopped" themes and the two Linux-detect + two vision skills. **Stale:** none confirmed — the OS/GPU facts I spot-checked against the live system are all correct.

**The real systemic signal:** the auto-janitor isn't pruning. 47 of 64 logged cycles ended in `budget_stop: "coach window full (review items remain queued)"` (only 17 cycles examined anything), the queue is backed up at 31, and every logged cycle shows `rules_retired: [], skills_retired: []`. So clutter accrues with no automatic cleanup — these weekly audits are currently the *only* pruning mechanism. (Minor: the `hits` counter is unreliable for "never triggered" judgments — many rules read exactly `17`, matching the 17 examined-cycles, so it appears to track cycle-presence, not real triggers.)

**Trend:** moderate, not severe. The ruleset is mostly healthy and the high-value rules show real signal; the clutter is contained to a few overlapping clusters and un-promoted drafts. Approving 1–10 above would cut the near-duplicates by most of the way; the bigger lever is getting the janitor/coach budget unstuck so pruning doesn't depend on this manual pass.
