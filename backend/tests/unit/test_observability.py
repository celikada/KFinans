"""OBS-001 (FAZ H): observability modulu unit testleri.

Sentry + OTel init opt-in olmali — DSN/endpoint bos ise hata atmadan
no-op donmeli. Aktif iken sentry_sdk.init / TracerProvider mock ile dogrula.
"""
from unittest.mock import MagicMock, patch

import pytest

from app import observability
from app.config import settings


@pytest.fixture(autouse=True)
def _reset_settings():
    """Her test sonrasi DSN/endpoint orjinaline dondur (test izolasyon)."""
    original_dsn = settings.sentry_dsn
    original_endpoint = settings.otel_endpoint
    yield
    settings.sentry_dsn = original_dsn
    settings.otel_endpoint = original_endpoint


def test_init_sentry_noop_when_dsn_empty():
    """settings.sentry_dsn bos ise sentry_sdk.init cagrilmaz."""
    settings.sentry_dsn = ""
    result = observability.init_sentry()
    assert result is False


def test_init_sentry_calls_sdk_init_when_dsn_set():
    """DSN set ise sentry_sdk.init cagrilmali, environment + sample rate gecmeli."""
    settings.sentry_dsn = "https://abc123@sentry.io/1"
    settings.sentry_env = "production"
    settings.sentry_traces_sample_rate = 0.25

    fake_sentry = MagicMock()
    fake_fastapi = MagicMock()
    fake_sqlalchemy = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "sentry_sdk": fake_sentry,
            "sentry_sdk.integrations.fastapi": MagicMock(FastApiIntegration=fake_fastapi),
            "sentry_sdk.integrations.sqlalchemy": MagicMock(SqlalchemyIntegration=fake_sqlalchemy),
        },
    ):
        result = observability.init_sentry()

    assert result is True
    fake_sentry.init.assert_called_once()
    kwargs = fake_sentry.init.call_args.kwargs
    assert kwargs["dsn"] == "https://abc123@sentry.io/1"
    assert kwargs["environment"] == "production"
    assert kwargs["traces_sample_rate"] == 0.25


def test_init_sentry_returns_false_on_import_error():
    """sentry_sdk yuklu degilse no-op, log warning."""
    settings.sentry_dsn = "https://abc@sentry.io/1"

    with patch.dict("sys.modules", {"sentry_sdk": None}):
        result = observability.init_sentry()

    assert result is False


def test_init_otel_noop_when_endpoint_empty():
    """settings.otel_endpoint bos ise OTel init no-op."""
    settings.otel_endpoint = ""
    fake_app = MagicMock()
    result = observability.init_otel(fake_app)
    assert result is False


def test_init_otel_returns_false_on_import_error():
    """opentelemetry paketleri yoksa no-op, log warning."""
    settings.otel_endpoint = "http://tempo:4318/v1/traces"
    fake_app = MagicMock()

    with patch.dict("sys.modules", {"opentelemetry": None}):
        result = observability.init_otel(fake_app)

    assert result is False


def test_release_tag_reads_git_sha_env():
    """GIT_SHA env set ise release tag olarak doner."""
    with patch.dict("os.environ", {"GIT_SHA": "abc123def"}, clear=False):
        assert observability._release_tag() == "abc123def"


def test_release_tag_returns_none_when_env_unset():
    """GIT_SHA bos ise None doner."""
    import os
    original = os.environ.pop("GIT_SHA", None)
    try:
        assert observability._release_tag() is None
    finally:
        if original is not None:
            os.environ["GIT_SHA"] = original
