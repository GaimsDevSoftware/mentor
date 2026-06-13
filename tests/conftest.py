"""Shared test configuration — ensure project root is on sys.path and stub heavy deps."""
import sys
import os
import types
import tempfile

# Tests must NEVER touch the user's real data/app.db. core.database reads
# DATABASE_URL at import and runs create_all() on it, so point it at a fresh
# throwaway SQLite file BEFORE anything imports core.database. setdefault() so
# an explicit DATABASE_URL (e.g. CI) still wins.
_test_db = os.path.join(tempfile.gettempdir(), "odysseus_pytest.db")
try:
    if os.path.exists(_test_db):
        os.remove(_test_db)
except OSError:
    pass
os.environ.setdefault("DATABASE_URL", "sqlite:///" + _test_db)
import importlib.util
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _has_module(mod_name: str) -> bool:
    try:
        return importlib.util.find_spec(mod_name) is not None
    except (ImportError, ValueError):
        return False


# Stub optional dependencies only when they are not installed. Do not replace
# real FastAPI/Starlette/Pydantic modules: route tests import their subpackages.
for mod_name in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.types", "sqlalchemy.ext", "sqlalchemy.ext.declarative",
    "sqlalchemy.ext.hybrid", "sqlalchemy.sql", "sqlalchemy.sql.expression",
    "sqlalchemy.sql.sqltypes", "bcrypt", "pyotp",
    "httpx", "fastapi", "fastapi.responses", "fastapi.routing",
    "starlette", "starlette.responses", "starlette.middleware", "starlette.middleware.base",
    "pydantic",
]:
    if mod_name not in sys.modules and not _has_module(mod_name):
        sys.modules[mod_name] = MagicMock()

if "src.database" not in sys.modules:
    _db = types.ModuleType("src.database")
    _db.SessionLocal = MagicMock()
    _db.ModelEndpoint = MagicMock()
    sys.modules["src.database"] = _db
