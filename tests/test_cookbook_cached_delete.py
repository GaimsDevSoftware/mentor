"""POST /api/model/cached/delete — remove a downloaded model from local storage.

Covers the on-disk deletion the cookbook's "Downloaded & ready" list calls when
the user clicks Delete: HuggingFace-cache folders (models--<org>--<name>),
custom model-dir folders (<dir>/<leaf>), and Ollama models (`ollama rm`). Also
proves the input validation that keeps the repo_id / path out of harm's way.

Calls the route handler directly (extracted from the router) with a minimal fake
request, matching the project's other route tests — no TestClient threadpool.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.cookbook_routes as cr


def _req():
    return SimpleNamespace(state=SimpleNamespace(current_user="admin"))


def _endpoint(suffix, method="POST"):
    router = cr.setup_cookbook_routes()
    for r in router.routes:
        if getattr(r, "path", "").endswith(suffix) and method in getattr(r, "methods", set()):
            return r.endpoint
    raise RuntimeError(f"{method} *{suffix} not found")


@pytest.fixture(autouse=True)
def _bypass_admin(monkeypatch):
    # The endpoint is admin-gated; the deletion logic is what we're testing here.
    monkeypatch.setattr(cr, "require_admin", lambda request: None)


async def test_deletes_hf_cache_folder():
    delete = _endpoint("/api/model/cached/delete")
    tmp = Path(tempfile.mkdtemp())
    hub = tmp / "hub"
    mdir = hub / "models--Qwen--Qwen2-VL-7B-Instruct"
    mdir.mkdir(parents=True)
    (mdir / "blob.bin").write_text("x" * 64)

    res = await delete(_req(), cr.ModelCacheDeleteRequest(
        repo_id="Qwen/Qwen2-VL-7B-Instruct", path=str(hub)))

    assert res["ok"] is True
    assert not mdir.exists()


async def test_deletes_custom_local_dir_model():
    delete = _endpoint("/api/model/cached/delete")
    tmp = Path(tempfile.mkdtemp())
    leaf = tmp / "DeepSeek-R1-UD-IQ4_XS"
    leaf.mkdir(parents=True)
    (leaf / "config.json").write_text("{}")

    res = await delete(_req(), cr.ModelCacheDeleteRequest(
        repo_id="DeepSeek-R1-UD-IQ4_XS", is_local_dir=True, path=str(tmp)))

    assert res["ok"] is True
    assert not leaf.exists()


async def test_missing_model_reports_not_found():
    delete = _endpoint("/api/model/cached/delete")
    tmp = Path(tempfile.mkdtemp())
    res = await delete(_req(), cr.ModelCacheDeleteRequest(
        repo_id="Foo/Bar", path=str(tmp)))
    assert res["ok"] is False
    assert "not found" in res["error"].lower()


async def test_rejects_injection_in_repo_id():
    delete = _endpoint("/api/model/cached/delete")
    tmp = Path(tempfile.mkdtemp())
    sentinel = tmp / "keep.txt"
    sentinel.write_text("safe")
    with pytest.raises(HTTPException) as ei:
        await delete(_req(), cr.ModelCacheDeleteRequest(
            repo_id="x; rm -rf ~ #", path=str(tmp)))
    assert ei.value.status_code == 400
    assert sentinel.exists()  # nothing was touched


async def test_local_dir_without_path_is_rejected():
    delete = _endpoint("/api/model/cached/delete")
    with pytest.raises(HTTPException) as ei:
        await delete(_req(), cr.ModelCacheDeleteRequest(
            repo_id="SomeModel", is_local_dir=True))
    assert ei.value.status_code == 400


async def test_ollama_without_binary_errors_gracefully(monkeypatch):
    delete = _endpoint("/api/model/cached/delete")
    monkeypatch.setattr(cr, "which_tool", lambda name: None)
    res = await delete(_req(), cr.ModelCacheDeleteRequest(
        repo_id="llama3.2:1b", is_ollama=True))
    assert res["ok"] is False
    assert "ollama" in res["error"].lower()
