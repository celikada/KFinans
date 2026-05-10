"""PERF-004 (FAZ H): In-memory per-route latency tracker.

Dependency-free percentile sayaci. Ring buffer (deque maxlen=1000) basina
olcum tutar; `/metrics/performance` endpoint'i snapshot doner.

Sentry/OTel (OBS-001) ileride eklenecek — bu modul gecici bir gozlemlenebilirlik
araci, production icin yeterli (1 replica K8s deploy'a uygun).
"""
from __future__ import annotations

import asyncio
import math
from collections import deque
from typing import TypedDict


class RouteStats(TypedDict):
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    slow_count: int


_BUFFER_MAXLEN = 1000
# Route key -> deque[duration_ms]
_BUFFERS: dict[str, deque[float]] = {}
# Route key -> slow request counter (cumulative since process start)
_SLOW_COUNTS: dict[str, int] = {}
_LOCK = asyncio.Lock()


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear interpolated percentile. `sorted_values` zaten sirali.

    NumPy bagimliligi yok; basit indeksleme yeterli (n<=1000).
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


async def record(route_key: str, duration_ms: float, *, slow: bool = False) -> None:
    """Olcumu route buffer'ina ekle. Buffer dolu ise eski deque oto-pop eder."""
    async with _LOCK:
        buf = _BUFFERS.setdefault(route_key, deque(maxlen=_BUFFER_MAXLEN))
        buf.append(duration_ms)
        if slow:
            _SLOW_COUNTS[route_key] = _SLOW_COUNTS.get(route_key, 0) + 1


async def snapshot() -> dict[str, RouteStats]:
    """Tum route'lar icin {count, p50, p95, p99, max, slow_count} dondur."""
    async with _LOCK:
        result: dict[str, RouteStats] = {}
        for route_key, buf in _BUFFERS.items():
            if not buf:
                continue
            sorted_vals = sorted(buf)
            result[route_key] = {
                "count": len(sorted_vals),
                "p50_ms": round(_percentile(sorted_vals, 50), 2),
                "p95_ms": round(_percentile(sorted_vals, 95), 2),
                "p99_ms": round(_percentile(sorted_vals, 99), 2),
                "max_ms": round(sorted_vals[-1], 2),
                "slow_count": _SLOW_COUNTS.get(route_key, 0),
            }
        return result


async def reset() -> None:
    """Test izolasyonu icin tum buffer'lari temizle."""
    async with _LOCK:
        _BUFFERS.clear()
        _SLOW_COUNTS.clear()
