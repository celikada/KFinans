"""OBS-001 (FAZ H): Sentry exception tracking + OpenTelemetry distributed tracing.

Iki saglayici, ayri opt-in:
- Sentry — exception capture, breadcrumb, performance monitoring, alerting.
- OTel  — distributed trace (FastAPI handler + SQLAlchemy/asyncpg query +
  httpx outbound HTTP) -> OTLP HTTP exporter (Tempo/Jaeger/Honeycomb).

Hicbir paket import edilse de import-time side effect yok; init fonksiyonlari
cagrilmadigi surece SDK aktif degil. `settings.sentry_dsn` / `otel_endpoint`
bos ise init no-op olur — dev'de bagimliliklar yuklu olsa bile aktive edilmez.

Production icin:
    SENTRY_DSN=https://...@sentry.io/...
    SENTRY_ENV=production
    OTEL_ENDPOINT=http://tempo:4318/v1/traces
    OTEL_SERVICE_NAME=kfinans-backend

PERF-004 dependency-free in-memory tracker hala calisir; OTel ileride o'nun
yerini alabilir (deprecate notu /metrics/performance comment'inde).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import settings

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """settings.sentry_dsn varsa Sentry SDK'i baslat.

    Doner: True = aktive edildi, False = no-op (DSN bos veya import basarisiz).
    """
    if not settings.sentry_dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("sentry-sdk yuklu degil; SENTRY_DSN set ama init no-op")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        # send_default_pii=False default — KVKK guvenli (kullanici email/IP gondermez)
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        # Release tagging: GIT_SHA env'i deploy sirasinda set edilir.
        release=_release_tag(),
    )
    logger.info(
        "Sentry initialized — env=%s sample_rate=%.2f",
        settings.sentry_env,
        settings.sentry_traces_sample_rate,
    )
    return True


def init_otel(app: FastAPI) -> bool:
    """settings.otel_endpoint varsa OpenTelemetry'i baslat.

    FastAPI + SQLAlchemy + asyncpg + httpx instrumentation; OTLPSpanExporter
    settings.otel_endpoint'e POST eder.

    Doner: True = aktive edildi, False = no-op.
    """
    if not settings.otel_endpoint:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "opentelemetry paketleri yuklu degil; OTEL_ENDPOINT set ama init no-op",
        )
        return False

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.sentry_env,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OpenTelemetry initialized — endpoint=%s service=%s",
        settings.otel_endpoint,
        settings.otel_service_name,
    )
    return True


def _release_tag() -> str | None:
    """K8s deploy SHA tagini env'den oku (release.yml CMD'a injekte eder)."""
    import os

    return os.environ.get("GIT_SHA") or None
