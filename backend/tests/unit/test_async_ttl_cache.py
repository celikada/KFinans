"""Unit tests for AsyncTTLCache (app/core/cache.py).

5 blockchain servisinde paylaşılan TTL + single-flight pattern'inin
ortak helper'ı. Cache hit, miss, TTL expiration, single-flight dedup,
exception isolation ve invalidation davranışları doğrulanır.
"""

import asyncio

import pytest

from app.core.cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value():
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    call_count = 0

    async def factory() -> int:
        nonlocal call_count
        call_count += 1
        return 42

    v1 = await cache.get_or_compute("k", factory)
    v2 = await cache.get_or_compute("k", factory)
    assert v1 == 42 == v2
    assert call_count == 1  # ikinci çağrı cache'ten döndü


@pytest.mark.asyncio
async def test_cache_miss_for_different_keys():
    cache: AsyncTTLCache[str] = AsyncTTLCache(ttl_sec=60)

    async def factory_a() -> str:
        return "A"

    async def factory_b() -> str:
        return "B"

    assert await cache.get_or_compute("a", factory_a) == "A"
    assert await cache.get_or_compute("b", factory_b) == "B"


@pytest.mark.asyncio
async def test_single_flight_dedups_parallel_calls():
    """Aynı anda gelen 5 paralel çağrı tek factory çağrısının sonucunu paylaşır."""
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    call_count = 0
    factory_started = asyncio.Event()
    release = asyncio.Event()

    async def slow_factory() -> int:
        nonlocal call_count
        call_count += 1
        factory_started.set()
        await release.wait()
        return 99

    # Owner + 4 waiter paralel başlat
    tasks = [asyncio.create_task(cache.get_or_compute("k", slow_factory)) for _ in range(5)]
    await factory_started.wait()
    release.set()
    results = await asyncio.gather(*tasks)

    assert results == [99, 99, 99, 99, 99]
    assert call_count == 1  # tek factory çalıştı


@pytest.mark.asyncio
async def test_exception_in_factory_does_not_cache():
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    call_count = 0

    async def failing_factory() -> int:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await cache.get_or_compute("k", failing_factory)
    with pytest.raises(RuntimeError, match="boom"):
        await cache.get_or_compute("k", failing_factory)

    assert call_count == 2  # exception cache'lenmedi, yeniden denendi


@pytest.mark.asyncio
async def test_exception_propagates_to_waiters():
    """Owner fail ederse bekleyenlerin de aynı exception'ı alır."""
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    factory_started = asyncio.Event()
    release = asyncio.Event()

    async def failing_factory() -> int:
        factory_started.set()
        await release.wait()
        raise ValueError("shared failure")

    tasks = [asyncio.create_task(cache.get_or_compute("k", failing_factory)) for _ in range(3)]
    await factory_started.wait()
    release.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert all(isinstance(r, ValueError) for r in results)
    assert all(str(r) == "shared failure" for r in results)


@pytest.mark.asyncio
async def test_owner_cancellation_does_not_poison_inflight():
    """Owner CANCEL edilirse inflight temizlenir → sonraki çağrı ölü future'ı
    BEKLEMEDEN yeniden dener.

    Regresyon: cleanup `async with self._lock` ile yapılınca, cancellation
    sırasında lock-await re-raise olup pop atlanıyordu → inflight future
    zehirleniyor, sonraki tüm çağrılar sonsuz bekliyordu (prod: BTC scan kalıcı
    45s timeout + 0 mempool isteği, pod restart'a kadar)."""
    cache: AsyncTTLCache[str] = AsyncTTLCache(ttl_sec=600)
    started = asyncio.Event()

    async def slow_factory() -> str:
        started.set()
        await asyncio.sleep(10)  # cancel edilecek
        return "slow"

    task = asyncio.create_task(cache.get_or_compute("k", slow_factory))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # inflight temizlenmiş olmalı → yeni çağrı yeni factory'yi çalıştırır (hang YOK)
    async def fast_factory() -> str:
        return "ok"

    result = await asyncio.wait_for(cache.get_or_compute("k", fast_factory), timeout=1.0)
    assert result == "ok"


@pytest.mark.asyncio
async def test_ttl_expiration_triggers_refetch():
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=0.05)
    call_count = 0

    async def factory() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    assert await cache.get_or_compute("k", factory) == 1
    await asyncio.sleep(0.1)  # TTL süresi geçer
    assert await cache.get_or_compute("k", factory) == 2  # yeniden çağrıldı


@pytest.mark.asyncio
async def test_invalidate_specific_key():
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    call_count = 0

    async def factory() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    assert await cache.get_or_compute("k1", factory) == 1
    assert await cache.get_or_compute("k2", factory) == 2
    cache.invalidate("k1")
    assert await cache.get_or_compute("k1", factory) == 3  # yeniden hesapla
    assert await cache.get_or_compute("k2", factory) == 2  # hâlâ cache'ten


@pytest.mark.asyncio
async def test_invalidate_all():
    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl_sec=60)
    call_count = 0

    async def factory() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    await cache.get_or_compute("a", factory)
    await cache.get_or_compute("b", factory)
    cache.invalidate()  # key None → tümü
    assert await cache.get_or_compute("a", factory) == 3  # yeniden
    assert await cache.get_or_compute("b", factory) == 4
