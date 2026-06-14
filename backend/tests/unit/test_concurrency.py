"""gather_bounded (bounded-parallel fan-out helper) birim testleri."""

import asyncio

import pytest

from app.services.concurrency import gather_bounded

pytestmark = pytest.mark.asyncio


async def test_preserves_order_and_results():
    async def worker(x):
        await asyncio.sleep(0)
        return x * 2

    out = await gather_bounded([1, 2, 3, 4], worker, limit=2)
    assert out == [2, 4, 6, 8]  # sıra korunur


async def test_empty_items():
    calls = []

    async def worker(x):
        calls.append(x)
        return x

    assert await gather_bounded([], worker, limit=3) == []
    assert calls == []


async def test_concurrency_bounded():
    """Aynı anda en fazla `limit` worker çalışır."""
    active = 0
    peak = 0

    async def worker(_x):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return _x

    await gather_bounded(range(10), worker, limit=3)
    assert peak <= 3


async def test_return_exceptions():
    async def worker(x):
        if x == 2:
            raise ValueError("boom")
        return x

    out = await gather_bounded([1, 2, 3], worker, limit=3, return_exceptions=True)
    assert out[0] == 1
    assert isinstance(out[1], ValueError)
    assert out[2] == 3


async def test_raises_without_return_exceptions():
    async def worker(x):
        if x == 1:
            raise ValueError("boom")
        return x

    with pytest.raises(ValueError, match="boom"):
        await gather_bounded([0, 1], worker, limit=2)
