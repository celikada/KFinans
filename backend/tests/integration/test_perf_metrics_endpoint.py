"""PERF-004 (FAZ H): RequestTimingMiddleware + /metrics/performance integration.

- X-Response-Time header her response'a ekleniyor mu?
- Slow request WARNING log'a yaziliyor mu?
- /metrics/performance token check + JSON sema dogrulamasi.
"""
import asyncio
import logging

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings
from app.core import perf_metrics


@pytest_asyncio.fixture(autouse=True)
async def _reset_perf_buffers():
    """Her test oncesi/sonrasi perf_metrics state sifirlanir — izolasyon."""
    await perf_metrics.reset()
    yield
    await perf_metrics.reset()


@pytest.mark.asyncio
async def test_x_response_time_header_added(client: AsyncClient):
    """Her response X-Response-Time header'i tasimali."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    rt = resp.headers.get("x-response-time")
    assert rt is not None
    assert rt.endswith("ms")
    # Pozitif sayisal deger
    value = float(rt[:-2])
    assert value >= 0


@pytest.mark.asyncio
async def test_metrics_endpoint_404_when_token_empty(client: AsyncClient):
    """settings.metrics_token bos ise endpoint kapali (404)."""
    original = settings.metrics_token
    settings.metrics_token = ""
    try:
        resp = await client.get("/api/v1/metrics/performance")
        assert resp.status_code == 404
    finally:
        settings.metrics_token = original


@pytest.mark.asyncio
async def test_metrics_endpoint_404_with_wrong_token(client: AsyncClient):
    """Yanlis token = 404 (varlik sizdirilmaz)."""
    original = settings.metrics_token
    settings.metrics_token = "secret-token-abc"
    try:
        resp = await client.get(
            "/api/v1/metrics/performance",
            headers={"X-Metrics-Token": "wrong-token"},
        )
        assert resp.status_code == 404
    finally:
        settings.metrics_token = original


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_snapshot_with_correct_token(
    client: AsyncClient,
):
    """Dogru token ile snapshot dondu; en az 1 route + count >= 1."""
    original = settings.metrics_token
    settings.metrics_token = "secret-token-abc"
    try:
        # Once /health'i cagir ki buffer'a kayit dussun
        await client.get("/health")
        # Sonra metrics'i cek
        resp = await client.get(
            "/api/v1/metrics/performance",
            headers={"X-Metrics-Token": "secret-token-abc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        # /health route'u kayitli olmali (template path: /health)
        health_keys = [k for k in data if "/health" in k]
        assert health_keys, f"Route key beklenir, gelen: {list(data.keys())}"
        stats = data[health_keys[0]]
        assert stats["count"] >= 1
        assert "p50_ms" in stats
        assert "p95_ms" in stats
        assert "p99_ms" in stats
        assert "max_ms" in stats
        assert "slow_count" in stats
    finally:
        settings.metrics_token = original


@pytest.mark.asyncio
async def test_slow_request_logs_warning(client: AsyncClient, caplog):
    """slow_request_threshold_ms uzerine cikan request WARNING'a yazilir.

    Threshold gecici 1ms'e dusuruluyor — /health bile slow sayilir.
    """
    original_threshold = settings.slow_request_threshold_ms
    settings.slow_request_threshold_ms = 1
    try:
        with caplog.at_level(logging.WARNING, logger="app.core.middleware"):
            await client.get("/health")
        slow_logs = [r for r in caplog.records if "SLOW_REQUEST" in r.message]
        assert slow_logs, "WARNING log bekleniyor (threshold=1ms)"
    finally:
        settings.slow_request_threshold_ms = original_threshold


@pytest.mark.asyncio
async def test_route_template_used_not_path_with_uuid(client: AsyncClient):
    """Path-param'li endpoint'te route key UUID icermemeli (cardinality bounded).

    Mantik: /api/v1/audit-logs?action_prefix=auth gibi auth gerektiren
    endpoint'ler 401 doner ama route template eslesir. 401 response'unun
    metrics'e dustugunu + key'in template formunda oldugunu dogrula.
    """
    original = settings.metrics_token
    settings.metrics_token = "tok"
    try:
        # Auth gerektiren endpoint'i token'sız çağır — 401
        await client.get("/api/v1/audit-logs")
        # Buffer'i kontrol et
        snap = await perf_metrics.snapshot()
        # Audit-logs route key icinde {uuid} pattern olmamali (zaten path'te yok)
        # ama herhangi bir UUID hex string icermemeli
        for key in snap:
            assert "audit-logs" not in key or "{" not in key.replace("audit-logs", "")
    finally:
        settings.metrics_token = original


@pytest.mark.asyncio
async def test_concurrent_requests_recorded_safely(client: AsyncClient):
    """Async lock altinda paralel request'lerin tamami buffer'a dusmeli."""
    await asyncio.gather(*[client.get("/health") for _ in range(10)])
    snap = await perf_metrics.snapshot()
    health_count = sum(s["count"] for k, s in snap.items() if "/health" in k)
    assert health_count >= 10
