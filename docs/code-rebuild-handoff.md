# Mentor — Code-ombygging: konsolidering & videreføring

> Overleveringsdokument. Start en ny Code-tråd fra dette. Skrevet 2026-06-09.
> Alt arbeid ligger **ucommittet** på git-branchen `code/agentic-rebuild` i `~/odysseus`.

---

## 1. Hva vi gjorde denne økten (alle spor)

| Spor | Status | Hvor |
|---|---|---|
| Mentor dock-ikon (W-ikon-bug) | ✅ Ferdig & verifisert | `~/.local/share/applications/mentor.desktop` |
| Office — "bare for syns skyld?" | ✅ Besvart (ekte funksjon, men sekvensiell på solo-GPU) | — |
| **Code — fungerer ikke / skal bli som Claude Code** | 🟡 Diagnose + 1 fiks landet, resten i kø | `src/code_edit.py`, `routes/code_routes.py` |
| Caveman (token-kompressor) | 🔎 Diagnostisert, venter | `plugins/caveman/` |
| Køe-funksjon i chat ("kjør nå") | 🟡 Implementert, mangler reload-test | `static/js/chat.js`, `static/style.css` |
| Upstream-bidrag til pewdiepie/odysseus | 💬 Rådgivning gitt | — |

---

## 2. CODE — hovedsporet (full status)

### Diagnose: tre separate bugs

1. **Feil modell-ruting (rotårsaken til "gjør ingenting").**
   `data/settings.json` hadde `aider_model = opencode/minimax-m2.7`. Du har TO opencode-endepunkter
   som begge inneholder `minimax-m2.7`:
   - `OpenCode` → `https://opencode.ai/zen/v1` (pay-as-you-go)
   - `OpenCode Go` → `https://opencode.ai/zen/go/v1` (abonnement)

   `resolve_aider_model` tok det *første* som matchet (Zen) → minimax rutes pay-as-you-go →
   `AuthenticationError: Insufficient balance`. Go-endepunktet (som dekker den) ble aldri valgt.

2. **`run_edit` lyver om suksess.** Sjekker aldri Aiders exit-kode — returnerer alltid
   "Aider applied the change" med `exit_code: 0`, selv ved auth-krasj.

3. **"+59/−28"-diffen er ikke fra Aider.** Den viser `git diff` på *hele* repoet, dvs.
   dine ~21 filer med ucommittede endringer fra annet arbeid — ikke kjøringens endringer.

### Beslutninger (bekreftet med deg)

- **Motor:** bygg Code på din egen `src/agent_loop.py` (flerrunde tool-loop), IKKE ett aider-skudd.
  Behold aider som valgfri "rask ett-skudd"-motor.
- **Standardmodell:** `minimax-m2.7@OpenCode Go` (sterk, stor kontekst, dekket av Go-abonnement,
  null lokal VRAM). Alternativer å teste: `minimax-m3`, `glm-5.1` (best tool-calling ~94%).
  **Lokal fallback:** `qwen3.6:27b` (SWE-bench 77.2, ~17 GB; mer stabil enn qwen3-coder:30b på 24GB-GPU delt med desktop).
- **KOSTNADS-SIKKERHET (hardt krav etter token-sprekken din):** Code-agenten kjøres med
  `relevant_tools`-allowlist = `{read_file, write_file, bash, plan_task}` og `disabled_tools`
  som sperrer `ask_teacher`, `chat_with_model`, `pipeline`, `trigger_research`. Ingen kodesti
  kan eskalere til Claude. Strammere `max_rounds` (~25, ikke globale 60). Modell pinnet til Go/lokal.

### Gjort så langt (på branch `code/agentic-rebuild`)

- ✅ **Go-ruting fikset** i `src/code_edit.py` → `resolve_aider_model` sorterer nå `/zen/go/`-endepunkt
  først, så minimax/glm/kimi/qwen3-coder/deepseek rutes via abonnementet. (Kompilerer OK.)
  *Alternativ/renere vei finnes også:* lagre spec-en som `minimax-m2.7@OpenCode Go` — `_resolve_model`
  støtter `modell@endepunkt`-syntaks og treffer Go-endepunktet direkte.

### Gjenstår (kø) — se oppgaveliste i §3

- Bygg `src/code_agent.py` (agentisk motor på `stream_agent_loop`).
- Koble `routes/code_routes.py` `_run_job` til ny motor (default agentisk, aider som toggle).
- Gjør `run_edit` ærlig: sjekk `proc.returncode` + logg for feilmarkører; diff kun mot
  snapshot tatt FØR kjøringen (`git stash create` som baseline) så pre-eksisterende endringer ekskluderes.
- Sett `aider_model`-default til Go-spec-en.
- Test ende-til-ende på en kast-bort-branch.

### Design for `src/code_agent.py` (klar til å skrives)

```text
run_agentic_edit(instruction, files, project, model, owner, auto_branch, progress_cb, line_cb):
  - valider repo/instruks/modell (speil run_edit)
  - lag trygg branch hvis på main/master
  - snapshot = git rev-parse HEAD (for scoped diff)
  - url, model_id, headers = _resolve_model(model, owner)   # foretrekk Go
  - messages = [system(coding-prompt m/ repo-sti + utforsk→rediger→verifiser), user(instruks)]
  - async for ev in stream_agent_loop(url, model_id, messages, headers=headers,
        relevant_tools={read_file,write_file,bash,plan_task},
        disabled_tools={ask_teacher,chat_with_model,pipeline,trigger_research,...},
        max_rounds=25, owner=owner, temperature=0.2):
       parse SSE-event → oversett til job["stage"] / job["live_log"] (samme felt som i dag)
         delta→akkumuler svar; tool_start→stage+log; tool_output→log; agent_step→"runde N"
  - til slutt: diff = git diff <snapshot>  (kun kjøringens endringer)
  - returner {response(=agentens oppsummering), diff, log, branch_created, exit_code(ærlig)}
```

Nøkkel-signatur som finnes: `stream_agent_loop(endpoint_url, model, messages, headers=, temperature=,
max_tokens=, max_rounds=, owner=, session_id=, disabled_tools=, relevant_tools=, fallbacks=)`
— yielder SSE: `delta`, `tool_start`, `tool_output`, `agent_step`, `metrics`, `[DONE]`.

NB om bash/filer: agent_loops `bash` kjører i appens cwd. For repoer ≠ ~/odysseus må system-prompten
instruere absolutte stier under `project` / `cd <project>`. (~/odysseus er cwd by default, så vanligste tilfelle funker.)

---

## 3. Oppgavekø (task list)

- [x] Mentor dock-ikon: `--class` + `StartupWMClass=chrome-127.0.0.1__app-Default`
- [x] (Code) Go-ruting i `resolve_aider_model`
- [ ] Bygg agentisk Code-backend på `agent_loop` (`src/code_agent.py`)
- [ ] Koble Code-siden til agentisk motor + aider-fallback-toggle
- [ ] Gjør aider `run_edit` ærlig (exit-kode + scoped diff)
- [ ] Test Code ende-til-ende (verifiser at minimax rutes via Go uten balance-feil)
- [~] Køe "kjør nå"-handling — implementert, mangler reload-test

### Senere i kø (egne spor, ikke startet)

- **Modell-pratsomhet:** hard "vær konsis"-instruks/lengdetak i system-prompten (løser "for lange svar" — IKKE en caveman-sak).
- **Caveman → "Laconic":** gjør kompresjonen faktisk effektiv (nå ~5%), grønn live-indikator i chat
  (rute `/api/plugins/caveman/stats` finnes), og navnebytte (rører mange filer + setting-nøkler → bekreft først).
- **Upstream-bidrag:** fork → ren grein fra `upstream/main` → cherry-pick KUN køe-endringen → PR. Plugin-API krever issue først.

---

## 4. Git / fil-tilstand (viktig for ren videreføring)

- **Branch:** `code/agentic-rebuild` (ut fra `feat/self-improvement-stack`).
- **Mine endringer denne økten (ucommittet):** `src/code_edit.py` (Go-ruting),
  `static/js/chat.js` + `static/style.css` (køe-funksjon).
- **OBS:** `chat.js` og `style.css` hadde *allerede* ucommittede endringer før økten — mine ligger oppå.
  For en ren upstream-PR må køe-endringen isoleres (cherry-pick fra fersk `upstream/main`).
- **Ingenting er committet.** Vurder å committe køe-arbeidet for seg så det ikke blandes med Code-rebuilden.
- Repoet er **344 commits bak** og **131 foran** `origin/main` (origin = upstream pewdiepie/odysseus).

---

## 5. Køe-funksjon "kjør nå" (Codex-CLI-stil) — hva som ble bygd

I `static/js/chat.js`:
- `_runNow(idx)`: løfter valgt kø-element fremst, **avbryter** pågående tur, og det sendes umiddelbart.
  Halvskrevet melding i komponisten køes (mistes ikke). Ikke-streaming → drainer med en gang.
- **Den avbrutte oppgaven re-køes** rett bak den fremskutte (`_activeTurnText` spores ved stream-start,
  settes til null ved idle) og merkes `_resumed` → fullføres så snart den fremskutte er ferdig.
- Ny ▶-knapp per kø-chip + grønn hover; gjenopptatte elementer vises med `↻` + tooltip.

Mangler: **hard-reload i appen og en faktisk test** (sandboksen har ikke `node`, så kun statisk sjekk er gjort:
kompilerer/balanserte klammer).

---

## 6. Hvor du tar opp tråden (neste konkrete steg)

1. (Anbefalt start) Skriv `src/code_agent.py` etter designet i §2.
2. Koble `_run_job` i `routes/code_routes.py` til den (default agentisk; behold `run_edit` som toggle).
3. Gjør `run_edit` ærlig + scoped diff.
4. Sett `aider_model` = `minimax-m2.7@OpenCode Go`.
5. Test på en kast-bort-branch i et lite repo først.
