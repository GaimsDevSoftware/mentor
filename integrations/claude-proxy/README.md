# Claude Code proxy — bruk Claude-abonnementet (OAuth) som lærer i Odysseus

Odysseus' innebygde Anthropic-kobling krever en **API-nøkkel**. Du har et **abonnement
(OAuth)**, som er det Claude Code-kommandoen bruker. Denne proxy-en bygger bro: den ser ut
som et helt vanlig OpenAI-kompatibelt API utad, men kjører `claude -p` internt — så Odysseus
kan bruke abonnementet ditt uten API-nøkkel.

## Hva som allerede er satt opp

- `claude_code_proxy.py` — selve proxy-en (ren Python, ingen avhengigheter).
- systemd-brukertjeneste `claude-code-proxy.service` — kjører på `http://127.0.0.1:8750`,
  starter automatisk ved oppstart (linger er på).

Sjekk at den kjører:
```bash
systemctl --user status claude-code-proxy.service
curl -s http://127.0.0.1:8750/v1/models
```

## Koble den til Odysseus (gjøres i Odysseus-grensesnittet)

1. **Settings → Model Endpoints → Add endpoint** (eller Integrasjoner → legg til endpoint):
   - **Navn:** `Claude Code (OAuth)`
   - **Base URL:** `http://127.0.0.1:8750/v1`
   - **API key:** la stå tom (eller skriv hva som helst — proxy-en bryr seg ikke).
   - Lagre. Odysseus prober og finner modellene `claude-code-sonnet`, `claude-code-opus`,
     `claude-code-haiku`.

2. **Sett Claude som lærer.** Enkleste vei: skriv i Odysseus-chatten:
   > set teacher model to `claude-code-sonnet@Claude Code (OAuth)`

   og slå deretter på lærer-loopen (Settings, eller be chatten sette `teacher_enabled = true`).
   Formatet er alltid `modellnavn@endpointnavn`.

Nå skjer dette automatisk: når en liten lokal modell står fast, eskalerer Odysseus til
Claude via proxy-en, Claude foreslår riktig fremgangsmåte, og **løsningen lagres som en ny
SKILL.md** — så modellene blir gradvis flinkere.

## Innstillinger (miljøvariabler i tjenestefila)

| Variabel | Standard | Forklaring |
|---|---|---|
| `CLAUDE_PROXY_PORT` | 8750 | Porten proxy-en lytter på |
| `CLAUDE_PROXY_MODEL` | sonnet | Standardmodell (sonnet/opus/haiku) |
| `CLAUDE_PROXY_HOME` | /home/robert | Hvor `~/.claude` (OAuth-innlogget) ligger |
| `CLAUDE_PROXY_TIMEOUT` | 300 | Sekunder per kall |
| `CLAUDE_PROXY_API_KEY` | (tom) | Sett for å kreve at klienter sender en Bearer-token |
| `CLAUDE_PROXY_EXTRA_ARGS` | (tom) | Ekstra `claude`-argumenter, f.eks. skru på verktøy |

Endre, så `systemctl --user restart claude-code-proxy.service`.

## Viktige forbehold

- **Innlogging må holdes ved like.** Proxy-en bruker OAuth-sesjonen i `~/.claude`. Hvis du
  noen gang blir logget ut, kjør `claude` én gang i terminalen og logg inn på nytt.
- **Best som lærer, ikke som hverdagsmodell.** Hvert kall starter en CLI-prosess (noen
  sekunder) og bruker av abonnementets rate-grenser. Perfekt for sporadiske lærer-kall;
  ikke ment som modellen all chat går gjennom.
- **Svarer fra egen kunnskap.** Verktøy er av som standard (`--max-turns 1`), så Claude
  surfer ikke nettet selv — den coacher de små modellene i *hvordan* de skal bruke Odysseus'
  egne research-verktøy. Vil du la læreren bruke verktøy, sett `CLAUDE_PROXY_EXTRA_ARGS`.
- **Kun localhost.** Proxy-en lytter på 127.0.0.1 og har ingen egen autentisering med
  mindre du setter `CLAUDE_PROXY_API_KEY`. Ikke eksponer porten på nettverket.
