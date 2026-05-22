"""SEC-005 (FAZ H): Rate limit eksik endpoint'lere eklenen koruma testleri.

Mevcut test ortaminda `limiter.enabled = False` (tests/conftest.py); bu test
dosyasi limiter'i AKTIF eder ve gercek 429 davranisini dogrular.
"""

import pytest
from httpx import AsyncClient

from app.core.limiter import limiter
from tests.conftest import make_user


@pytest.fixture
def _enable_limiter():
    """Bu test dosyasinin scope'unda slowapi rate limit'i aktif et."""
    # Conftest globally devre disi (limiter.enabled = False); bu testte aktif et.
    original = limiter.enabled
    limiter.enabled = True
    # Storage'i sifirla — onceki testlerden kalan sayim olmasin
    limiter.reset()
    yield
    limiter.enabled = original


@pytest.mark.asyncio
async def test_email_request_rate_limit_3_per_minute(client: AsyncClient, _enable_limiter):
    """3/dakika asilirsa 429."""
    headers = await make_user(client, "rl_email@example.com")
    # 3 istek basarili, 4. 429
    for i in range(3):
        resp = await client.post(
            "/api/v1/user/email/request",
            json={"new_email": f"target{i}@example.com"},
            headers=headers,
        )
        # 202 ya da 400/409 (sirala farkli email gonderiyoruz, 202 beklenir)
        assert resp.status_code in (202, 400, 409), f"Beklenmeyen istek {i}: {resp.status_code}"

    over = await client.post(
        "/api/v1/user/email/request",
        json={"new_email": "target_over@example.com"},
        headers=headers,
    )
    assert over.status_code == 429


@pytest.mark.asyncio
async def test_data_export_rate_limit_5_per_hour(client: AsyncClient, _enable_limiter):
    """5/saat asilirsa 429. Her cagri buyuk JSON dondurur."""
    headers = await make_user(client, "rl_export@example.com")
    for _ in range(5):
        resp = await client.get("/api/v1/user/data-export", headers=headers)
        assert resp.status_code == 200

    over = await client.get("/api/v1/user/data-export", headers=headers)
    assert over.status_code == 429


@pytest.mark.asyncio
async def test_anthropic_consent_rate_limit_10_per_hour(client: AsyncClient, _enable_limiter):
    """POST/DELETE 10/saat ortak (ayni endpoint farkli method ayri sayim)."""
    headers = await make_user(client, "rl_consent@example.com")
    for _ in range(10):
        resp = await client.post("/api/v1/user/anthropic-consent", headers=headers)
        assert resp.status_code == 200

    over = await client.post("/api/v1/user/anthropic-consent", headers=headers)
    assert over.status_code == 429


@pytest.mark.asyncio
async def test_snapshot_preview_rate_limit_6_per_hour(client: AsyncClient, _enable_limiter):
    """Snapshot preview 6/saat asilirsa 429."""
    headers = await make_user(client, "rl_preview@example.com")
    # 6 cagri (her biri biraz uzun surer cunku tum dis API'leri sorgular,
    # ama integration ortaminda tum entegrasyonlar bos -> hizli doner)
    for i in range(6):
        resp = await client.post("/api/v1/portfolio/snapshot/preview", headers=headers)
        # 200 ya da 503 (dis API hatasi); rate limit dahili sayim
        assert resp.status_code in (200, 503), f"Iter {i}: {resp.status_code}"

    over = await client.post("/api/v1/portfolio/snapshot/preview", headers=headers)
    assert over.status_code == 429
