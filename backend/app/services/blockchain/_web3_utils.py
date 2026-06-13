"""web3.py (AsyncWeb3) için ortak timeout + bounded multi-RPC fallback helper'ları.

Prod sorunu (2026-06-13): `GET /portfolio/wallets` 373 saniye sürdü. Kök neden:
AsyncWeb3.AsyncHTTPProvider'a timeout verilmiyordu ve ölü/yavaş bir RPC tüm
fetch'i kilitleyebiliyordu. Bu modül:

1. `provider_request_kwargs()` — AsyncHTTPProvider'a verilecek `request_kwargs`
   (aiohttp ClientTimeout = settings.blockchain_rpc_timeout).
2. `web3_with_fallback(make_w3, rpcs, probe)` — RPC listesini sırayla dener; her
   denemeyi AYRICA `asyncio.wait_for` ile sarar (provider timeout'u tutmazsa bile
   deadline garanti). İlk başarılı (w3, probe_sonucu) döner; tümü patlarsa
   (None, None). Tekrarlı RPC'leri atlar.

NOT: w3 nesnesi `make_w3` callable'ı ÜZERİNDEN, çağıran servis modülünün kendi
`AsyncWeb3` adıyla kurulur — böylece testlerin modül-seviyesi `AsyncWeb3`
monkeypatch'i çalışmaya devam eder.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")
W3 = TypeVar("W3")


def provider_request_kwargs() -> dict[str, Any]:
    """AsyncHTTPProvider(request_kwargs=...) için timeout sözlüğü.

    Her web3 HTTP isteği blockchain_rpc_timeout saniyede sınırlanır.
    """
    return {"timeout": aiohttp.ClientTimeout(total=settings.blockchain_rpc_timeout)}


async def web3_with_fallback(
    make_w3: Callable[[str], W3],
    rpcs: tuple[str, ...],
    probe: Callable[[W3], Awaitable[T]],
    *,
    label: str = "RPC",
) -> tuple[W3 | None, T | None]:
    """RPC'leri sırayla dener; ilk çalışanı `(w3, probe(w3))` olarak döndürür.

    Her deneme hem provider timeout'u (make_w3 içinde) hem `asyncio.wait_for` ile
    bounded — ölü RPC en fazla `blockchain_rpc_timeout` saniye bekletir. Boş/tekrarlı
    RPC'ler atlanır. Hiçbiri çalışmazsa `(None, None)`.
    """
    seen: set[str] = set()
    for rpc in rpcs:
        if not rpc or rpc in seen:
            continue
        seen.add(rpc)
        try:
            w3 = make_w3(rpc)
            # asyncio.wait_for: provider timeout tutmazsa bile deadline garanti
            # (TimeoutError, Exception'ın alt sınıfı → fallback'e düşer).
            result = await asyncio.wait_for(probe(w3), timeout=settings.blockchain_rpc_timeout)
            return w3, result
        except Exception as exc:
            logger.warning("%s %s başarısız: %s", label, rpc[:40], exc)
    return None, None
