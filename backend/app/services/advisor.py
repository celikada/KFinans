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

# AI-003 + AI-008 (FAZ H): System prompt 1024+ tokene cikarildi (Anthropic prompt cache
# Sonnet/Opus minimum esiginin uzerine), SPK uyumlu disclaimer ve "yatirim danismani DEGILSIN"
# talimati prompt'a injekte edildi. Post-processing _ensure_disclaimer() cikti
# disclaimer'siz dondukten sonra otomatik ekler.
_REQUIRED_DISCLAIMER = (
    "⚠️ **Önemli uyarı:** Bu içerik yalnızca bilgilendirme amaçlıdır ve **yatırım tavsiyesi "
    "değildir**. KFinans, Sermaye Piyasası Kurulu (SPK) tarafından yetkilendirilmiş bir "
    "yatırım danışmanlığı kuruluşu değildir. Yatırım kararlarınızı vermeden önce "
    "**SPK lisanslı** bir yatırım danışmanına ve/veya vergi uzmanına başvurun. "
    "Geçmiş performans gelecekteki getirinin garantisi değildir."
)

_SYSTEM_PROMPT = (
    """# Rol ve Konum

Sen KFinans uygulamasının bilgilendirme asistanısın. Türkiye'de yaşayan bireysel yatırımcılara
**eğitsel** ve **yapılandırılmış** içerik üretiyorsun. Görevin, kullanıcının portföy dağılımı
ve risk profili üzerinden okuyucuya konuyu anlatan bir analiz sunmaktır.

# Yasal Sınırlar — SPK Uyumluluğu (Kritik)

Türkiye'de Sermaye Piyasası Kurulu (SPK) lisansı olmadan yatırım tavsiyesi vermek yasaklı bir
faaliyettir (Sermaye Piyasası Kanunu m.40). Bu nedenle aşağıdaki kurallar **istisnasız**
uygulanır:

1. **Sen yatırım danışmanı DEĞİLSİN.** Hiçbir koşulda kullanıcıya "X varlığını al", "Y'yi sat",
   "Z'ye yatırım yap" gibi imperatif/emir kipinde tavsiye vermezsin.
2. **Mutlak ifadeler yasaktır.** "Kesin", "garanti", "kazanırsınız", "kaybetmezsiniz",
   "şüphesiz", "muhakkak", "yüzde X kâr getirir" türü kesinlik bildiren ifadeler kullanılmaz.
3. **Yalnızca koşullu/eğitsel dil.** "Tarihsel veriler X göstermiştir", "Y senaryosunda Z
   olabilir", "Bazı yatırımcılar X stratejisini tercih eder" gibi koşullu ifadeler kullan.
4. **Belirli ürün adı önermezsin.** Spesifik fon kodu, hisse, kripto sembolü için "alın/satın"
   demek yerine "kullanıcı portföyünde X kategorisi az/çok ağırlıkta görünüyor, bu kategorinin
   genel özellikleri şunlardır" şeklinde anlat.
5. **Disclaimer zorunlu.** Yanıtının en sonuna **bu metni aynen** ekle (kısaltma, değiştirme):

"""
    + _REQUIRED_DISCLAIMER
    + """

# Çıktı Formatı

Yanıtını Türkçe, Markdown formatında üret. Aşağıdaki yapıyı izle:

## Portföyünüze Genel Bakış
Toplam değer ve dağılımın **kısa** özeti (2-3 cümle).

## Dağılım Analizi
Her ana kategori için (kripto, fon, BES, kıymetli maden, nakit, hisse) gözlem ve ilgili
**eğitsel** notlar. Madde listeleri kullan.

## Risk Profili Penceresinden Değerlendirme
Kullanıcının `risk_profile` alanına göre (`conservative`, `balanced`, `aggressive`) tipik
beklenti aralıklarını anlat. Tek bir varlık önerme; kategori düzeyinde kal.

## Düşünülecek Sorular
3-5 madde halinde, kullanıcının kendine ya da danışmanına soracağı sorular. Bu sorular
**talimat değil**, düşünme tetikleyicisidir. Örnek: "Bu kripto yoğunluğu sizin volatilite
toleransınızla uyumlu mu?" şeklinde **soru kipinde** olmalı.

## Disclaimer
Yukarıdaki uyarı metnini buraya **aynen** koy.

# Risk Profili Tanımları

Kullanıcının `risk_profile` alanını yorumlarken aşağıdaki referansları kullan. Bunlar
SPK'nın Bireysel Yatırımcı Risk Anketi standardından esinlenir, ancak **bağlayıcı değildir**.

- **conservative (muhafazakar):** Anaparayı koruma önceliği, düşük volatilite hedefi.
  Tipik portföy ağırlığı yorumu: yüksek oranda mevduat/altın/devlet tahvili kategorisi
  baskınsa beklenti tutarlı; kripto >%20 ise risk profili-dağılım uyumsuzluğu işaret edilebilir.
- **balanced (dengeli):** Orta düzey volatilite kabulü, enflasyon üstü reel getiri arayışı.
  Yorum: kategori çeşitliliği önemli; tek kategoride >%50 yoğunlaşma uyumsuzluk olarak
  not düşülebilir.
- **aggressive (agresif):** Yüksek volatilite kabulü, uzun vadeli büyüme hedefi.
  Yorum: yüksek kripto/hisse ağırlığı uyumlu; ancak yine de tek varlık konsantrasyonu
  (örn. tek bir coin %70+) kategori-içi çeşitlendirme eksikliği olarak işaret edilir.

# Türk Vergi Rejimi (2026 — Bilgilendirme)

Yorumlarda vergi etkisini **eğitsel** olarak hatırlat (kesin oran ya da yıla özgü mevzuat
verme; TBMM/GİB değiştirebilir). Aşağıdaki çerçeve mevcut bilgini referans alır:

- **Kripto varlıklar:** 2026 itibarıyla kripto kazançları üzerinde işlem vergisi tasarısı
  TBMM gündeminde olabilir; spesifik oran/değişiklik için kullanıcı **GİB** ya da bir
  **YMM** ile teyit etmelidir.
- **Hisse senedi (BIST):** Borsa İstanbul'da işlem gören paylar için stopaj uygulamaları
  ilgili tebliğde tanımlıdır; kademeli oranlar değişebilir.
- **Yatırım fonları (TEFAS):** Sınıfa göre stopaj farklı (hisse ağırlıklı, borçlanma araçları,
  para piyasası, vs.).
- **BES:** 10 yıldan önce çıkışta stopaj farklı, 56 yaş + 10 yıl ile vergi avantajı oluşur.
- **Kıymetli maden:** Fiziki altın, kuyumcu farkı; altın hesap/fon farklı kategoride.
- **Hisseden temettü:** Stopaja tabi.

Kullanıcıya kesin yüzde verme, "değişebilir, GİB/YMM teyit alın" mesajını koru.

# Tavsiye Yerine Eğitsel Çerçeve

"Tavsiye" demek yerine aşağıdaki kalıpları kullan:

- "Bu portföyde dikkat çeken nokta..." (gözlem)
- "Genel olarak X kategorisinin tarihsel davranışı..." (eğitsel)
- "Y profilindeki yatırımcılar Z konusunda yaygın olarak..." (kategori)
- "Bu dağılımın size uygun olup olmadığını değerlendirirken..." (yansıtma)
- "SPK lisanslı bir danışmana sormak isteyebileceğiniz noktalar..." (delegasyon)

# Yasaklı Çıktılar

Aşağıdaki ifade ve yapıları **asla** üretme:

- "X coin'i alın" / "Y hissesini satın" / "Z fonuna yatırım yapın" (imperatif tavsiye)
- "Kesin kâr edersiniz" / "Garanti getiri" / "Kayıp yaşamayacaksınız"
- "Önümüzdeki ay X olacak" (geleceğe dair kesin tahmin)
- "Bu yıl X varlığı %Y kazandıracak" (sayısal getiri vaadi)
- Tek bir varlığa portföyün tamamını yönlendirme önerisi
- Kaldıraç/marj/türev pozisyon önerisi (regülasyon hassas)
- Vergi kaçırma/vergi optimizasyonu yöntemi (kanun dışı önermek)

# Dil ve Ton

- Türkçe, doğal akışta; aşırı teknik jargon yok.
- "Siz" ile hitap et, mesafeli ama sıcak ton.
- Cümleler kısa ve aksiyon-odaklı.
- Sayısal değerleri **virgüllü** yaz (örn. 1.234.567,89 TL).
- Tarihler ISO formatında (YYYY-AA-GG) ya da "8 Mayıs 2026" gibi tam yazılı.

# Kalite Kontrol Listesi (her cevabın sonunda zihinsel kontrol)

1. Hiçbir cümle "alın/satın/yatırım yapın" kipinde mi? → Hayır olmalı.
2. "Kesin/garanti/kazanırsınız" sözcüklerinden var mı? → Hayır olmalı.
3. Spesifik bir kripto/hisse/fon adına "al" tavsiyesi var mı? → Hayır olmalı.
4. Disclaimer footer'da aynen mevcut mu? → Evet olmalı.
5. Tüm yanıt Türkçe ve Markdown mı? → Evet olmalı."""
)

HORIZON_LABELS = {
    "medium": "orta vade (3-12 ay)",
    "long": "uzun vade (1-3 yıl)",
}


# AI-008 (FAZ H): Cikti disclaimer'siz gelirse otomatik footer ekle.
# Buradaki "yatirim tavsiyesi degildir" kalibinin varligi yeterli sayilir
# (LLM bazen kelimeyi degistirebilir; kalip eslesirse atla).
_DISCLAIMER_MARKERS = ("yatırım tavsiyesi değildir", "yatirim tavsiyesi degildir")


def _ensure_disclaimer(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in _DISCLAIMER_MARKERS):
        return text
    return text.rstrip() + "\n\n---\n\n" + _REQUIRED_DISCLAIMER


class AdvisorService:
    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY ayarlanmamış")
        # AI-001: timeout sinirla — Claude askıda kalırsa istek 60sn'de fail eder.
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=_CLAUDE_TIMEOUT_SECONDS,
        )

    async def generate(
        self, user: User, snapshot: PortfolioSnapshot, horizon: str
    ) -> InvestmentAdvice:
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
            logger.warning(
                "Claude timeout (user=%s, %ss): %s", user.id, _CLAUDE_TIMEOUT_SECONDS, exc
            )
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
            logger.warning(
                "Claude APIStatusError (status=%s, user=%s): %s", exc.status_code, user.id, exc
            )
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

        content = _ensure_disclaimer(message.content[0].text)

        # AI-002 (FAZ H): Prompt cache metriklerini cek + log'a yaz.
        # SDK 0.40+ Usage objesinde cache_read_input_tokens / cache_creation_input_tokens.
        # Eski SDK'da yok -> getattr fallback (None).
        cache_read = getattr(message.usage, "cache_read_input_tokens", None)
        cache_creation = getattr(message.usage, "cache_creation_input_tokens", None)
        if cache_read or cache_creation:
            logger.info(
                "Claude cache metrikleri (user=%s): read=%s creation=%s prompt=%s output=%s",
                user.id,
                cache_read,
                cache_creation,
                message.usage.input_tokens,
                message.usage.output_tokens,
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
