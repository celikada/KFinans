"""Bounded-parallel fan-out helper (tek yerde — her serviste tekrar yazılmaz).

Portföy verisi çoğu yerde zaten `asyncio.gather` ile paralel çekilir (cüzdan
zincirleri, hisse ticker'ları, Sonic validator'ları). Ancak SIRALI kalan
döngüler (BTC xpub adres taraması, çoklu borsa, ERC-20 token'lar) vardı.

KRİTİK nüans: public API'ler (mempool.space, Yahoo, RPC) rate-limit uygular.
SINIRSIZ paralel istek 429 fırtınası yaratır → daha YAVAŞ veya hata. Bu yüzden
fan-out **bounded** olmalı: her servis kendi rate-limit'ine uygun bir `limit`
(semaphore) verir. "Hepsini aynı anda" değil, "kontrollü paralel".
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence


async def gather_bounded[T, R](
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R]:
    """`worker`'ı `items` üzerinde EN FAZLA `limit` eşzamanlı çalıştırır.

    Sıra korunur (asyncio.gather gibi). `limit` her servisin rate-limit'ine
    göre seçilir (ör. mempool.space ~5, RPC ~3). `return_exceptions=True` ise
    bir öğenin hatası diğerlerini düşürmez (sonuç listesinde exception döner).
    """
    items_seq: Sequence[T] = list(items)
    if not items_seq:
        return []
    sem = asyncio.Semaphore(max(1, limit))

    async def _run(item: T) -> R:
        async with sem:
            return await worker(item)

    return await asyncio.gather(*(_run(i) for i in items_seq), return_exceptions=return_exceptions)
