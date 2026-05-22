import logging
import uuid
from contextlib import asynccontextmanager
from decimal import ROUND_HALF_UP, getcontext

from fastapi import FastAPI, Request

# Audit 2026-05-22 P0 #8 (finance): Decimal rounding mode global olarak
# ROUND_HALF_UP'e set edilir. Python default ROUND_HALF_EVEN (banker's rounding)
# muhasebede/vergi raporlamada beklenmeyen sonuclar verir (0.005 -> 0.00 yerine
# 0.01). Bu set tum Decimal islemlerini etkiler — TL/USD conversion, kar/zarar,
# bütçe hesabı, snapshot. Import-time yapilir; uvicorn baslamasindan once aktif.
getcontext().rounding = ROUND_HALF_UP
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1.router import api_router
from app.config import settings
from app.core.limiter import limiter
from app.core.middleware import RequestTimingMiddleware, SecurityHeadersMiddleware
from app.observability import init_otel, init_sentry
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# SEC: PII masking filter (defence-in-depth). Manuel `mask_email` çağrıları
# korunur; bu filter 3. parti kütüphane (SQLAlchemy/httpx/FastAPI) log'larında
# sızabilecek PII'leri otomatik mask'ler. Sentry `send_default_pii=False`'a ek.
from app.core.log_filter import install_pii_filter  # noqa: E402

install_pii_filter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KFinans API başlatılıyor")
    # OBS-001: Sentry/OTel opt-in init (DSN/endpoint bos = no-op).
    # Sentry once — exception capture FastAPI handler'larini sarmalamadan once aktif.
    init_sentry()
    init_otel(app)
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("KFinans API durduruluyor")


# Audit 2026-05-22 P0 #7 (security): Swagger UI + /openapi.json prod'da
# DEFAULT KAPALI. Saldirgan enumeration vektorudur — endpoint listesi,
# request/response schema, auth pattern hepsi public OpenAPI'da gozukur.
# Dev'de settings.expose_swagger=True ile aktive edilir (env veya .env).
# Prod'da gerekirse reverse-proxy basic auth + IP whitelist arkasinda
# expose edilebilir.
_docs_enabled = settings.expose_swagger
app = FastAPI(
    title="KFinans API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def log_validation_errors(request: Request, exc: RequestValidationError):
    """Hata ayıklama: 422 detayını log'a yaz, frontend'e mevcut FastAPI formatında dön.

    Pydantic 2'de `exc.errors()` ctx içinde ham ValueError instance'ı döndürür;
    JSONResponse default JSON encoder'i bunu serialize edemiyor (TypeError).
    `jsonable_encoder` ValueError'ı str()'e çevirir, JSON-safe yapar.
    """
    errors = jsonable_encoder(exc.errors())
    logger.warning(
        "422 VALIDATION %s %s — errors=%s",
        request.method,
        request.url.path,
        errors,
    )
    return JSONResponse(status_code=422, content={"detail": errors})


# BACK-008 + ARC-006 (FAZ H): IntegrityError -> 409, SQLAlchemyError generic -> 500,
# Exception genel -> 500 sanitized. Error response formati: {detail, code, request_id}.
# request_id korelasyonu icin uuid4 hex (server log + frontend hata raporu eslesmesi).


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """DB UNIQUE/FK ihlali — 409 Conflict. ORM message frontend'e sizmasin
    (saldirgana sema bilgisi vermez)."""
    rid = uuid.uuid4().hex
    logger.warning(
        "409 INTEGRITY %s %s rid=%s — %s",
        request.method,
        request.url.path,
        rid,
        exc.orig if exc.orig else exc,
    )
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Bu kayit zaten mevcut veya iliskisel kisitla celisiyor",
            "code": "integrity_error",
            "request_id": rid,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Diger ORM hatalari (OperationalError, TimeoutError vb.) — 500.
    DB hata mesaji frontend'e sizmasin; ops icin log'da full trace."""
    rid = uuid.uuid4().hex
    logger.exception(
        "500 DB_ERROR %s %s rid=%s",
        request.method,
        request.url.path,
        rid,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Veritabani islemi gerceklestirilemedi",
            "code": "db_error",
            "request_id": rid,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Son catch-all — beklenmedik hatalarda information disclosure'i engelle.
    HTTPException ve RequestValidationError FastAPI tarafindan kendi handler'lari
    cagirildigi icin buraya dusmez."""
    rid = uuid.uuid4().hex
    logger.exception(
        "500 UNHANDLED %s %s rid=%s",
        request.method,
        request.url.path,
        rid,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Beklenmedik bir hata olustu",
            "code": "internal_error",
            "request_id": rid,
        },
    )


# Middleware sırası önemli: add_middleware LIFO çalışır
# (en SON add edilen request'te İLK çalışır).
#
# add sırası                 →  request flow              →  response flow
# 1. RequestTiming (innermost)  →  5. çalışır (app'e en yakın) →  1. çalışır (timing app + SecurityHeaders dahil değil)
# 2. SecurityHeaders         →  4. çalışır                →  2. çalışır (her response'a header)
# 3. TrustedHost             →  3. çalışır (Host check)   →  3. çalışır
# 4. CORS (en son add)       →  1. çalışır (preflight)    →  4. çalışır
#
# RequestTiming en içte: app handler süresini (+ SecurityHeaders dispatch'i) ölçer;
# X-Response-Time header'i set edilir, sonraki middleware'ler header'a dokunmaz.
# CORS en son add ediliyor çünkü preflight OPTIONS isteklerini diğer
# middleware'lerden önce yakalaması ve CORS error response'larına da
# güvenlik header'larının uygulanması gerekiyor.
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# TrustedHost (FAZ C3): Host header injection koruması.
# Dev'de allowed_hosts=["*"] (config default) — testler ve localhost serbest.
# Prod'da env: ALLOWED_HOSTS=["kfinans.app","www.kfinans.app","api.kfinans.app"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
