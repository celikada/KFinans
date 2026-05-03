"""AdvisorService — Anthropic SDK ile Claude tavsiye uretimi.

Tum dis cagri (Anthropic API) AsyncMock ile patchlenir; gercek aga gidilmez.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.advisor import AdvisorService


@pytest.fixture(autouse=True)
def _restore_settings():
    """Test sirasinda anthropic_api_key set edilebilmesi icin restore."""
    original = settings.anthropic_api_key
    yield
    settings.anthropic_api_key = original


def _fake_user(risk: str = "balanced"):
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001", risk_profile=risk)


def _fake_snapshot(total: str = "100000.00"):
    return SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        snapshot_date=date(2026, 5, 2),
        total_value_tl=Decimal(total),
        asset_positions=[],
    )


def _fake_anthropic_message(text: str = "Test tavsiye"):
    """Anthropic SDK'nin Message yanit nesnesini taklit eder."""
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=120, output_tokens=80),
    )


class TestAdvisorInit:
    def test_raises_when_api_key_missing(self):
        settings.anthropic_api_key = ""
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            AdvisorService()

    def test_creates_client_when_key_set(self):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()
        assert svc._client is not None


class TestAdvisorGenerate:
    @pytest.mark.asyncio
    async def test_uses_settings_claude_model(self):
        """Hardcoded yerine settings.claude_model kullanildigini dogrula."""
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(return_value=_fake_anthropic_message())
        with patch.object(svc._client.messages, "create", mock_create):
            result = await svc.generate(
                user=_fake_user(),
                snapshot=_fake_snapshot(),
                horizon="medium",
            )

        # Çağrıdaki model parametresi config'ten geldi mi?
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == settings.claude_model
        assert call_kwargs["max_tokens"] == settings.claude_max_tokens
        assert result.horizon == "medium"
        assert result.content == "Test tavsiye"

    @pytest.mark.asyncio
    async def test_records_token_usage(self):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(return_value=_fake_anthropic_message())
        with patch.object(svc._client.messages, "create", mock_create):
            advice = await svc.generate(
                user=_fake_user(),
                snapshot=_fake_snapshot(),
                horizon="long",
            )

        assert advice.prompt_tokens == 120
        assert advice.completion_tokens == 80

    @pytest.mark.asyncio
    async def test_horizon_label_in_prompt(self):
        """Prompt icinde horizon etiketi (orta vade / uzun vade) yer almali."""
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(return_value=_fake_anthropic_message())
        with patch.object(svc._client.messages, "create", mock_create):
            await svc.generate(
                user=_fake_user(risk="aggressive"),
                snapshot=_fake_snapshot("250000.00"),
                horizon="long",
            )

        sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "uzun vade" in sent_prompt
        assert "aggressive" in sent_prompt

    @pytest.mark.asyncio
    async def test_uses_prompt_caching_on_system(self):
        """System prompt cache_control: ephemeral ile gonderiliyor mu?"""
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(return_value=_fake_anthropic_message())
        with patch.object(svc._client.messages, "create", mock_create):
            await svc.generate(
                user=_fake_user(),
                snapshot=_fake_snapshot(),
                horizon="medium",
            )

        system = mock_create.call_args.kwargs["system"]
        assert isinstance(system, list)
        assert system[0]["cache_control"]["type"] == "ephemeral"
