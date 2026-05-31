"""TTL-based async cache with single-flight pattern.

5 blockchain servisinde (bitcoin, avalanche, solana, polkadot, litecoin)
aynı kopya/yapıştır cache + in-flight Future pattern'ı vardı. Bu modül
o DRY borcunu kapatır.

Single-flight: aynı key için aynı anda birden fazla fetch koşmamasını
sağlar. Paralel cache miss çağrıları tek factory'nin sonucunu paylaşır
(rate limit'i koruyup latency'yi düşürür).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class AsyncTTLCache[V]:
    """Async TTL cache + single-flight Future dedup.

    Kullanım:
        _cache: AsyncTTLCache[Decimal] = AsyncTTLCache(ttl_sec=600)

        async def _cached_balance(self) -> Decimal:
            return await _cache.get_or_compute(
                self.address,
                lambda: self._fetch_balance(self.address),
            )

    Notlar:
    - `time.monotonic()` kullanır (system clock değişimine bağışık).
    - Exception durumunda cache YAZILMAZ, in-flight Future yalnızca
      o anki bekleyenlere fırlatılır; sonraki çağrı yeniden dener.
    - Per-instance: her servisin kendi cache'i olmalı (TTL/key namespace
      ayrı). Module-level instance'lar process-wide singleton'dır.
    """

    def __init__(self, ttl_sec: float = 600.0) -> None:
        self._ttl_sec = float(ttl_sec)
        self._cache: dict[str, tuple[float, V]] = {}
        self._inflight: dict[str, asyncio.Future[V]] = {}
        self._lock = asyncio.Lock()

    async def get_or_compute(
        self,
        key: str,
        factory: Callable[[], Awaitable[V]],
    ) -> V:
        loop = asyncio.get_running_loop()
        is_owner = False
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None and time.monotonic() - cached[0] < self._ttl_sec:
                return cached[1]
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = loop.create_future()
                self._inflight[key] = inflight
                is_owner = True

        if not is_owner:
            return await inflight

        try:
            value = await factory()
        except BaseException as exc:
            async with self._lock:
                self._inflight.pop(key, None)
            if not inflight.done():
                inflight.set_exception(exc)
            raise
        else:
            async with self._lock:
                self._cache[key] = (time.monotonic(), value)
                self._inflight.pop(key, None)
            if not inflight.done():
                inflight.set_result(value)
            return value

    def invalidate(self, key: str | None = None) -> None:
        """Cache temizle. Test/admin için.

        - `key` None → tüm cache silinir
        - `key` verilirse sadece o key silinir (in-flight Future
          dokunulmaz, fetch tamamlanırsa yeni cache yazar).
        """
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    @property
    def ttl_sec(self) -> float:
        return self._ttl_sec
