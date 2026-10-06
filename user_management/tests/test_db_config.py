import importlib
import os


def test_default_database_uses_sqlite_when_postgres_not_configured(monkeypatch):
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('USE_SQLITE', 'true')
    module_name = 'models.user'
    import sys
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    assert str(module.DATABASE_URL).startswith('sqlite:///')
