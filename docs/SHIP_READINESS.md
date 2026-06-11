# Mentor / Odysseus — Ship-Readiness Checklist

Goal: everything that must be true before shipping this app to other users
(self-hosted, local-first AI workspace). Worked top-to-bottom. Each open
decision carries a **recommendation** so work can continue without blocking.
Items marked **[NEEDS ROBERT]** genuinely need your call.

Legend: `[x]` done/verified · `[~]` partial · `[ ]` todo · `[?]` needs decision

"Verified-live" = checked in the running app via the browser, not just by
reading code.

---

## A. Stability & correctness
- [x] Chat send → stream → turn-end is deterministic (root-cause `_silenceTimer` bug fixed; verified live)
- [x] Message queue drains correctly; #2 sends itself, no loop (verified live)
- [x] Queue survives reload (server-persisted, paused-restore; verified live)
- [x] Server always emits `[DONE]` (Phase 1; unit-tested)
- [x] No uncaught console errors on the chat page — cleared buffer, ran a fresh new-chat turn (reasoning model), 0 errors
- [~] Full Python test suite: 1778 pass / 31 fail / 83 skip. Triaged — the 31 are PRE-EXISTING failures in unrelated subsystems (email, gallery, search, documents, context-compaction, webhook) in this heavily-WIP tree, plus a few test-isolation artifacts (pass when run alone). **None are caused by the queue/ship work**; all my own tests pass. → see "Blocked / needs decision".
- [~] Graceful when a provider is down / key invalid — endpoint-health tracker + 2-pass resolver failover added earlier; not re-verified live this run.
- [~] Graceful first-run with NO models configured — code path verified graceful: with no teacher model the setup assistant returns `need_model` and the UI shows a friendly "pick a model in the card above — Groq (free, ~1 min)" + scrolls to the picker (no crash, no dead-end). Full fresh-DB browser walk still pending.

## B. Security
- [x] Auth required by default — `AUTH_ENABLED` defaults `true`; middleware gates all routes except a tight allowlist (auth/health/version/login/static)
- [x] Secrets encrypted at rest (Fernet, `src/secret_storage.py`; confirmed keys stored as `enc:`)
- [x] **FIXED** — systemd service binds `127.0.0.1` (was `0.0.0.0`). Start scripts already defaulted to localhost; `AUTH_ENABLED=true`; `LOCALHOST_BYPASS` defaults false.
- [x] No secret values in logs — scanned; logs reference keys ("failed with API key: HTTP 403") but never print values
- [x] CORS not wide-open — defaults to `http://localhost,http://127.0.0.1`
- [x] Security headers present — X-Content-Type-Options, Referrer-Policy, per-request CSP nonce, X-Frame-Options SAMEORIGIN
- [x] Admin endpoints gated (`require_admin`); new `/api/queue/*` are auth-gated + owner-scoped + size-bounded
- [~] `/security-review` not run as a formal pass; manual audit of the new queue surface done (parameterized ORM, bounded, owner-checked — clean)
- [ ] `SECURITY.md` / `THREAT_MODEL.md` re-read for accuracy (not done this run)

## C. First-run / onboarding
- [x] Settings AI-guide explains each setting (leakage bug fixed; verified live)
- [x] Atlas setup guide is decisive + concise + offers starter suggestions (see G) — source-level review done; live test pending browser
- [~] Path to first chat / setup wizard — code present; source-reviewed for cohesion/dead-ends (see notes below); not walked end-to-end in a browser (needs fresh/logged-out state)
- [~] No confusing dead-ends on core tabs — chat audited live earlier; setup/onboarding flow source-reviewed this run (need_model handled, action loop maps every action to a real endpoint, `done` is server-gated against premature completion, and both success-screen links `/` + `/app/office` resolve). Other tabs not swept live.
- [?] Default model tier — recommendation below (acting as guidance; no key shipped)

## D. Packaging & install
- [x] `requirements.txt` present (41 deps)
- [x] `README` install steps accurate + consistent with secure defaults (native uvicorn `--host 127.0.0.1`, Docker, opt-in LAN via `ODYSSEUS_HOST=0.0.0.0`)
- [ ] Clean install in a fresh venv — not run (needs throwaway env)
- [ ] Docker image builds + runs — not run (needs throwaway env)
- [ ] First-run from empty DB — `create_all` + migrations exist; new `queued_messages` table auto-creates (confirmed table created on restart)

## E. Cleanup
- [x] No stray debug `console.warn/log` left in chat.js (temp diagnostics removed)
- [x] No `.bak`/scratch files tracked by git (all untracked → won't ship)
- [x] **Hardened `.gitignore`** — added `*.bak`, `*.bak-*`, `*.orig`, `=0.*` so backups can never be accidentally committed
- [~] `window.turnManager` left exposed as a read-only debug aid (harmless, client-only). Remove before a polished public release if you prefer.
- [x] Dead band-aid removed (20s queue-kick) in the hardening pass

## F. Privacy / local-first
- [x] No telemetry / phone-home — scanned: no posthog/segment/GA/sentry/amplitude; only a LOCAL `search_analytics.json`; no non-model outbound calls
- [x] Data stays local unless a cloud model is chosen
- [x] Cloud model usage opt-in + cost-clear (tiering now correct: Zen free/paid, Go subscription)

## G. Polish & branding
- [x] AI-guide no longer leaks reasoning (fixed)
- [x] Model tiering correct
- [x] **Download UX** — each active download now has a visual progress bar + approximate time remaining (shard-corrected overall %, overall-throughput ETA, resume-safe). Served-asset + V8 + unit-test verified; live visual click-test pending browser reconnect.
- [x] **Atlas setup guide** — fixed the "identity crisis" (Atlas is the decisive expert; user only decides privacy-vs-cloud + spending) and the narration leak (conclusion-only, max 2 sentences, banned narration openers). Added starter-suggestion chips for common setups. Prompt + chips in source; live conversational test pending browser reconnect.
- [x] "Mentor" branding for all user-FACING surfaces — DONE (decision #1 = Mentor). Renamed: composer placeholder (fixed the resize-revert bug), login + landing `<title>` + wordmark, MCP authorize title. Internal IDs (localStorage `odysseus-*`, CSS `.odysseus-*`, `window.__odysseus*`, BroadcastChannel/cache names), the persona preset, and repo-origin/attribution + comments intentionally KEPT (~270 refs).
- [ ] Full broken-link/404 nav sweep — not done

## H. Docs
- [x] `LICENSE`, `CONTRIBUTING`, `SECURITY` present
- [x] `README` install accurate
- [x] Known limitations documented (below)

### Known limitations (for new users)
- **GPU-in-Docker for local model serving** can be finicky (NVIDIA Container
  Toolkit / AMD ROCm passthrough); native install is the smoothest path for
  Cookbook model-serving.
- **Cloud models cost money / need your own key.** No key is shipped. Local
  Ollama and free-tier keys (Groq, OpenRouter `:free`) are the free paths.
- **Single-machine focus.** Auth + bind default to localhost; deliberate LAN
  exposure requires a reverse proxy / Tailscale + auth (never raw on a LAN).
- **First run needs a model.** With none configured you get a setup prompt;
  the AI-guide explains settings once a teacher/utility model is set.
- **Reasoning models** stream a thinking block first; the "Still thinking…"
  hint is normal during long reasoning, not a hang.

---

## Decisions made autonomously (acting on my recommendation)
1. **Bind `127.0.0.1` by default** → DONE (systemd service fixed).
2. **Auth required by default** → already the default; confirmed.
3. **Aegis default mode `ask`** → recommended; not changed (need to confirm current default — deferred, low risk).
4. **Default model tier**: prefer local Ollama, else free-key tier via BYO-key wizard; never ship a shared key → guidance only, nothing shipped.
5. **Primary install path**: native (systemd/scripts) documented first, Docker alternative → README already orders it sensibly.
7. **Telemetry**: confirmed NONE exists; recommend keeping it that way → no action needed.

## Decisions — RESOLVED (Robert accepted all recommendations)
- **Branding** = "Mentor" (product) / "Odysseus" (repo-origin + persona). → user-facing rename DONE.
- **Test-suite** = separate stabilization effort; does not block ship.
- **Telemetry** = none (confirmed); keep it that way.
- **Bind / auth / install path** = localhost + auth-required + native-primary. → done/confirmed.

## Remaining — needs a clean environment or interactive step (yours to run)
- **Clean-install / Docker verification** — one `git clone` → venv → run, and
  one `docker compose up`, on a spare box/VM. I won't run these on your live
  machine. *(Recommended pre-release gate.)*
- **First-run walkthrough** — verify the new-user setup wizard end-to-end. This
  needs interactive admin-account creation (password entry), which I can't do.
  Spin up a fresh-`DATA_DIR` instance and walk it once.
- **Test-suite stabilization** — separate effort when you want it (31 pre-existing
  failures in email/gallery/search/document/context-compaction subsystems).
