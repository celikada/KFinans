"""PERF-004 (FAZ H): perf_metrics modulu unit testleri.

Ring buffer + percentile hesaplama dogrulanir; middleware integration
testleri tests/integration/test_perf_metrics_endpoint.py'da.
"""
import pytest

from app.core import perf_metrics


@pytest.fixture(autouse=True)
async def _reset_buffers():
    await perf_metrics.reset()
    yield
    await perf_metrics.reset()


@pytest.mark.asyncio
async def test_record_and_snapshot_basic():
    """Tek route'a 5 olcum eklenirse count=5, percentile'lar dogru hesaplanir."""
    for ms in [10.0, 20.0, 30.0, 40.0, 50.0]:
        await perf_metrics.record("GET /test", ms)

    snap = await perf_metrics.snapshot()
    assert "GET /test" in snap
    stats = snap["GET /test"]
    assert stats["count"] == 5
    # Linear interpolated percentile: p50 of [10,20,30,40,50] = 30.0
    assert stats["p50_ms"] == 30.0
    # p95 = 10 + 0.95*4 = index 3.8 -> 40 + 0.8*10 = 48.0
    assert stats["p95_ms"] == 48.0
    assert stats["max_ms"] == 50.0
    assert stats["slow_count"] == 0


@pytest.mark.asyncio
async def test_slow_count_increments():
    """slow=True flag her cagrida slow_count'u arttirir."""
    await perf_metrics.record("GET /slow", 100.0, slow=False)
    await perf_metrics.record("GET /slow", 600.0, slow=True)
    await perf_metrics.record("GET /slow", 700.0, slow=True)

    snap = await perf_metrics.snapshot()
    assert snap["GET /slow"]["count"] == 3
    assert snap["GET /slow"]["slow_count"] == 2


@pytest.mark.asyncio
async def test_ring_buffer_enforces_maxlen():
    """1000'den fazla olcum eklenirse en eski deque'ten dusurulur (FIFO)."""
    for i in range(1500):
        await perf_metrics.record("GET /flood", float(i))

    snap = await perf_metrics.snapshot()
    assert snap["GET /flood"]["count"] == 1000
    # En eski 500 dustu; max 1499 olmali
    assert snap["GET /flood"]["max_ms"] == 1499.0


@pytest.mark.asyncio
async def test_multiple_routes_isolated():
    """Farkli route key'leri ayri buffer'da tutulur."""
    await perf_metrics.record("GET /a", 10.0)
    await perf_metrics.record("POST /b", 20.0)
    await perf_metrics.record("GET /a", 30.0)

    snap = await perf_metrics.snapshot()
    assert snap["GET /a"]["count"] == 2
    assert snap["POST /b"]["count"] == 1


@pytest.mark.asyncio
async def test_reset_clears_buffers_and_slow_counts():
    """reset() snapshot'i bos dondu."""
    await perf_metrics.record("GET /a", 10.0, slow=True)
    await perf_metrics.reset()
    snap = await perf_metrics.snapshot()
    assert snap == {}


@pytest.mark.asyncio
async def test_empty_buffer_returns_zero_percentile():
    """Hicbir kayit yoksa snapshot bos sozluk."""
    snap = await perf_metrics.snapshot()
    assert snap == {}


def test_percentile_single_value():
    """Tek deger varsa p50/p95/p99 hep o degeri doner (degisken interpolasyon yok)."""
    assert perf_metrics._percentile([42.0], 50) == 42.0
    assert perf_metrics._percentile([42.0], 95) == 42.0
    assert perf_metrics._percentile([42.0], 99) == 42.0


def test_percentile_empty_list_zero():
    assert perf_metrics._percentile([], 50) == 0.0
