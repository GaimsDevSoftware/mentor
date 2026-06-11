# Mentor / Odysseus — Ship-Readiness Checklist

Goal: everything that must be true before shipping this app to other users
(self-hosted, local-first AI workspace). Worked top-to-bottom. Each open
decision carries a **recommendation** (what I'd advise) so work can continue
without blocking. Items marked **[NEEDS ROBERT]** genuinely need your call.

Legend: `[x]` done · `[~]` in progress / partial · `[ ]` todo · `[?]` needs decision

Status key updated live as work proceeds. Verified-live items were checked in
the running app via the browser, not just by reading code.

---

## A. Stability & correctness
- [x] Chat send → stream → turn-end is deterministic (root-cause `_silenceTimer` bug fixed; verified live)
- [x] Message queue drains correctly; #2 sends itself, no loop (verified live)
- [x] Queue survives reload (server-persisted, paused-restore; verified live)
- [x] Server always emits `[DONE]` (Phase 1; tested)
- [ ] Full Python test suite green (or every failure triaged as pre-existing/intentional)
- [ ] No uncaught console errors on core pages (chat, settings, cookbook, office, code, admin)
- [ ] Graceful first-run with NO models configured (welcome/setup, no white screen)
- [ ] Graceful when a provider is down / key invalid (endpoint-health + 2-pass failover already added)

## B. Security  (highest priority for a shippable self-hosted app)
- [ ] Auth required by default — no bypass in the default config
- [x] Secrets encrypted at rest (Fernet, `src/secret_storage.py`; verified keys stored `enc:`)
- [ ] Server binds to `127.0.0.1` by default, not `0.0.0.0` — verify + document deliberate exposure
- [ ] No diagnostic/admin endpoints reachable without admin auth
- [x] New `/api/queue/*` endpoints are owner-scoped (`_verify_session_owner`)
- [ ] Aegis tool-call firewall ON at a sane default mode
- [ ] No secrets in server logs, client payloads, or URLs
- [ ] CORS not wide-open
- [ ] `/security-review` run on the recent changes; findings triaged
- [ ] `SECURITY.md` / `THREAT_MODEL.md` still accurate

## C. First-run / onboarding
- [ ] Fresh user → clear path to first working chat (model-setup wizard)
- [x] Settings AI-guide explains each setting (leakage bug fixed; verified)
- [ ] Setup concierge works end-to-end (or is clearly optional)
- [ ] Sensible default model tier (see decision below)
- [ ] No confusing dead-ends / empty states on core tabs

## D. Packaging & install
- [ ] `requirements.txt` complete; clean install in a fresh venv
- [ ] Install scripts work (`install-service.sh`, `start-macos.sh`, `launch-windows.ps1`)
- [ ] Docker image builds + runs (`docker-compose.yml`)
- [ ] `README` install steps accurate
- [ ] First-run DB creation/migration works from an empty DB

## E. Cleanup
- [ ] Debug exposes removed or gated (`window.turnManager`)
- [ ] Stray debug `console.warn/log` removed from hot paths
- [ ] `.bak` / scratch files not tracked by git / ignored
- [ ] Dead code from the queue-debugging saga removed

## F. Privacy / local-first
- [ ] No telemetry / phone-home by default
- [ ] Data stays local unless the user opts into a cloud model
- [ ] Cloud model usage is opt-in and clear about cost (tiering now correct)

## G. Polish & branding
- [x] AI-guide no longer leaks reasoning (fixed)
- [x] Model tiering correct (Zen free/paid, Go subscription)
- [ ] "Mentor" branding consistent app-wide (do NOT rebrand the Odysseus persona preset)
- [ ] No broken nav links / 404s

## H. Docs
- [ ] `README` accurate to current features
- [x] `LICENSE`, `CONTRIBUTING`, `SECURITY` present
- [ ] Known limitations documented

---

## Open decisions — with my recommendation (acting on these unless you override)

1. **Default bind address** → **Recommend `127.0.0.1` (localhost-only)**. A
   self-hosted personal app should never default to `0.0.0.0`. Document an
   explicit, deliberate opt-in for LAN exposure. *(Acting on this.)*

2. **Auth by default** → **Recommend: required**, with a first-run admin
   setup. Shipping an unauthenticated AI app that can run tools/spend money is
   unsafe. *(Acting on this — verifying it's already the default.)*

3. **Aegis firewall default mode** → **Recommend `ask`** (prompt before risky
   tool calls). Safe for new users without being as noisy as `enforce`.
   *(Acting on this as the recommended default if not already.)*

4. **Default model tier for new users** → **Recommend: prefer local Ollama if
   present; otherwise a free-key tier (Groq / OpenRouter `:free`) via the BYO-key
   wizard.** Never ship a shared embedded key. Matches the local-first promise
   and the cost research. *(Acting on this as guidance; no secret shipped.)*

5. **Primary install path** → **Recommend: native (systemd / start scripts) as
   the documented primary for the local-first story; Docker as the alternative.**
   Both already exist. *(Acting on this for docs ordering.)*

6. **[NEEDS ROBERT]** Public distribution channel (GitHub release of this fork?
   under what name — "Mentor"? "Odysseus"?) and license posture for the rebrand.
   This affects branding cleanup and README framing — your call.

7. **[NEEDS ROBERT]** Is there any analytics/telemetry you WANT (even opt-in)?
   Default assumption: none. Confirm.
