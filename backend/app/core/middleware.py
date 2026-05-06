"""Custom ASGI/Starlette middleware'leri."""
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


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
