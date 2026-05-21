"""Custom ASGI/Starlette middleware'leri."""

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core import perf_metrics

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Tüm HTTP yanıtlarına standart güvenlik header'larını ekler.

    Header'lar:
      - Strict-Transport-Security: HTTPS zorunluluğu (defence-in-depth;
        .app TLD HSTS preload listesinde olsa da explicit ekliyoruz)
      - X-Frame-Options: DENY → clickjacking koruması
      - X-Content-Type-Options: nosniff → MIME sniffing engeli
      - Referrer-Policy: strict-origin-when-cross-origin
      - Content-Security-Policy: API JSON-only olduğu için katı varsayılan
      - Permissions-Policy: hassas browser özelliklerini kapat
      - Cross-Origin-* headers: izolasyon

    Production'da settings.enable_security_headers=True (default).
    Dev'de False yapılırsa middleware no-op olur.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        if not settings.enable_security_headers:
            return response

        # ─── Transport security ──────────────────────────────────────────
        # max-age 1 yıl + alt domain'ler dahil + preload list'e adaylık
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains; preload"
        )

        # ─── Anti-framing / anti-sniffing ────────────────────────────────
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"

        # ─── Referrer kontrolü ───────────────────────────────────────────
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ─── Content Security Policy ─────────────────────────────────────
        # Backend API JSON döner, HTML render etmez. Bu yüzden default-src 'none'
        # makul. Eğer Swagger UI açıksa /docs için override gerekebilir.
        if settings.csp_policy:
            response.headers["Content-Security-Policy"] = settings.csp_policy

        # ─── Permissions Policy (eski Feature-Policy) ────────────────────
        # Hassas browser özellikleri default'ta kapalı; ihtiyaca göre aç.
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        # ─── Cross-Origin izolasyon (Spectre koruması) ───────────────────
        # COEP credentialless yerine require-corp daha katı; API için yeterli.
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"

        # ─── Server header'ı maskele ─────────────────────────────────────
        # Uvicorn versiyonu sızdırma yok
        response.headers["Server"] = "kfinans"

        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """PERF-004 (FAZ H): Endpoint bazinda response time olcumu.

    - `X-Response-Time` header (ms, 1 ondalik) her response'a eklenir.
    - `>= settings.slow_request_threshold_ms` requestler WARNING log'a yazilir.
    - Per-route ring buffer'a duration kaydedilir; `/metrics/performance` ile
      p50/p95/p99 cikariminda kullanilir.

    Route key: matched route template (`/api/v1/portfolio/snapshot/{snapshot_date}`)
    — UUID/path-param leak yok, dict cardinality bounded. Eslemeyen path icin
    `<unmatched>` kullanilir (404'ler tek bucket'a toplanir).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Ölçümü hata anında da yapalım — exception handler 500 dondurur,
            # ama buradan sonra metrics'e dusmez. Yine de raise et.
            duration_ms = (time.perf_counter() - start) * 1000
            route_key = _route_key(request)
            slow = duration_ms >= settings.slow_request_threshold_ms
            await perf_metrics.record(route_key, duration_ms, slow=slow)
            if slow:
                logger.warning(
                    "SLOW_REQUEST(error) %s %s duration_ms=%.1f",
                    request.method,
                    route_key,
                    duration_ms,
                )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        route_key = _route_key(request)
        slow = duration_ms >= settings.slow_request_threshold_ms
        await perf_metrics.record(route_key, duration_ms, slow=slow)
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
        if slow:
            logger.warning(
                "SLOW_REQUEST %s %s duration_ms=%.1f status=%s",
                request.method,
                route_key,
                duration_ms,
                response.status_code,
            )
        return response


def _route_key(request: Request) -> str:
    """Matched route template + method dondurur. Match yoksa <unmatched>."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return f"{request.method} {template}"
    return f"{request.method} <unmatched>"
