#!/usr/bin/env python3
"""Codex / ChatGPT-subscription proxy — an OpenAI-compatible /v1/chat/completions
endpoint backed by the official ``codex exec`` CLI (logged in via ChatGPT OAuth).

Ban-safe by design, mirroring integrations/claude-proxy: it talks to OpenAI ONLY
through the sanctioned ``codex`` binary using your real OAuth login. It never
scrapes ~/.codex tokens or replays them against ChatGPT's backend (that is what
gets accounts banned). Keep volume low and serial, and bind to localhost only.

Run:  python codex_proxy.py --port 8775
Then register http://127.0.0.1:8775/v1 as a model endpoint in Mentor.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CODEX_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CODEX_PROXY_PORT", "8775"))
CODEX_BIN = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
TIMEOUT = int(os.environ.get("CODEX_PROXY_TIMEOUT", "180"))
REQUIRED_KEY = os.environ.get("CODEX_PROXY_KEY", "")  # optional bearer to guard the local port
REAL_HOME = os.environ.get("HOME") or os.path.expanduser("~")
SCRATCH = tempfile.gettempdir()
# Advertised model id. The actual model is whatever `codex` is configured to use
# for your ChatGPT login — we don't force one, so we never send an invalid -m.
MODELS = ["codex"]
RETRIES = int(os.environ.get("CODEX_PROXY_RETRIES", "1"))

_TRANSIENT = ("overloaded", "rate limit", "429", "529", "503", "502", "500",
              "timed out", "timeout", "connection", "temporarily", "try again", "unavailable")
_AUTH = ("not logged in", "login", "unauthorized", "401", "403", "authentication")


def _now() -> int:
    return int(time.time())


def _clean_env() -> dict:
    """Env so `codex` uses the real ChatGPT OAuth login at ~/.codex — strip any
    OPENAI_API_KEY/base override that would bypass the subscription login."""
    env = dict(os.environ)
    for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"):
        env.pop(k, None)
    env["HOME"] = REAL_HOME
    return env


def _text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("text", None):
                out.append(str(b.get("text", "")))
            elif isinstance(b, str):
                out.append(b)
        return "\n".join(out)
    return "" if content is None else str(content)


def _flatten(messages: list):
    system_parts, convo = [], []
    for m in messages or []:
        role = m.get("role", "user")
        text = _text_from_content(m.get("content"))
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            convo.append("Assistant: " + text)
        else:
            convo.append("User: " + text)
    system = "\n\n".join(system_parts).strip()
    if len(convo) <= 1:
        user = convo[0][6:] if convo and convo[0].startswith("User: ") else (convo[0] if convo else "")
    else:
        user = ("Here is the conversation so far:\n\n" + "\n\n".join(convo)
                + "\n\nWrite the next Assistant reply to the final User turn. Reply with the answer only.")
    return system, user


def _invoke(system: str, user: str):
    """One codex exec call. Returns (ok, text_or_error, transient)."""
    prompt = ((system + "\n\n") if system else "") + user
    out_path = os.path.join(SCRATCH, "codexproxy-" + uuid.uuid4().hex[:12] + ".txt")
    cmd = [CODEX_BIN, "exec", "-s", "read-only", "--skip-git-repo-check",
           "--ephemeral", "--color", "never", "-o", out_path, "-"]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              env=_clean_env(), cwd=SCRATCH, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "codex CLI timed out after %ss" % TIMEOUT, True
    text = ""
    try:
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read().strip()
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
    if not text:
        text = (proc.stdout or "").strip()
    if not text:
        err = "codex returned nothing (exit %s). %s" % (proc.returncode, (proc.stderr or "")[:400])
        low = err.lower()
        if any(a in low for a in _AUTH):
            return False, "Not logged in to Codex/ChatGPT — run `codex login`.", False
        return False, err, any(t in low for t in _TRANSIENT)
    return True, text, False


def _run(system: str, user: str):
    last = "codex error"
    for attempt in range(RETRIES + 1):
        ok, text, transient = _invoke(system, user)
        if ok:
            return True, text
        last = text
        if not transient or attempt == RETRIES:
            break
        time.sleep(2.0 * (2 ** attempt))
    return False, last


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[codex-proxy] " + (fmt % args) + "\n")

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        if not REQUIRED_KEY:
            return True
        return self.headers.get("Authorization", "").replace("Bearer ", "").strip() == REQUIRED_KEY

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", "/v1/health"):
            return self._json(200, {"status": "ok"})
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model", "created": _now(), "owned_by": "codex"} for m in MODELS]})
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
            return self._json(400, {"error": {"message": "bad request: %s" % e}})
        system, user = _flatten(payload.get("messages", []))
        if not user:
            return self._json(400, {"error": {"message": "no user content"}})
        ok, text = _run(system, user)
        if not ok:
            return self._json(502, {"error": {"message": text, "type": "codex_cli_error"}})
        cid = "chatcmpl-" + uuid.uuid4().hex[:24]
        model_req = payload.get("model", "codex")
        if payload.get("stream"):
            return self._stream(cid, model_req, text)
        return self._json(200, {
            "id": cid, "object": "chat.completion", "created": _now(), "model": model_req,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})

    def _stream(self, cid, model, text):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def chunk(delta, finish=None):
            obj = {"id": cid, "object": "chat.completion.chunk", "created": _now(), "model": model,
                   "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            self.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode())
            self.wfile.flush()

        chunk({"role": "assistant"})
        step = max(1, len(text) // 40) or 1
        for i in range(0, len(text), step):
            chunk({"content": text[i:i + step]})
        chunk({}, finish="stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--host", default=HOST)
    args = ap.parse_args()
    if not CODEX_BIN or not os.path.exists(CODEX_BIN):
        sys.stderr.write("[codex-proxy] codex CLI not found — install it and `codex login`.\n")
        sys.exit(2)
    sys.stderr.write("[codex-proxy] OpenAI-compatible Codex proxy on http://%s:%s (HOME=%s)\n"
                     % (args.host, args.port, REAL_HOME))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
