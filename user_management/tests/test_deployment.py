import ast
import os
from pathlib import Path
import pytest


def resolver():
    # Isolate environment selection without creating engines or reading local .env.
    source = Path("models/user.py").read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_resolve_database_url")
    namespace = {"os": os, "__file__": str(Path("models/user.py").resolve())}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "database_config", "exec"), namespace)
    return namespace["_resolve_database_url"]


def test_postgres_precedence(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgres://example.invalid/primary")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/secondary")
    monkeypatch.setenv("USE_SQLITE", "true")
    assert resolver()() == "postgresql://example.invalid/primary"


def test_database_url_fallback(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/secondary")
    assert resolver()() == "postgresql://example.invalid/secondary"


def test_requires_explicit_configuration(monkeypatch):
    for variable in ("POSTGRES_URL", "DATABASE_URL", "USE_SQLITE"):
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(RuntimeError, match="Configure POSTGRES_URL"):
        resolver()()
