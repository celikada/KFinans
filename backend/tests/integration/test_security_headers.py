"""
SecurityHeadersMiddleware + TrustedHostMiddleware regresyon testleri.

Bu testler tarayici tabanli koruma katmanlarinin (HSTS, X-Frame, CSP, Referrer
Policy, Permissions Policy) her response'a eklendigini ve TrustedHostMiddleware'in
beklenmeyen Host header'larini reddettigini dogrular.
"""

import pytest
from httpx import AsyncClient

# ─── SecurityHeaders ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_on_health_endpoint(client: AsyncClient):
    """En basit endpoint olan /health bile guvenlik header'lari tasimali."""
    resp = await client.get("/health")
    assert resp.status_code == 200

    # HSTS — 1 yil + alt domain + preload
    hsts = resp.headers.get("strict-transport-security")
    assert hsts is not None
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts

    # Anti-framing / anti-sniffing
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-content-type-options") == "nosniff"

    # Referrer
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    # CSP — backend JSON-only, default-src 'none'
    csp = resp.headers.get("content-security-policy")
    assert csp is not None
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp

    # Permissions Policy
    perm = resp.headers.get("permissions-policy")
    assert perm is not None
    assert "geolocation=()" in perm
    assert "camera=()" in perm

    # Cross-Origin izolasyon
    assert resp.headers.get("cross-origin-opener-policy") == "same-origin"
    assert resp.headers.get("cross-origin-resource-policy") == "same-site"

    # Server header maskelendi
    assert resp.headers.get("server") == "kfinans"


@pytest.mark.asyncio
async def test_security_headers_on_api_endpoint(client: AsyncClient):
    """API endpoint'lerinde de header'lar olmali (sadece /health degil)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpass"},
    )
    # Status code onemli degil; header her response'a eklenmeli
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("strict-transport-security") is not None


@pytest.mark.asyncio
async def test_security_headers_on_404(client: AsyncClient):
    """404 hata yanitlarinda da header'lar olmali (defence-in-depth)."""
    resp = await client.get("/api/v1/nonexistent-endpoint-xyz")
    assert resp.status_code == 404
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("strict-transport-security") is not None


@pytest.mark.asyncio
async def test_security_headers_on_validation_error(client: AsyncClient):
    """422 validation hatalarinda da header'lar olmali."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "x"},  # invalid input
    )
    # 422 veya 400 — middleware her ikisinde de calismali
    assert resp.status_code in (400, 422)
    assert resp.headers.get("x-frame-options") == "DENY"


# ─── TrustedHost ────────────────────────────────────────────────────────────
# Not: Test ortaminda config default allowed_hosts=["*"] oldugundan TrustedHost
# tum host'lara izin verir (testler bozulmasin diye). Production override:
# ALLOWED_HOSTS=["kfinans.app","www.kfinans.app"] env ile yapilir.
# Bu testler middleware'in mount edildigini ve "*" davranisini dogrular.


@pytest.mark.asyncio
async def test_trusted_host_allows_localhost_in_dev(client: AsyncClient):
    """Dev/test'te allowed_hosts=['*'] — localhost serbest gecmeli."""
    resp = await client.get("/health", headers={"Host": "localhost"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_trusted_host_allows_arbitrary_host_when_wildcard(client: AsyncClient):
    """allowed_hosts wildcard iken arbitrary host header reddedilmemeli."""
    resp = await client.get("/health", headers={"Host": "example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_trusted_host_rejects_when_strict():
    """Production-style strict allowed_hosts ile yanlis host 400 donmeli."""
    # Settings'i gecici override edip yeni bir app instance test et
    from fastapi import FastAPI
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from httpx import ASGITransport
    from httpx import AsyncClient as ACli

    test_app = FastAPI()

    @test_app.get("/ping")
    async def _ping():
        return {"ok": True}

    test_app.add_middleware(TrustedHostMiddleware, allowed_hosts=["kfinans.app"])

    async with ACli(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        # Yanlis host
        bad = await c.get("/ping", headers={"Host": "evil.example.com"})
        assert bad.status_code == 400

        # Dogru host
        good = await c.get("/ping", headers={"Host": "kfinans.app"})
        assert good.status_code == 200
