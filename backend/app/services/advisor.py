import logging

import anthropic
from fastapi import HTTPException, status

from app.config import settings
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.services.aggregator import calculate_breakdown

logger = logging.getLogger(__name__)

# AI-001 (FAZ H): Claude API cagrisi timeout
# httpx default no-timeout — slow Claude tarafi tum FastAPI worker'i bloke ederdi.
_CLAUDE_TIMEOUT_SECONDS = 60.0

_SYSTEM_PROMPT = """Deneyimli bir portföy danışmanısın.
Türk yatırımcısı için gerçekçi, uygulanabilir tavsiyeler üretiyorsun.
Yanıtını Türkçe, Markdown formatında ver: başlıklar ve madde listeleri kullan.
Tavsiyelerini net, somut ve pratik tut."""

HORIZON_LABELS = {
    "medium": "orta vade (3-12 ay)",
    "long": "uzun vade (1-3 yıl)",
}


class AdvisorService:

    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY ayarlanmamış")
        # AI-001: timeout sinirla — Claude askıda kalırsa istek 60sn'de fail eder.
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=_CLAUDE_TIMEOUT_SECONDS,
        )

    async def generate(self, user: User, snapshot: PortfolioSnapshot, horizon: str) -> InvestmentAdvice:
        breakdown = calculate_breakdown(snapshot)

        staking_lines = "\n".join(
            f"  - {pos.provider.upper()}: {pos.staked_quantity} adet stake"
            for pos in snapshot.asset_positions
            if pos.staked_quantity > 0
        )

        prompt = f"""Portföy özeti:
- Risk profili: {user.risk_profile}
- Toplam değer: {snapshot.total_value_tl:,.2f} TL
- Dağılım: Kripto %{breakdown.crypto_pct}, Stake kripto %{breakdown.staked_crypto_pct}, Fon %{breakdown.fund_pct}, BES %{breakdown.pension_pct}
- Staking pozisyonları:
{staking_lines or "  Yok"}
- En yüksek değerli varlıklar: {", ".join(p.symbol for p in breakdown.top_assets[:3])}

{HORIZON_LABELS[horizon]} için yatırım tavsiyesi ver."""

        # AI-001 (FAZ H): Anthropic exception -> uygun HTTP status mapping.
        # FastAPI exception handler raw 500 yerine kullaniciya anlamli hata doner.
        try:
            message = await self._client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},  # prompt caching
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError as exc:
            logger.warning("Claude rate limit (user=%s): %s", user.id, exc)
            # 429 + Retry-After header (default 30sn — Anthropic anlik degeri saglamiyor)
            retry_after = "30"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Claude API rate limit'e takildi, lutfen bir dakika bekleyin",
                headers={"Retry-After": retry_after},
            ) from exc
        except anthropic.APITimeoutError as exc:
            logger.warning("Claude timeout (user=%s, %ss): %s", user.id, _CLAUDE_TIMEOUT_SECONDS, exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Claude API zaman asimina ugradi, tekrar deneyin",
            ) from exc
        except anthropic.APIConnectionError as exc:
            logger.warning("Claude baglanti hatasi (user=%s): %s", user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Claude API'ye baglanti kurulamadi, tekrar deneyin",
            ) from exc
        except anthropic.AuthenticationError as exc:
            # API key gecersiz/expired — KULLANICI HATASI DEGIL, ops/dev problemi
            logger.critical("Claude API key gecersiz: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI servis konfigurasyon hatasi, destege bildirin",
            ) from exc
        except anthropic.BadRequestError as exc:
            # Prompt format hatasi, model adi yanlis vb.
            logger.error("Claude bad request (user=%s): %s", user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI istegi olusturulamadi (format hatasi)",
            ) from exc
        except anthropic.APIStatusError as exc:
            # 5xx genel veya OverloadedError (529)
            logger.warning("Claude APIStatusError (status=%s, user=%s): %s",
                           exc.status_code, user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Claude API gecici olarak ulasilamiyor, tekrar deneyin",
            ) from exc
        except anthropic.AnthropicError as exc:
            # SDK base exception — beklenmedik tipler icin generic fallback
            logger.error("Claude API beklenmedik hata (user=%s): %s", user.id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI servisi su anda kullanilamiyor",
            ) from exc

        content = message.content[0].text

        # AI-002 (FAZ H): Prompt cache metriklerini cek + log'a yaz.
        # SDK 0.40+ Usage objesinde cache_read_input_tokens / cache_creation_input_tokens.
        # Eski SDK'da yok -> getattr fallback (None).
        cache_read = getattr(message.usage, "cache_read_input_tokens", None)
        cache_creation = getattr(message.usage, "cache_creation_input_tokens", None)
        if cache_read or cache_creation:
            logger.info(
                "Claude cache metrikleri (user=%s): read=%s creation=%s prompt=%s output=%s",
                user.id, cache_read, cache_creation,
                message.usage.input_tokens, message.usage.output_tokens,
            )

        return InvestmentAdvice(
            user_id=user.id,
            snapshot_id=snapshot.id,
            horizon=horizon,
            content=content,
            prompt_tokens=message.usage.input_tokens,
            completion_tokens=message.usage.output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )
