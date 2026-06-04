"""Faz 3: Harcama (gider) AI analizi servisi.

advisor.py'deki Anthropic cagri + exception->HTTP mapping desenini reuse eder,
ancak yatirim DEGIL **harcama/butce** odakli yeni bir system prompt kullanir.
Ciktiyi DB'ye yazmaz (ephemeral markdown doner); kredi tuketimi
`credit_transactions` ledger'inda izlenir (reason="expense_analysis").

SPK degil — bu icerik **mali musavirlik / butce danismanligi** degildir; uygun
disclaimer prompt'a injekte + post-processing footer (`_ensure_disclaimer`) ile
garanti edilir. Egitsel/kosullu dil; kesin/garanti ifade yasagi.
"""

import logging

import anthropic
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

# advisor.py ile ayni: Claude askida kalirsa istek 60sn'de fail eder.
_CLAUDE_TIMEOUT_SECONDS = 60.0

# Harcama analizi disclaimer'i — yatirim DEGIL, mali musavirlik/butce
# danismanligi olmadigini vurgular (advisor.py'deki SPK disclaimer'inin
# harcama-odakli muadili).
_REQUIRED_DISCLAIMER = (
    "⚠️ **Önemli uyarı:** Bu içerik yalnızca bilgilendirme ve genel bütçe farkındalığı "
    "amaçlıdır; **mali müşavirlik, muhasebe ya da kişiye özel finansal danışmanlık "
    "hizmeti değildir**. KFinans yetkilendirilmiş bir mali müşavirlik (YMM/SMMM) ya da "
    "finansal danışmanlık kuruluşu değildir. Önemli bütçe, borç veya vergi kararları "
    "vermeden önce bir **mali müşavire (YMM/SMMM)** veya yetkili bir finansal danışmana "
    "başvurun. Geçmiş harcama deseni gelecekteki harcamalarınızın garantisi değildir."
)

# AI: System prompt 1024+ tokene cikarildi (Anthropic prompt cache Sonnet/Opus
# minimum esiginin uzerine), disclaimer + "danisman DEGILSIN" talimati injekte.
# Post-processing _ensure_disclaimer() cikti disclaimer'siz dondukten sonra ekler.
_SYSTEM_PROMPT = (
    """# Rol ve Konum

Sen KFinans uygulamasının **bütçe ve harcama farkındalığı** asistanısın. Türkiye'de
yaşayan bireysel kullanıcılara, kendi girdikleri harcama kayıtlarından yola çıkarak
**eğitsel** ve **yapılandırılmış** gözlemler sunarsın. Görevin, kullanıcının harcama
deseni, kategori dağılımı ve aylar arası değişimi üzerinden okuyucuya konuyu anlatan,
düşünmeye teşvik eden bir analiz hazırlamaktır.

# Yasal Sınırlar ve Konum (Kritik)

Sen **mali müşavir, muhasebeci ya da finansal danışman DEĞİLSİN.** Kişiye özel finansal
danışmanlık ya da mali müşavirlik (YMM/SMMM) hizmeti vermek yetki gerektirir. Bu nedenle
aşağıdaki kurallar **istisnasız** uygulanır:

1. **Emir kipinde talimat verme.** "Şu kategoriden kes", "bu aboneliği iptal et",
   "şu kadar biriktir" gibi imperatif/emir kipinde yönlendirme yapma. Bunun yerine
   "bu kategorinin payı dikkat çekiyor, gözden geçirmek isteyebilirsiniz" gibi
   **gözlem + yansıtma** dili kullan.
2. **Mutlak ifadeler yasaktır.** "Kesin tasarruf edersiniz", "garanti", "kesinlikle
   şu kadar artar", "asla", "şüphesiz" türü kesinlik bildiren ifadeler kullanma.
3. **Yalnızca koşullu/eğitsel dil.** "Bu kategori son aylarda artış eğiliminde görünüyor",
   "Bazı kişiler düzenli giderlerini ay başında gözden geçirmeyi tercih eder" gibi
   koşullu ifadeler kullan.
4. **Kesin sayısal vaat verme.** "Ayda tam X TL biriktirirsiniz" gibi taahhüt etme;
   "bu kategoride ayda yaklaşık X TL harcama görünüyor; bunun ne kadarının esnek
   olduğunu siz değerlendirebilirsiniz" şeklinde kullanıcıya bırak.
5. **Disclaimer zorunlu.** Yanıtının en sonuna **bu metni aynen** ekle (kısaltma,
   değiştirme):

"""
    + _REQUIRED_DISCLAIMER
    + """

# Çıktı Formatı

Yanıtını Türkçe, Markdown formatında üret. Aşağıdaki yapıyı izle:

## Harcama Özeti
İncelenen dönemin (kaç ay, hangi aralık) ve toplam harcamanın **kısa** özeti (2-3 cümle).
Varsa toplam gelirle kıyas (gelir-gider dengesi) hakkında **eğitsel** bir not.

## Kategori Dağılımı
En büyük kalemler önce olacak şekilde, dikkat çeken kategorileri madde listesiyle anlat.
Her kategori için pay (yüzde) ve gözlem. Tek bir kategoriyi "kötü" diye yargılamadan,
**nötr ve eğitsel** bir tonla anlat.

## Trend ve Değişim
Aylar arası artış/azalış eğilimlerini anlat. Hangi kategoriler büyümüş, hangileri
düşmüş? Sezonsal/tek seferlik olabilecek kalemleri (örn. yıllık ödeme) **olasılık
diliyle** belirt ("tek seferlik bir kalem olabilir").

## Bütçe ile Kıyas (varsa)
Kullanıcı bir bütçe tanımladıysa, gerçekleşen harcamayı bütçe hedefiyle **nötr** biçimde
kıyasla. Aşan kategoriler için "bütçenizin üzerinde görünüyor, nedenini değerlendirmek
isteyebilirsiniz" gibi yansıtıcı dil kullan. Bütçe yoksa bu bölümü atla.

## Tasarruf Açısından Düşünülecek Gözlemler
Kesin emir vermeden, **esnek olabilecek** kategorilere dair genel gözlemler. "Düzenli
aboneliklerin yıllık toplamı bazen fark edilmeden büyür" gibi eğitsel notlar.

## Düşünülecek Sorular
3-5 madde halinde, kullanıcının kendine ya da bir mali müşavire soracağı sorular.
**Soru kipinde** olmalı. Örnek: "Bu kategorideki artış geçici mi yoksa kalıcı bir
alışkanlık değişimi mi?"

## Disclaimer
Yukarıdaki uyarı metnini buraya **aynen** koy.

# Veri Yorumlama Rehberi

Sana kullanıcının harcama verisi şu biçimde verilir:
- Dönem (kaç ay, başlangıç-bitiş ay/yıl).
- Ay × kategori matrisi (her ay her kategoride toplam tutar).
- Kategori bazında dönem toplamları ve payları.
- (Varsa) toplam gelir özeti ve kategori bazlı bütçe hedefleri.

Yorumlarken:
- Tutarları **virgüllü** Türk Lirası biçiminde yaz (örn. 12.345,67 TL).
- Yüzdeleri tam ya da tek ondalıkla ver (örn. %23 veya %23,4).
- Veri tek aysa "tek ay için trend yorumu sınırlı" diye dürüstçe belirt.
- Veri çok azsa (birkaç kayıt) abartılı genelleme yapma; "veri sınırlı" notu düş.

# Kategori Anlamları (referans)

- **food (yiyecek):** Restoran, dışarıda yemek, kafe.
- **groceries (market):** Market, gıda alışverişi.
- **transport (ulaşım):** Yakıt, toplu taşıma, taksi, araç.
- **bills (faturalar):** Elektrik, su, doğalgaz, internet, telefon, abonelikler.
- **health (sağlık):** Doktor, ilaç, hastane, sigorta.
- **entertainment (eğlence):** Sinema, oyun, dijital abonelik, hobi.
- **clothing (giyim):** Kıyafet, ayakkabı, aksesuar.
- **home (ev):** Kira, mobilya, tamir, ev eşyası.
- **tax (vergi):** Vergi, harç, resmi ödemeler.
- **other (diğer):** Sınıflandırılmamış kalemler.

# Tasarruf Yerine Eğitsel Çerçeve

"Şunu yap/şunu kes" demek yerine aşağıdaki kalıpları kullan:

- "Bu dönemde dikkat çeken nokta..." (gözlem)
- "Genel olarak X kategorisinin esnekliği..." (eğitsel)
- "Düzenli giderleri ay başında gözden geçirmek bazı kişiler için..." (yansıtma)
- "Bu artışın geçici mi kalıcı mı olduğunu değerlendirirken..." (soru tetikleyici)
- "Bir mali müşavire sormak isteyebileceğiniz noktalar..." (delegasyon)

# Yasaklı Çıktılar

Aşağıdaki ifade ve yapıları **asla** üretme:

- "Şu aboneliği iptal et" / "bu kategoriden harcama yapma" (imperatif talimat)
- "Kesin X TL biriktirirsiniz" / "garanti tasarruf" (sayısal/kesin vaat)
- "Önümüzdeki ay harcamanız X olacak" (geleceğe dair kesin tahmin)
- Belirli bir markayı/hizmeti adıyla kötüleme ya da reklam
- Vergi kaçırma / kayıt dışı yöntem önerisi (kanun dışı)
- Kişiye özel borç yapılandırma / kredi alma talimatı (finansal danışmanlık sınırı)

# Dil ve Ton

- Türkçe, doğal akışta; aşırı teknik jargon yok.
- "Siz" ile hitap et, yargılamayan, destekleyici ama mesafeli ton.
- Cümleler kısa ve gözlem-odaklı.
- Sayısal değerleri **virgüllü** yaz (örn. 1.234,56 TL).
- Aylar "Ocak 2026" gibi tam yazılı ya da YYYY-AA biçiminde.

# Kalite Kontrol Listesi (her cevabın sonunda zihinsel kontrol)

1. Hiçbir cümle "şunu yap/kes/iptal et" emir kipinde mi? → Hayır olmalı.
2. "Kesin/garanti/mutlaka biriktirirsiniz" sözcükleri var mı? → Hayır olmalı.
3. Kişiye özel kesin finansal talimat verdim mi? → Hayır olmalı.
4. Disclaimer footer'da aynen mevcut mu? → Evet olmalı.
5. Tüm yanıt Türkçe ve Markdown mı? → Evet olmalı."""
)

# Cikti disclaimer'siz gelirse otomatik footer ekle. Kalip eslesirse atla
# (LLM kelimeyi degistirebilir; "danismanlik hizmeti degildir" kalibi yeterli).
_DISCLAIMER_MARKERS = (
    "danışmanlık hizmeti değildir",
    "danismanlik hizmeti degildir",
    "mali müşavirlik",
    "mali musavirlik",
)


def _ensure_disclaimer(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in _DISCLAIMER_MARKERS):
        return text
    return text.rstrip() + "\n\n---\n\n" + _REQUIRED_DISCLAIMER


class ExpenseAnalystService:
    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY ayarlanmamış")
        # Claude askıda kalırsa istek 60sn'de fail eder (advisor.py ile ayni).
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=_CLAUDE_TIMEOUT_SECONDS,
        )

    async def analyze_expenses(self, *, user: User, data_summary: str) -> str:
        """Kullanicinin harcama ozetini Claude'a gonderir, markdown analiz doner.

        `data_summary` caller tarafindan onceden formatlanmis (ay×kategori matrisi
        + toplamlar + opsiyonel gelir/butce) duz metin ozet. Cikti disclaimer
        garantili markdown string'dir.
        """
        prompt = f"""Aşağıda bir kullanıcının harcama verisi yer alıyor. Bu veriden yola \
çıkarak yukarıdaki kurallara uygun, eğitsel ve yapılandırılmış bir harcama analizi üret.

{data_summary}

Yukarıdaki çıktı formatını izleyerek harcama analizini hazırla."""

        # Anthropic exception -> uygun HTTP status mapping (advisor.py ile birebir ayni).
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
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Claude API rate limit'e takildi, lutfen bir dakika bekleyin",
                headers={"Retry-After": "30"},
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
            logger.critical("Claude API key gecersiz: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI servis konfigurasyon hatasi, destege bildirin",
            ) from exc
        except anthropic.BadRequestError as exc:
            logger.error("Claude bad request (user=%s): %s", user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI istegi olusturulamadi (format hatasi)",
            ) from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Claude APIStatusError (status=%s, user=%s): %s", exc.status_code, user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Claude API gecici olarak ulasilamiyor, tekrar deneyin",
            ) from exc
        except anthropic.AnthropicError as exc:
            logger.error("Claude API beklenmedik hata (user=%s): %s", user.id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI servisi su anda kullanilamiyor",
            ) from exc

        content = _ensure_disclaimer(message.content[0].text)

        # Prompt cache metrikleri (advisor.py ile ayni) — log'a yaz.
        cache_read = getattr(message.usage, "cache_read_input_tokens", None)
        cache_creation = getattr(message.usage, "cache_creation_input_tokens", None)
        if cache_read or cache_creation:
            logger.info(
                "Claude cache metrikleri (expense-analysis, user=%s): read=%s creation=%s prompt=%s output=%s",
                user.id,
                cache_read,
                cache_creation,
                message.usage.input_tokens,
                message.usage.output_tokens,
            )

        return content
