"""SEC-003 (FAZ H): Rate limiter Redis backend testi.

settings.redis_url set ise Limiter storage_uri Redis URL alir; bos ise
default MemoryStorage kalir. _safe_url helper'i sifre alanini gizler
(log injection / dump'larda credential sizmasin).
"""

from app.core import limiter as limiter_module


def test_safe_url_masks_password():
    """redis://user:secret@host -> redis://user:***@host"""
    masked = limiter_module._safe_url("redis://kfinans:s3cret@redis:6379/0")
    assert "s3cret" not in masked
    assert "kfinans:***" in masked
    assert "@redis:6379/0" in masked


def test_safe_url_no_credentials_unchanged():
    """Anonim URL aynen doner."""
    url = "redis://redis:6379/0"
    assert limiter_module._safe_url(url) == url


def test_safe_url_handles_empty():
    assert limiter_module._safe_url("") == ""


def test_build_limiter_uses_memory_when_no_redis_url():
    """settings.redis_url bos ise default MemoryStorage."""
    from app.config import settings

    original = settings.redis_url
    settings.redis_url = ""
    try:
        lim = limiter_module._build_limiter()
        # slowapi Limiter._storage MemoryStorage tipinde olmali
        storage_class = type(lim._storage).__name__
        assert "Memory" in storage_class, f"Beklenen Memory storage, gelen: {storage_class}"
    finally:
        settings.redis_url = original


def test_build_limiter_uses_redis_when_url_set():
    """settings.redis_url set ise Redis storage konfigure edilir.

    NOT: Gercek Redis baglantisi yok — slowapi storage URI lazy connect
    yapar; sadece config'e gectigi dogrulanir.
    """
    from app.config import settings

    original = settings.redis_url
    settings.redis_url = "redis://localhost:6379/0"
    try:
        lim = limiter_module._build_limiter()
        # storage_uri attribute set olmali
        assert (
            lim._storage_uri == "redis://localhost:6379/0" or "redis" in str(lim._storage).lower()
        )
    finally:
        settings.redis_url = original
