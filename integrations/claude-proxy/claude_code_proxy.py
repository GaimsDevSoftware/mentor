#!/usr/bin/env python3
"""
claude_code_proxy.py — OpenAI-compatible HTTP shim in front of the Claude Code CLI.

Lets Odysseus (or any OpenAI-compatible client) use your Claude *subscription*
(OAuth login, no API key) as a model endpoint. The proxy receives standard
`/v1/chat/completions` requests, runs `claude -p` under the hood, and returns the
answer in OpenAI shape. Used as Odysseus' `teacher_model` it powers the
student→teacher escalation loop, so the small local models get coached by Claude.

Design notes
------------
* Stdlib only — no pip installs. Runs anywhere Python 3.9+ and `claude` exist.
* Environment sanitation: any harness that injected ANTHROPIC_BASE_URL /
  ANTHROPIC_API_KEY / CLAUDE_CONFIG_DIR would redirect the CLI away from your
  real OAuth login. We strip those and pin HOME before each call.
* Runs the CLI in an empty scratch dir so it does NOT load a project's
  CLAUDE.md (keeps prompts small and answers neutral).
* Tools are disabled by default (`--max-turns 1`) so it behaves like a plain
  chat model, not an autonomous agent poking at your files. Override via
  CLAUDE_PROXY_EXTRA_ARGS if you want tool use.

Config via env (all optional):
  CLAUDE_PROXY_HOST        default 127.0.0.1
  CLAUDE_PROXY_PORT        default 8750
  CLAUDE_PROXY_HOME        default /home/robert   (where ~/.claude lives)
  CLAUDE_PROXY_BIN         default claude
  CLAUDE_PROXY_MODEL       default sonnet         (fallback model alias)
  CLAUDE_PROXY_TIMEOUT     default 300            (seconds per call)
  CLAUDE_PROXY_API_KEY     default "" (if set, clients must send this Bearer token)
  CLAUDE_PROXY_EXTRA_ARGS  default "" (extra args appended to the claude command)
"""

import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CLAUDE_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLAUDE_PROXY_PORT", "8750"))
REAL_HOME = os.environ.get("CLAUDE_PROXY_HOME", os.path.expanduser("~"))
CLAUDE_BIN = os.environ.get("CLAUDE_PROXY_BIN", "claude")
DEFAULT_MODEL = os.environ.get("CLAUDE_PROXY_MODEL", "sonnet")
TIMEOUT = int(os.environ.get("CLAUDE_PROXY_TIMEOUT", "300"))
REQUIRED_KEY = os.environ.get("CLAUDE_PROXY_API_KEY", "").strip()
EXTRA_ARGS = shlex.split(os.environ.get("CLAUDE_PROXY_EXTRA_ARGS", ""))

SCRATCH_DIR = os.path.join(REAL_HOME, ".cache", "claude-code-proxy")
os.makedirs(SCRATCH_DIR, exist_ok=True)

# Models advertised to the client. The suffix picks the Claude tier.
MODELS = ["claude-code-sonnet", "claude-code-opus", "claude-code-haiku", "claude-code"]


def _clean_env() -> dict:
    """Environment that makes `claude` use the real OAuth login at $HOME/.claude."""
    env = dict(os.environ)
    for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(k, None)
    env["HOME"] = REAL_HOME
    return env


def _model_alias(requested: str) -> str:
    r = (requested or "").lower()
    if "opus" in r:
        return "opus"
    if "haiku" in r:
        return "haiku"
    if "sonnet" in r:
        return "sonnet"
    return DEFAULT_MODEL


def _text_from_content(content) -> str:
    """OpenAI message content may be a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("text", None):
                parts.append(str(b.get("text", "")))
            elif isinstance(b, str):
                parts.append(b)
        return "\n".join(parts)
    return "" if content is None else str(content)


def _flatten(messages: list) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the CLI from OpenAI messages."""
    system_parts, convo = [], []
    for m in messages or []:
        role = m.get("role", "user")
        text = _text_from_content(m.get("content"))
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            convo.append(f"Assistant: {text}")
        else:
            convo.append(f"User: {text}")
    system = "\n\n".join(system_parts).strip()
    if len(convo) <= 1:
        # Single turn — feed the raw user text, no transcript framing.
        user = convo[0][6:] if convo and convo[0].startswith("User: ") else (convo[0] if convo else "")
    else:
        user = (
            "Here is the conversation so far:\n\n"
            + "\n\n".join(convo)
            + "\n\nWrite the next Assistant reply to the final User turn. "
            "Reply with the answer only."
        )
    return system, user


# How many times to retry a TRANSIENT CLI failure (overloaded / rate-limit /
# 5xx / network blips) before giving up. Auth failures are never retried.
RETRIES = int(os.environ.get("CLAUDE_PROXY_RETRIES", "2"))
RETRY_BACKOFF = float(os.environ.get("CLAUDE_PROXY_RETRY_BACKOFF", "2.0"))

# Substrings that mark an error as transient (worth retrying) vs. permanent.
_TRANSIENT_MARKERS = (
    "overloaded", "rate limit", "rate_limit", "ratelimit", "429", "529",
    "503", "502", "500", "internal server", "timed out", "timeout",
    "connection", "temporarily", "try again", "unavailable", "econnreset",
)
_AUTH_MARKERS = ("not logged in", "/login", "invalid api key",
                 "authentication", "unauthorized", "401", "403")


def _is_transient(msg: str) -> bool:
    m = (msg or "").lower()
    if any(a in m for a in _AUTH_MARKERS):
        return False  # auth won't fix itself by retrying
    return any(t in m for t in _TRANSIENT_MARKERS)


def _invoke_claude(system: str, user: str, model: str) -> tuple[bool, str, bool]:
    """One CLI invocation. Returns (ok, text_or_error, transient)."""
    cmd = [CLAUDE_BIN, "-p", "--output-format", "json", "--model", model, "--max-turns", "1"]
    if system:
        cmd += ["--append-system-prompt", system]
    cmd += EXTRA_ARGS
    try:
        proc = subprocess.run(
            cmd, input=user, capture_output=True, text=True,
            env=_clean_env(), cwd=SCRATCH_DIR, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"claude CLI timed out after {TIMEOUT}s", True
    raw = (proc.stdout or "").strip()
    if not raw:
        err = f"claude CLI returned nothing (exit {proc.returncode}). stderr: {(proc.stderr or '')[:500]}"
        return False, err, True  # empty output is usually a transient crash
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Some CLI versions may print plain text — accept it.
        return True, raw, False
    if data.get("is_error"):
        msg = str(data.get("result") or data.get("api_error_status") or "claude CLI reported an error")
        return False, msg, _is_transient(msg + " " + str(data.get("api_error_status", "")))
    return True, str(data.get("result", "")), False


def _run_claude(system: str, user: str, model: str) -> tuple[bool, str]:
    """Run the CLI, retrying transient failures with backoff so a momentary
    overload/rate-limit blip doesn't surface to the client as a 502."""
    last = "claude CLI reported an error"
    for attempt in range(RETRIES + 1):
        ok, text, transient = _invoke_claude(system, user, model)
        if ok:
            return True, text
        last = text
        if not transient or attempt == RETRIES:
            break
        delay = RETRY_BACKOFF * (2 ** attempt)
        sys.stderr.write(f"[proxy] transient CLI error (attempt {attempt + 1}/{RETRIES + 1}), "
                         f"retrying in {delay:.0f}s: {text[:160]}\n")
        time.sleep(delay)
    return False, last


def _now() -> int:
    return int(time.time())


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("[proxy] " + (fmt % args) + "\n")

    # ---- helpers ----
    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        if not REQUIRED_KEY:
            return True
        auth = self.headers.get("Authorization", "")
        return auth.replace("Bearer ", "").strip() == REQUIRED_KEY

    # ---- routes ----
    def do_GET(self):
        if self.path.rstrip("/") in ("/health", "/v1/health"):
            return self._json(200, {"status": "ok"})
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {
                "object": "list",
                "data": [{"id": m, "object": "model", "created": _now(), "owned_by": "claude-code"} for m in MODELS],
            })
        return self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "not found"}})
        if not self._auth_ok():
            return self._json(401, {"error": {"message": "invalid api key"}})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            return self._json(400, {"error": {"message": f"bad request: {e}"}})

        model_req = payload.get("model", DEFAULT_MODEL)
        model = _model_alias(model_req)
        system, user = _flatten(payload.get("messages", []))
        if not user:
            return self._json(400, {"error": {"message": "no user content"}})

        ok, text = _run_claude(system, user, model)
        if not ok:
            return self._json(502, {"error": {"message": text, "type": "claude_cli_error"}})

        cid = "chatcmpl-" + uuid.uuid4().hex[:24]
        if payload.get("stream"):
            return self._stream(cid, model_req, text)

        return self._json(200, {
            "id": cid, "object": "chat.completion", "created": _now(), "model": model_req,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def _stream(self, cid: str, model: str, text: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def chunk(delta: dict, finish=None):
            obj = {
                "id": cid, "object": "chat.completion.chunk", "created": _now(), "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            self.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode())
            self.wfile.flush()

        chunk({"role": "assistant"})
        # Emit in a few slices so SSE clients render progressively.
        step = max(1, len(text) // 40) or 1
        for i in range(0, len(text), step):
            chunk({"content": text[i:i + step]})
        chunk({}, finish="stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main():
    print(f"[proxy] Claude Code proxy on http://{HOST}:{PORT}  (HOME={REAL_HOME}, model={DEFAULT_MODEL})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
