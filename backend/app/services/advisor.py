import anthropic
from app.config import settings
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.services.aggregator import calculate_breakdown

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
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

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

        content = message.content[0].text

        return InvestmentAdvice(
            user_id=user.id,
            snapshot_id=snapshot.id,
            horizon=horizon,
            content=content,
            prompt_tokens=message.usage.input_tokens,
            completion_tokens=message.usage.output_tokens,
        )
