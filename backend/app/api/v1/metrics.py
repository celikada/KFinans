"""PERF-004 (FAZ H): Performance metrics endpoint (token korumali).

Production'da `METRICS_TOKEN` env set edilir. `X-Metrics-Token` header
eslesirse JSON snapshot doner; eslesmezse veya token bos ise 404 (endpoint
varligi sizdirilmaz — saldirgan tarama yapamaz).

Frontend dashboard cizmek istemeyiz; ops scrape (curl + jq) icin tasarlandi.
Sentry/OTel (OBS-001) eklenince bu endpoint deprecate edilebilir.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.core import perf_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/performance")
async def performance_snapshot(
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
) -> dict[str, dict]:
    """Per-route latency snapshot dondu.

    Response sema: `{ "GET /api/v1/portfolio": {count, p50_ms, p95_ms, p99_ms,
    max_ms, slow_count}, ... }`. Ring buffer en son 1000 olcumu tutar.
    """
    expected = settings.metrics_token
    # Bos token = endpoint kapali. compare_digest constant-time.
    if not expected or not x_metrics_token or not secrets.compare_digest(x_metrics_token, expected):
        raise HTTPException(status_code=404, detail="Not Found")

    return await perf_metrics.snapshot()
