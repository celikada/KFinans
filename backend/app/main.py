import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.api.v1.router import api_router
from app.config import settings
from app.core.limiter import limiter
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KFinans API başlatılıyor")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("KFinans API durduruluyor")


app = FastAPI(title="KFinans API", version="0.1.0", lifespan=lifespan)

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
        request.method, request.url.path, errors,
    )
    return JSONResponse(status_code=422, content={"detail": errors})

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
