"""
Odysseus Web Backend — Standalone proxy + SPA server
Provides authentication layer and CORS forwarding to Odysseus API (localhost:7000)
"""

import os
import json
import secrets
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import FastAPI, Request, HTTPException, Depends, Form, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiohttp

# Configuration
ODYSSEUS_API = os.getenv("ODYSSEUS_API_URL", "http://127.0.0.1:7000")
API_KEY_FILE = Path(__file__).parent / ".api_key"
USER_DIR = Path(os.path.expanduser("~/.odysseus-web"))

app = FastAPI(title="Mentor Web", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: Dict[str, dict] = {}
SESSION_TIMEOUT = 24 * 3600


async def init_api_key():
    if not API_KEY_FILE.exists():
        USER_DIR.mkdir(parents=True, exist_ok=True)
        API_KEY_FILE.write_text(secrets.token_urlsafe(48))

@app.on_event("startup")
async def startup():
    await init_api_key()

def get_api_key() -> str:
    return API_KEY_FILE.read_text().strip()

async def require_auth(request: Request) -> dict:
    token = request.headers.get("X-Api-Key") or request.cookies.get("odysseus_token")
    if not token or token not in SESSIONS:
        raise HTTPException(401, "Authentication required")
    now = datetime.now(timezone.utc).timestamp()
    if now - SESSIONS[token]["created"] > SESSION_TIMEOUT:
        del SESSIONS[token]
        raise HTTPException(401, "Session expired")
    return SESSIONS[token]


@app.post("/api/auth/login", response_model=dict)
async def login(request: Request):
    key = (await request.json()).get("apiKey", "")
    if key == get_api_key():
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {"created": datetime.now(timezone.utc).timestamp()}
        resp = JSONResponse({"token": token, "status": "ok"})
        resp.set_cookie("odysseus_token", token, httponly=True, max_age=SESSION_TIMEOUT, samesite="lax")
        return resp
    raise HTTPException(403, "Invalid API key")

@app.post("/api/auth/login-form")
async def login_form(apiKey: str = Form(...)):
    if apiKey == get_api_key():
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {"created": datetime.now(timezone.utc).timestamp()}
        resp = JSONResponse({"token": token, "status": "ok"})
        resp.set_cookie("odysseus_token", token, httponly=True, max_age=SESSION_TIMEOUT, samesite="lax")
        return resp
    raise HTTPException(403, "Invalid API key")

@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get("odysseus_token")
    if token and token in SESSIONS:
        del SESSIONS[token]
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("odysseus_token")
    return resp

@app.post("/api/auth/me")
async def me(session: dict = Depends(require_auth)):
    return {"authenticated": True}


PROXY_PREFIXES = [
    "/api/calendar/", "/api/chat", "/api/codex/", "/api/compare/",
    "/api/contacts/", "/api/cookbook/", "/api/document/", "/api/documents/",
    "/api/editor-drafts/", "/api/email/", "/api/export", "/api/gallery/",
    "/api/history/", "/api/memory/", "/api/notes/", "/api/sessions/",
    "/api/settings/", "/api/tasks/", "/api/todos/", "/api/tokens/",
    "/api/conversations/", "/api/db/", "/api/assistant/",
]

async def proxy_to_odysseus(request: Request, path_suffix: str = "", method: Optional[str] = None):
    target_url = ODYSSEUS_API + request.url.path.lstrip("/api") + path_suffix
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "cookie")}
    m = method or request.method
    try:
        async with aiohttp.ClientSession(headers=headers) as sess:
            content_type = headers.get("content-type", "")
            
            if m in ("POST", "PUT", "PATCH"):
                if "multipart" in content_type:
                    form_data = await request.form()
                    post_data = aiohttp.FormData()
                    for key, value in form_data.items():
                        if isinstance(value, UploadFile):
                            contents = await value.read()
                            post_data.add_field(key.encode(), contents,
                                filename=value.filename, content_type=value.content_type)
                        else:
                            post_data.add_field(key, value)
                    body = post_data
                elif content_type.startswith("application/json"):
                    json_body = await request.json()
                    body = json.dumps(json_body).encode()
                else:
                    body = await request.body()
            elif m in ("GET", "HEAD"):
                qs = urlencode(request.query_params)
                if qs:
                    target_url += "?" + qs
                body = None
            
            async with sess.request(m, target_url, data=body) as resp:
                content = await resp.read()
                return StreamingResponse(
                    iter([content]),
                    status_code=resp.status,
                    headers={k: v for k, v in resp.headers.items() 
                            if k.lower() not in ("transfer-encoding", "content-length")},
                )
    except Exception as e:
        raise HTTPException(502, f"Odysseus API error: {str(e)}")


for prefix in PROXY_PREFIXES:
    @app.get(prefix, dependencies=[Depends(require_auth)])
    @app.post(prefix, dependencies=[Depends(require_auth)])
    @app.put(prefix, dependencies=[Depends(require_auth)])
    @app.patch(prefix, dependencies=[Depends(require_auth)])
    @app.delete(prefix, dependencies=[Depends(require_auth)])
    async def proxy_all(request: Request):
        return await proxy_to_odysseus(request)


@app.get("/api/health")
async def health():
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(ODYSSEUS_API + "/api/health", timeout=aiohttp.ClientTimeout(3)) as resp:
                data = await resp.json()
        return {"web": "ok", "odysseus": data}
    except Exception:
        return {"web": "ok", "odysseus": "unreachable"}

@app.get("/api/web/api-key")
async def get_api_key_endpoint(session: dict = Depends(require_auth)):
    return {"apiKey": get_api_key()}


FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    token = request.cookies.get("odysseus_token")
    is_authenticated = bool(token and token in SESSIONS)
    
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    
    return LOGIN_HTML


LOGIN_HTML = '''<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mentor Web — Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e0e0e0;
        }
        .login-container {
            width: 400px; min-width: 100%; max-width: 90%;
            background: #12122a; padding: 48px 40px;
            border-radius: 16px; box-shadow: 0 0 40px rgba(59, 130, 246, 0.1);
            border: 1px solid #1e1e3a;
        }
        h1 { text-align: center; margin-bottom: 8px; font-size: 1.8em; color: #f0f0f0; }
        .subtitle { text-align: center; color: #888; margin-bottom: 32px; font-size: 0.9em; }
        .logo { text-align: center; font-size: 3em; margin-bottom: 16px; }
        input[type="password"] {
            width: 100%; padding: 12px 16px; background: #1a1a30; border: 1px solid #2e2e4a;
            color: #e0e0e0; border-radius: 8px; font-size: 1em; outline: none;
            transition: border-color 0.2s; margin-bottom: 16px;
        }
        input:focus { border-color: #3b82f6 !important; }
        button {
            width: 100%; padding: 14px; background: #3b82f6; color: white;
            border: none; border-radius: 8px; font-size: 1em; cursor: pointer;
            transition: background 0.2s, transform 0.1s; font-weight: 600;
        }
        button:hover { background: #2563eb; }
        .error { color: #ef4444; text-align: center; margin-top: 12px; font-size: 0.9em; min-height: 1.2em; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">&#x1f9e0;</div>
        <h1>Mentor Web</h1>
        <p class="subtitle">Standalone web interface — Log in to continue</p>
        <form id="loginForm">
            <input type="password" id="apiKey" name="apiKey"
                   placeholder="API Key (found at ~/.odysseus-web/.api_key)" autocomplete="current-password" autofocus>
            <button type="submit">Sign In</button>
        </form>
        <p class="error" id="error"></p>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const apiKey = document.getElementById('apiKey').value;
            const errEl = document.getElementById('error');
            errEl.textContent = '';
            try {
                const formData = new FormData();
                formData.append('apiKey', apiKey);
                const res = await fetch('/api/auth/login-form', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) { window.location.href = '/'; }
                else { errEl.textContent = data.detail || 'Login failed'; }
            } catch(err) { errEl.textContent = 'Connection error'; }
        });
    </script>
</body>
</html>'''

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
