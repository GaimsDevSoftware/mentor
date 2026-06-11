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
- [ ] Graceful first-run with NO models configured — needs a fresh/empty-DB instance to verify (see Blocked).

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
- [~] Path to first chat / setup wizard — code present; not walked end-to-end (needs fresh/logged-out state)
- [ ] No confusing dead-ends on core tabs — only chat audited live this run
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
- [?] "Mentor" vs "Odysseus" branding consistency — depends on the naming decision (Blocked). Concrete state: **275 "Odysseus" vs 65 "Mentor"** refs in static JS/HTML; title bars say "Mentor", login + landing pages say "Odysseus". A mass rename must spare the Odysseus *persona preset* and legitimate upstream/repo-origin mentions — too risky to automate blind.
- [ ] Full broken-link/404 nav sweep — not done

## H. Docs
- [x] `LICENSE`, `CONTRIBUTING`, `SECURITY` present
- [x] `README` install accurate
- [ ] Known limitations documented (not done)

---

## Decisions made autonomously (acting on my recommendation)
1. **Bind `127.0.0.1` by default** → DONE (systemd service fixed).
2. **Auth required by default** → already the default; confirmed.
3. **Aegis default mode `ask`** → recommended; not changed (need to confirm current default — deferred, low risk).
4. **Default model tier**: prefer local Ollama, else free-key tier via BYO-key wizard; never ship a shared key → guidance only, nothing shipped.
5. **Primary install path**: native (systemd/scripts) documented first, Docker alternative → README already orders it sensibly.
7. **Telemetry**: confirmed NONE exists; recommend keeping it that way → no action needed.

## Blocked / needs Robert
- **[NEEDS ROBERT] Branding name** — ship as "Mentor" or "Odysseus"? The app
  mixes both (title=Mentor, login/docs=Odysseus). This blocks item G (branding
  consistency) and README framing. My rec: pick "Mentor" as the product name
  (per your north-star), keep "Odysseus" only where it's the upstream/repo
  origin + the persona preset (do NOT rename the persona).
- **[NEEDS ROBERT] Test-suite policy** — 31 pre-existing failures in unrelated
  subsystems. Block ship on a full green suite, or triage as a separate
  stabilization effort? My rec: separate effort — they don't touch the core
  chat/queue/security paths, and fixing them blind risks regressions.
- **[NEEDS ROBERT] Clean-install / Docker verification** — needs a throwaway
  environment (I won't run a full Docker build or `install-service.sh` on your
  live machine). My rec: do one clean `git clone` → venv → run, and one
  `docker compose up` on a spare box or VM before release.
- **First-run walkthrough** — needs a logged-out / empty-DB instance to verify
  the new-user setup wizard has no dead-ends. My rec: spin up a throwaway
  instance (fresh DATA_DIR) and walk it once.
