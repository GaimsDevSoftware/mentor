# Weekly Skills/Memory Audit — 2026-06-06 (PROPOSE-ONLY)

No changes were made. Every item below is a suggestion for you to approve or reject and apply yourself.
Ranked within each group by confidence that the change helps. Verified against the live system where noted.

---

## MERGE

1. **Rules — empty-response cluster** (`87a17e53c9e0` 0.97, `1119675d0bfd` 0.95, `9ce3cd2c2b3b` 0.95, `8848e7f1df57` 0.92)
   Four rules all say "never return an empty response"; two are generic, two are context-specific.
   → Merge `1119675d0bfd` into `87a17e53c9e0` (keep the highest-confidence generic rule). Keep `9ce3cd2c2b3b` (after tool calls) and `8848e7f1df57` (on 502) as specializations.

2. **Rules — language-matching cluster** (`9546416ba3f6` 0.95, `fd237ea2402d` 0.95, `443bcff8e835` draft 0.82)
   Three rules all say "reply in the user's language."
   → Merge `fd237ea2402d` + `443bcff8e835` into `9546416ba3f6`; delete the lingering draft `443bcff8e835`.

3. **App memory — hardware/OS triplicate** (`89debd17` 2 uses, `9e11a24c` 26 uses, `fc01d60e` 4 uses)
   `fc01d60e` already combines OS + hardware + driver; the other two are subsets.
   → Consolidate into one canonical fact based on `fc01d60e`; retire `89debd17`, fold `9e11a24c`.

4. **App memory — malformed/duplicate research-protocol entries** (`b0c3314f` 0 uses, `25bc5d9b` 0 uses)
   Both have body text stuffed into the `category` field (schema bug), both are about "source diversity in research," both overlap each other and `6fcaa759` (37 uses).
   → Merge `b0c3314f` + `25bc5d9b` into one well-formed entry (fix the `category` field), or fold into `6fcaa759`.

5. **Rules — "ask Claude" escalation** (`488326aefb76` 0.88, `05e874dd423a` 0.88)
   Near-identical: both map "ask/use Claude" → teacher escalation. (`1bc586166a92` identity is related but distinct — keep it.)
   → Merge `05e874dd423a` into `488326aefb76`.

6. **Skills — image temp-storage triplicate** (`clipboard-image-storage-with-auto-deletion` EN 0 uses, `bildelagring-med-automatisk-sletting` NO 0 uses, `midlertidig-bildeh-ndtering` NO 0 uses)
   Three near-identical SKILL.md (one English, two Norwegian) for the same clipboard→temp→auto-delete procedure.
   → Keep `clipboard-image-storage-with-auto-deletion`; retire the two Norwegian duplicates.

7. **Skills — image model-routing duplicate** (`qwen3-vl-model-routing` 0 uses, `automatisk-model-routing-for-bildespesifikke-oppgaver` NO 1 use)
   Both route image/vision tasks to qwen3-vl.
   → Merge into `qwen3-vl-model-routing`; retire the Norwegian one.

8. **Rules — clarification overlap** (`37dcf175c72e` 0.88, `522ce0d3abf7` 0.88)
   Both say "don't import operator/system-prompt concepts (e.g. the assistant's own name) into a clarifying question."
   → Merge `522ce0d3abf7` into `37dcf175c72e`. (Lower confidence — they have slightly different framing.)

9. **Skills — OS-detection overlap** (`auto-detect-linux-distribution-version` 2 uses, `auto-detect-and-persist-fedora-version-in-memory` 2 uses)
   Fedora-specific skill is a subset of the generic distro-detection skill plus a "persist to memory" step.
   → Merge the persist behavior into the generic skill; retire the Fedora-specific one.

10. **App memory — small-context overlap** (`8eb42bb2` 4 uses; overlaps `8d16ba5a` 46 uses + `4a06aaf3` 34 uses)
    `8eb42bb2` ("save technical context automatically") is largely covered by the other two.
    → Fold `8eb42bb2` into `4a06aaf3`.

---

## RECONCILE (auto-memory contradictions — verified against live system)

11. **`odysseus-vllm-backend.md` vs `odysseus-local-ai-stack.md`** — direct conflict.
    backend.md: "vLLM 0.22 installed … used by the configured vllm-backend models (Qwen3 AWQ)."
    stack.md: "vLLM is NOT installed … 99GB HF models deleted … went pure-Ollama."
    **Verified:** vLLM 0.22.0 *package* IS still in `~/odysseus/venv`, but `~/.cache/huggingface` is empty (320K) — the AWQ models are gone and nothing uses vLLM.
    → Update `odysseus-vllm-backend.md` to state the package remains installed but is unused (no models, endpoint removed, pure-Ollama), or fold the still-true package facts into `odysseus-local-ai-stack.md` and retire the standalone file.

12. **Default-model contradiction** — `odysseus-local-ai-stack.md` lists "`qwen3.6:35b` (DEFAULT)"; `odysseus-resident-model-policy.md` and live `settings.json` say `default_model`/`vision_model`/`task_model` = `qwen3-vl:8b`.
    **Verified:** live settings = `qwen3-vl:8b` on all three.
    → Update the lineup line in `odysseus-local-ai-stack.md` so qwen3-vl:8b is marked the resident default (35b loads on demand).

---

## PROMOTE

13. **Rule `d1a910926109`** (documents: read before `update_document`, draft 0.82) — consistent with the active read-before-modify family (`3ee4f376b5eb`, `06808173d843`, `3f0ff40fa60d`).
    → Promote to active.

14. **Rule `c009f0e8da79`** (media: always specify style + lighting in image prompts, draft 0.80) — sound and self-contained.
    → Promote to active (or keep draft; low priority).

---

## RETIRE (skills that never triggered and merely restate an existing always-on rule)

15. `safe-write-file` (draft, 0 uses) — restates rules `3ee4f376b5eb` + `06808173d843`.
16. `edit-document-exact-match` (draft, 0 uses) — restates rule `3f0ff40fa60d`.
17. `update-document-safely` (draft, 0 uses) — restates rule `d1a910926109`.
18. `fix-response-truncation` (draft 0.72, 0 uses) — restates rule `5838d1bb1251`.
19. `handle-local-endpoint-outage` (draft, 0 uses) — restates rule `8848e7f1df57`.
20. `chat-with-model` (draft, 0 uses) — very generic; restates the llm rules.
21. `generate-image` (draft 0.72, 0 uses) — restates rule `c009f0e8da79`.

(Caveat: rules are injected every prompt while skills are retrieved on demand, so these are medium-confidence — retire only if you find the rule already covers the case in practice. `escalate-to-claude` and `bash-safe-composition` are *published* with 0 uses; monitor rather than retire.)

---

## DELETE

22. **Rule `443bcff8e835`** (conversation: respond in user's language, draft) — exact-duplicate draft of `9546416ba3f6`/`fd237ea2402d`; never promoted. → Delete (covered by MERGE #2).

---

## KEEP-AS-IS (notable, no action)

- Rules: shell pair (`ff7767ecf91a`, `bc2660650c91`), read-before-write family, llm pair (`5838d1bb1251`, `daef9137914c`), `c63f50a328f9` + `3a82a87f81ad` (live-measurement/verify-before-answer) — all current and verified.
- Skills: `deep-investigative-web-research` (25 uses — top performer), `real-esrgan-installation-fix` (6 uses), `create-linux-desktop-entry-for-local-python-app` (conf 1.0), `implement-progressive-context-manager-for-llms`, `automate-gmail-inbox-management-with-filters`.
- App memory: `757b7987` (code-gen, 58 uses), `049f943d` (Ollama vision /api/chat — verified-style fact), `6fcaa759`, `8d16ba5a`, `4a06aaf3`, `12acc0f4`.
- Auto-memory files: `desktop-setup`, `pkexec-for-sudo`, `research-cache`, `whitesur-menu-contrast-fix`, `jellyfin-media-disk`, `odysseus-email-accounts`, `realesrgan-upscaling` — current, verified, non-overlapping.

---

## Health summary

The system is still net-useful but accumulating faster than it consolidates, and almost all of the duplication appeared in the last ~2 days.

**Rules:** 26 total (22 active, 4 draft). Roughly 8 rules (~30%) are near-duplicates concentrated in three clusters — empty-response (×4), language-matching (×3), ask-Claude (×2). Applying the merges/delete above would take this to ~18 distinct rules with no loss of coverage. Note: **every rule shows `hits: 0`**, so the hit counter appears not to be wired — do not retire rules on usage until that's fixed.

**Skills:** 21 total (4 published, 17 draft). **14 of 21 have never triggered.** Clear clutter: an image-temp-storage triplicate, an image-routing duplicate, an OS-detection duplicate, plus ~7 thin draft skills that only restate a rule. Dedup would bring this to ~13–15 skills, with the real workhorses (`deep-investigative-web-research`, `real-esrgan-installation-fix`) untouched.

**App memory (memory.json):** 13 entries — 1 hardware triplicate, 2 malformed-and-unused research entries, 1 small-context overlap. ~4 entries are redundant or schema-broken.

**Auto-memory (markdown):** 12 files, healthy — only two reconciliations needed (vLLM status, default model), both stale rather than wrong.

**Background loop:** `improvement_queue.jsonl` holds **50 unprocessed review items**; the last cycles examined 0 ("coach window full — review items remain queued"). The windowed budget (`improve_coach_per_window=3` / 2h) is draining slower than turns arrive, so the backlog is growing — the most likely driver of future duplicate rules/skills.

**Overall trend:** clutter rising, but contained and easy to cut. The highest-leverage single action is clearing the duplicate clusters (#1–#9); the highest-leverage structural fix is raising coach throughput (or deduping queued turns before review) so the loop stops minting near-identical rules.
