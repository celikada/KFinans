"""AdvisorService — Anthropic SDK ile Claude tavsiye uretimi.

Tum dis cagri (Anthropic API) AsyncMock ile patchlenir; gercek aga gidilmez.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.advisor import (
    _REQUIRED_DISCLAIMER,
    _SYSTEM_PROMPT,
    AdvisorService,
    _ensure_disclaimer,
)


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
        # AI-008: LLM disclaimer'siz cikti dondurdu, post-processing eklemis olmali
        assert "Test tavsiye" in result.content
        assert "yatırım tavsiyesi değildir" in result.content.lower()

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


# AI-003 (FAZ H): system prompt 1024+ token (Anthropic prompt cache esigi)
class TestSystemPromptCacheEligibility:
    """Anthropic prompt cache Sonnet/Opus modellerinde 1024 token altinda sessizce
    devre disi kalir. system prompt'un guvenle bu esigi astigini dogrula.
    Turkce icin ortalama 3-4 char/token; cok muhafazakar 4 char/token referansi
    ile minimum 4096 char olmali. Asagi yonde guvenlik payi icin 5000+."""

    def test_system_prompt_long_enough_for_cache(self):
        # 4096 chars ≈ 1024 token (4 char/token muhafazakar tahmin)
        # Pratikte Turkce 3 char/token civari -> 6154 char ≈ 1538-2051 token
        assert len(_SYSTEM_PROMPT) >= 5000, (
            f"system prompt {len(_SYSTEM_PROMPT)} char < 5000 — "
            "Anthropic prompt cache 1024 token esigi guvensiz"
        )

    def test_system_prompt_mentions_spk_compliance(self):
        # AI-008: SPK uyumlulugu prompt'a injekte edilmeli
        assert "SPK" in _SYSTEM_PROMPT
        assert "yatırım danışmanı DEĞİLSİN" in _SYSTEM_PROMPT or \
               "danışman değilsin" in _SYSTEM_PROMPT.lower()

    def test_system_prompt_lists_forbidden_phrases(self):
        # Mutlak ifadelerin yasak oldugu prompt'ta gorunmeli
        for forbidden in ["Kesin", "garanti", "kazanırsınız"]:
            assert forbidden in _SYSTEM_PROMPT, f"Yasakli ifade rehberi eksik: {forbidden}"

    def test_system_prompt_includes_required_disclaimer(self):
        # _REQUIRED_DISCLAIMER tam metni prompt icine gomulu olmali (LLM kopyalasin)
        assert _REQUIRED_DISCLAIMER in _SYSTEM_PROMPT


# AI-008 (FAZ H): SPK disclaimer post-processing
class TestEnsureDisclaimer:
    def test_appends_disclaimer_when_missing(self):
        text = "## Genel Bakış\n\nPortföyünüz dengeli görünüyor."
        result = _ensure_disclaimer(text)
        assert "yatırım tavsiyesi değildir" in result.lower()
        assert "SPK" in result
        # Orijinal icerik korunmus
        assert "dengeli görünüyor" in result

    def test_keeps_disclaimer_when_already_present(self):
        # LLM zaten disclaimer eklemisse cift eklemez
        text = "## Görüş\n\nİçerik...\n\n⚠️ Yatırım tavsiyesi değildir, danışmana sorun."
        result = _ensure_disclaimer(text)
        # Tek bir disclaimer marker olmali
        assert result.lower().count("yatırım tavsiyesi değildir") == 1

    def test_handles_ascii_disclaimer_marker(self):
        # Bazi LLM ciktilarinda Turkce karakter olmadan donebilir
        text = "Icerik\n\nYatirim tavsiyesi degildir, lutfen danisin."
        result = _ensure_disclaimer(text)
        # Marker tanindi, ekstra eklenmedi
        assert "Önemli uyarı" not in result

    @pytest.mark.asyncio
    async def test_advisor_output_always_has_disclaimer(self):
        """End-to-end: LLM disclaimer'siz dondurse bile kullaniciya disclaimer'li gider."""
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        # LLM disclaimer'siz cikti dondurdu
        no_disclaimer_msg = _fake_anthropic_message(
            text="## Genel Bakış\n\nPortföy dengeli, kripto %30."
        )
        mock_create = AsyncMock(return_value=no_disclaimer_msg)
        with patch.object(svc._client.messages, "create", mock_create):
            advice = await svc.generate(
                user=_fake_user(),
                snapshot=_fake_snapshot(),
                horizon="medium",
            )

        assert "yatırım tavsiyesi değildir" in advice.content.lower()
        assert "SPK" in advice.content


# AI-001 (FAZ H): Anthropic exception -> uygun HTTP status mapping
class TestAdvisorExceptionMapping:
    """Anthropic SDK exception'lari kullaniciya anlamli HTTP status doner."""

    def _httpx_response(self, status_code: int = 500) -> httpx.Response:
        return httpx.Response(status_code, request=httpx.Request("POST", "https://x"))

    @pytest.mark.asyncio
    async def test_rate_limit_error_returns_429_with_retry_after(self):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(side_effect=anthropic.RateLimitError(
            message="rate limit",
            response=self._httpx_response(429),
            body=None,
        ))
        with patch.object(svc._client.messages, "create", mock_create):
            with pytest.raises(HTTPException) as exc:
                await svc.generate(
                    user=_fake_user(), snapshot=_fake_snapshot(), horizon="medium",
                )
        assert exc.value.status_code == 429
        assert exc.value.headers and exc.value.headers.get("Retry-After") == "30"

    @pytest.mark.asyncio
    async def test_timeout_error_returns_504(self):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(side_effect=anthropic.APITimeoutError(
            request=httpx.Request("POST", "https://x"),
        ))
        with patch.object(svc._client.messages, "create", mock_create):
            with pytest.raises(HTTPException) as exc:
                await svc.generate(
                    user=_fake_user(), snapshot=_fake_snapshot(), horizon="medium",
                )
        assert exc.value.status_code == 504

    @pytest.mark.asyncio
    async def test_connection_error_returns_503(self):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(side_effect=anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://x"),
        ))
        with patch.object(svc._client.messages, "create", mock_create):
            with pytest.raises(HTTPException) as exc:
                await svc.generate(
                    user=_fake_user(), snapshot=_fake_snapshot(), horizon="medium",
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_authentication_error_returns_500_critical_log(self, caplog):
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        mock_create = AsyncMock(side_effect=anthropic.AuthenticationError(
            message="invalid api key",
            response=self._httpx_response(401),
            body=None,
        ))
        with patch.object(svc._client.messages, "create", mock_create):
            with pytest.raises(HTTPException) as exc:
                with caplog.at_level("CRITICAL"):
                    await svc.generate(
                        user=_fake_user(), snapshot=_fake_snapshot(), horizon="medium",
                    )
        assert exc.value.status_code == 500
        # Log critical (ops aksiyon gerekli)
        assert any("Claude API key gecersiz" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_overloaded_error_returns_503(self):
        """OverloadedError APIStatusError'in alt sinifi (status 529)."""
        settings.anthropic_api_key = "sk-ant-test"
        svc = AdvisorService()

        # Anthropic SDK 0.x APIStatusError generic — 529 Overloaded
        mock_create = AsyncMock(side_effect=anthropic.APIStatusError(
            message="overloaded",
            response=self._httpx_response(529),
            body=None,
        ))
        with patch.object(svc._client.messages, "create", mock_create):
            with pytest.raises(HTTPException) as exc:
                await svc.generate(
                    user=_fake_user(), snapshot=_fake_snapshot(), horizon="medium",
                )
        assert exc.value.status_code == 503
