"""DB TLS connect_args uretimi (database.py) unit testleri.

Audit 2026-05-21 #3: settings.database_ssl_mode degerine gore asyncpg
connect_args farklilik gosterir. Bu testler modul-level dal mantigini
importlib.reload ile her mod icin yeniden calistirip dogrular.

Kaynak koda dokunulmaz; sadece settings monkeypatch + reload.
"""

import importlib
import ssl

import pytest

import app.database as database_module


def _reload_database():
    """app.database modulunu yeniden import edip connect_args'i yeniden kurar."""
    return importlib.reload(database_module)


@pytest.fixture(autouse=True)
def _restore_database_module():
    """Her testten sonra database modulunu orijinal settings ile geri yukle —
    diger testlerin (engine vs.) bozulmamasi icin."""
    yield
    importlib.reload(database_module)


def test_ssl_mode_disable_sets_ssl_false(monkeypatch):
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "disable")
    mod = _reload_database()
    assert mod._connect_args == {"ssl": False}


def test_ssl_mode_prefer_builds_unverified_context(monkeypatch):
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "prefer")
    mod = _reload_database()
    ctx = mod._connect_args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    # Self-signed cluster cert: hostname + chain verify kapali
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


def test_ssl_mode_require_without_ca_falls_back_to_true(monkeypatch):
    """CA bundle dosyasi yoksa connect_args {'ssl': True} (asyncpg default ctx)."""
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "require")
    # Olmayan bir path ver -> os.path.isfile False
    monkeypatch.setattr(database_module.settings, "database_ssl_ca_path", "/nonexistent/ca.crt")
    mod = _reload_database()
    assert mod._connect_args == {"ssl": True}


def test_ssl_mode_require_empty_ca_path_falls_back_to_true(monkeypatch):
    """CA path bos string -> yine {'ssl': True} (if _ca_path falsy)."""
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "require")
    monkeypatch.setattr(database_module.settings, "database_ssl_ca_path", "")
    mod = _reload_database()
    assert mod._connect_args == {"ssl": True}


def test_ssl_mode_require_with_ca_file_builds_verified_context(monkeypatch, tmp_path):
    """Gercek bir CA bundle dosyasi varsa CERT_REQUIRED + check_hostname=True ctx."""
    # create_default_context(cafile=...) gecerli PEM ister; sistemin kendi
    # CA bundle'ini kopyalayarak gecerli bir dosya saglariz.
    import certifi

    ca_file = tmp_path / "ca.crt"
    ca_file.write_bytes(open(certifi.where(), "rb").read())

    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "require")
    monkeypatch.setattr(database_module.settings, "database_ssl_ca_path", str(ca_file))
    mod = _reload_database()
    ctx = mod._connect_args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_ssl_mode_unknown_value_returns_empty_connect_args(monkeypatch):
    """Bilinmeyen mod (else dali) -> bos connect_args."""
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "whatever")
    mod = _reload_database()
    assert mod._connect_args == {}


def test_engine_and_sessionmaker_rebuilt(monkeypatch):
    """reload sonrasi engine + AsyncSessionLocal yeniden olusturulur (smoke)."""
    monkeypatch.setattr(database_module.settings, "database_ssl_mode", "disable")
    mod = _reload_database()
    assert mod.engine is not None
    assert mod.AsyncSessionLocal is not None
