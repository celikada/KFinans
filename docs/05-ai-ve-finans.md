# AI Tavsiye Motoru ve Finansal Hesaplamalar

**Sahip ajanlar:** `ai-expert`, `finance-expert`
**İlgili:** [api-referansi.md](./api-referansi.md), [kredi-sistemi.md](./kredi-sistemi.md)

---

# Bölüm A — AI Tavsiye Motoru

## A.1 Mevcut Fonksiyonel Gereksinimler

| Bileşen                                                               | Durum                                 |
| --------------------------------------------------------------------- | ------------------------------------- |
| Anthropic SDK entegrasyonu (`AsyncAnthropic`, 60 sn timeout)          | ✅ Aktif                               |
| `claude-sonnet-4-6` model kullanımı (config'den)                      | ✅ Aktif                               |
| System prompt + prompt caching (`cache_control: ephemeral`)           | ✅ Aktif (1024+ token, SPK uyumlu)     |
| Token sayımı `investment_advice` tablosuna kayıt                      | ✅ Aktif                               |
| Cache metrikleri DB'ye kayıt (`cache_read_tokens`, `cache_creation_tokens`) | ✅ Aktif (AI-002)               |
| Türkçe Markdown çıktı                                                 | ✅ Aktif                               |
| Risk profili + portföy dağılımı + staking pozisyonları prompt'a dahil | ✅ Aktif                               |
| Vade etiketi (`medium` / `long`)                                      | ✅ Aktif                               |
| SPK disclaimer post-processing (`_ensure_disclaimer`)                 | ✅ Aktif (AI-008)                       |
| Anthropic SDK exception → HTTP status mapping (timeout/rate limit/5xx) | ✅ Aktif (AI-001)                      |
| Anthropic için açık rıza kontrolü (`anthropic_consent_at` → 403)      | ✅ Aktif (AI-005, KVKK m.9)             |
| Kredi tüketimi (`credit_balance`, `credits_used`, atomik düşüm)       | ✅ Aktif (AI-007, tavsiye başına 1 kredi) |
| Audit log (`AuditAction.ADVICE_GENERATE`)                             | ✅ Aktif (AI-004)                       |
| Endpoint aktif (`POST /advice/generate`)                              | ⚠️ Kodda var; frontend kullanımı sınırlı |

**Bu davranışlar regresyon kabul etmez.**

---

## A.2 Mimari

```
Frontend
  ↓ POST /api/v1/advice/generate { horizon: "medium" }
api/v1/advice.py (slowapi 5/saat rate limit)
  ↓ 1) anthropic_consent_at IS NULL → 403 (AI-005, KVKK m.9)
  ↓ 2) credit_balance < ADVICE_COST (=1) → 402 Payment Required (AI-007)
  ↓ 3) son snapshot'ı çek (yoksa 404)
services/advisor.py: AdvisorService.generate(user, snapshot, horizon)
  ↓ calculate_breakdown(snapshot) — yüzde hesabı
  ↓ user prompt formatla
  ↓ AsyncAnthropic.messages.create(...)  (60 sn timeout, AI-001)
    ↓ system prompt (cached, ephemeral)
    ↓ user prompt (per-call)
    ↓ Anthropic exception → HTTP 429/503/504/500 mapping (AI-001)
  ↓ _ensure_disclaimer(content) — SPK footer garanti (AI-008)
  ↓ InvestmentAdvice modelini oluştur (token + cache metrikleri)
api/v1/advice.py (devam, transactional)
  ↓ advice.credits_used = 1; user.credit_balance -= 1 (AI-007 atomik düşüm)
  ↓ audit log: AuditAction.ADVICE_GENERATE (AI-004)
  ↓ db.commit()  → AI fail durumunda buraya gelinmez, kredi düşmez
  ↓ JSON response
```

> **Not (kredi sistemi kapsamı):** Buradaki kredi düşümü uygulandı (`credit_balance`
> sütunu + `credits_used` + atomik düşüm). Kredi **satın alma / ödeme** akışı (iyzico,
> `credit_transactions` tablosu, checkout/webhook) henüz uygulanmadı — bkz.
> [kredi-sistemi.md](./kredi-sistemi.md) (Faz 3 tasarımı).

## A.3 Model Seçimi

| Görev                           | Model                       | Gerekçe                                          |
| ------------------------------- | --------------------------- | ------------------------------------------------ |
| Standart tavsiye, vade analizi  | `claude-sonnet-4-6`         | Hız + kalite dengesi, maliyet uygun              |
| Karmaşık portföy (20+ varlık)   | `claude-opus-4-7`           | Çok varlık + staking + döviz; derin akıl yürütme |
| Hızlı sınıflandırma, etiketleme | `claude-haiku-4-5-20251001` | Düşük maliyet, basit görev                       |

**Çözüldü (2026-05-01):** Model adı ve max_tokens config'e taşındı:
```python
# app/config.py
claude_model: str = "claude-sonnet-4-6"
claude_max_tokens: int = 1024
```
`.env` ile override edilebilir (`CLAUDE_MODEL=...`, `CLAUDE_MAX_TOKENS=...`). Yeni Claude sürümüne geçişte kod değişikliği gerekmez.

## A.4 Prompt Tasarımı

### A.4.1 System Prompt (Cache'li)
`advisor.py::_SYSTEM_PROMPT` artık **1024+ token** uzunluğunda, SPK uyumlu, yapılandırılmış
bir prompt'tur (AI-003 + AI-008). İçeriği (özet):
- **Rol ve Konum** — "bilgilendirme asistanı", yatırım danışmanı DEĞİL
- **Yasal Sınırlar — SPK Uyumluluğu** — Sermaye Piyasası Kanunu m.40 atfı + 5 istisnasız kural
  (imperatif tavsiye yok, mutlak ifade yok, koşullu/eğitsel dil, ürün adı önermeme, zorunlu disclaimer)
- **Çıktı Formatı** — sabit Markdown başlık yapısı (Genel Bakış / Dağılım Analizi / Risk Profili
  Penceresinden Değerlendirme / Düşünülecek Sorular / Disclaimer)
- **Risk Profili Tanımları** — conservative / balanced / aggressive yorum referansları
- **Türk Vergi Rejimi (2026)** — eğitsel hatırlatma (kesin oran verme, GİB/YMM teyit mesajı)
- **Tavsiye Yerine Eğitsel Çerçeve** + **Yasaklı Çıktılar** + **Dil ve Ton** + **Kalite Kontrol Listesi**

Detay: `_REQUIRED_DISCLAIMER` sabiti SPK uyumlu uyarı metnini tutar; prompt'a injekte edilir.

- **Neden 1024+ token?** Anthropic Sonnet/Opus prompt cache **minimum eşiği** 1024 token;
  daha kısa system prompt cache'lenemez. Eski ~80 token'lık prompt cache hit alamıyordu.
- Her çağrıda aynı → `cache_control: ephemeral` (5 dk TTL)
- Tasarruf: cache hit'te input token'ın büyük kısmı cache'den okunur (`cache_read_input_tokens`)

### A.4.2 User Prompt (Dinamik)
```
Portföy özeti:
- Risk profili: {user.risk_profile}
- Toplam değer: {snapshot.total_value_tl:,.2f} TL
- Dağılım: Kripto %{breakdown.crypto_pct}, Stake kripto %{breakdown.staked_crypto_pct},
           Fon %{breakdown.fund_pct}, BES %{breakdown.pension_pct}
- Staking pozisyonları:
  - SONIC: 1500 adet stake
  - AVALANCHE_P: 25 adet stake
- En yüksek değerli varlıklar: BTC, ETH, GO3

{HORIZON_LABELS[horizon]} için yatırım tavsiyesi ver.
```
- ~150-300 token (portföy büyüklüğüne göre)

### A.4.3 Token Bütçesi
System prompt artık 1024+ token (cache eşiği). Cache hit'te input maliyeti `cache_read`
indirimli okunur; cache miss'te `cache_creation` orta bedelli yazılır.

| Bileşen                   | Token (yaklaşık)        |
| ------------------------- | ----------------------- |
| System prompt             | ~1024+ (cache hit'te indirimli `cache_read`) |
| User prompt               | ~200                    |
| Output (max)              | `settings.claude_max_tokens` (default 1024) |

Gerçek değerler `investment_advice` tablosunda kayıtlıdır:
`prompt_tokens`, `completion_tokens`, `cache_read_tokens`, `cache_creation_tokens`.

## A.5 Eklenecek İyileştirmeler

### A.5.1 Hata Yönetimi ✅ (Uygulandı — AI-001)
`advisor.py::generate()` Anthropic SDK'nın exception taksonomisini HTTP status'a maplar:
```python
except anthropic.RateLimitError:      # → 429 + Retry-After: 30
except anthropic.APITimeoutError:     # → 504 (60 sn timeout)
except anthropic.APIConnectionError:  # → 503
except anthropic.AuthenticationError: # → 500 (ops/dev problemi, logger.critical)
except anthropic.BadRequestError:     # → 500 (format hatası)
except anthropic.APIStatusError:      # → 503 (5xx / OverloadedError 529)
except anthropic.AnthropicError:      # → 503 (generic fallback)
```

### A.5.2 Cache Hit Oranı İzleme ✅ (Kısmen — AI-002)
Cache metrikleri DB'ye yazılıyor (`investment_advice.cache_read_tokens` +
`cache_creation_tokens`, nullable — eski SDK geri uyumlu). Değer varsa `logger.info` ile
loglanır:
```python
cache_read = getattr(message.usage, "cache_read_input_tokens", None)
cache_creation = getattr(message.usage, "cache_creation_input_tokens", None)
...
return InvestmentAdvice(
    ...,
    prompt_tokens=message.usage.input_tokens,
    completion_tokens=message.usage.output_tokens,
    cache_read_tokens=cache_read,
    cache_creation_tokens=cache_creation,
)
```
**Hâlâ eksik:** Cache hit oranı dashboard/alert (`GET /metrics/ai` endpoint) — backlog,
bkz. `docs/audit-2026-05-22/ai-notes.md` #2.

### A.5.3 Prompt Versiyonlama (Faz 3)
```python
ADVICE_PROMPT_VERSION = "v2"  # her major değişiklikte arttır

# investment_advice tablosuna ekle:
prompt_version: Mapped[str] = mapped_column(String(10), default="v2")
```
A/B test için kritik.

### A.5.4 Streaming Yanıt (Faz 4)
Uzun tavsiyeler için streaming:
```python
stream = await self._client.messages.stream(...)
async for chunk in stream:
    yield chunk.delta.text
```
Frontend Server-Sent Events ile alır → kullanıcı yanıt biter beklemeden okumaya başlar.

---

## A.6 KVKK Uyumu

> Anthropic ABD merkezli — yurt dışı veri aktarımı. Detay: [uyumluluk-kvkk.md](./uyumluluk-kvkk.md#5-üçüncü-taraf-veri-aktarımı)

### Veri Minimizasyonu (Aktif)
Anthropic'e gönderilen veri:
- ✅ Risk profili (string)
- ✅ Portföy yüzdeleri
- ✅ Staking miktarları (sembol bazında)
- ✅ Top 3 varlık sembolü
- ❌ E-posta GÖNDERİLMEZ
- ❌ User ID GÖNDERİLMEZ
- ❌ Cüzdan adresi GÖNDERİLMEZ
- ❌ Exchange API key GÖNDERİLMEZ

### Açık Rıza ✅ (Uygulandı — AI-005, KVKK m.9)
`anthropic_consent_at` (TIMESTAMPTZ) + `anthropic_consent_version` (String 10) kolonları
`users` tablosunda mevcut. `POST /advice/generate` ilk adımı:
```python
if current_user.anthropic_consent_at is None:
    raise HTTPException(403, "Anthropic API'ye veri aktarimi icin acik riza gerekli (KVKK m.9). ...")
```
Onay genel yurt dışı rıza (`overseas_consent_at`) ile ayrıdır — bu kolon spesifik olarak
Anthropic aktarımı içindir; metin güncellenince `anthropic_consent_version` ile re-accept
zorlanabilir. Her üretim ayrıca `AuditAction.ADVICE_GENERATE` ile audit'lenir (AI-004,
KVKK m.12 üçüncü taraf aktarım izleme).

---

# Bölüm B — Finansal Hesaplamalar

## B.1 Mevcut Fonksiyonel Gereksinimler

| Hesaplama                                       | Durum   |
| ----------------------------------------------- | ------- |
| USD/TRY kuru çekme (TCMB → exchangerate-api fallback) | ✅ Aktif |
| GBP/USD kuru çekme (TCMB derive → exchangerate-api)   | ✅ Aktif |
| Spot fiyat çekme (Binance → CoinGecko fallback) | ✅ Aktif |
| Kripto pozisyonu TL değer hesabı                | ✅ Aktif |
| Staking + pending rewards ayrımı                | ✅ Aktif |
| TEFAS fon fiyatı (sonPortfoyDegeri/sonPayAdedi) | ✅ Aktif |
| Yahoo Finance hisse fiyatı (TRY/USD/GBp)        | ✅ Aktif |
| WoW + MoM değişim hesabı                        | ✅ Aktif |
| Varlık türü dağılımı (breakdown)                | ✅ Aktif |
| Ağırlık yüzdesi (`weight_pct`)                  | ✅ Aktif |

## B.2 Para Birimi Normalizasyonu

### B.2.1 Hedef Para Birimi: TL
Tüm sunum, kıyaslama ve snapshot **TL** üzerinden yapılır. USD/EUR/GBP fiyatları işlem anında dönüştürülür.

### B.2.2 USD/TRY Kuru
```python
# aggregator.py — Faz 2'de TCMB primary'ye taşındı
async def fetch_usd_to_tl() -> Decimal:
    # 1) TCMB today.xml (https://www.tcmb.gov.tr/kurlar/today.xml) — ForexBuying
    # 2) Fallback: https://api.exchangerate-api.com/v4/latest/USD
    # 3) İkisi de fail → RuntimeError (snapshot iptal — 503)
```
TCMB XML'i 5 dk in-memory cache'lenir; aynı snapshot içinde tek HTTP çağrısı.
GBP/USD için aynı zincir: TCMB'den derive (`GBP/TRY ÷ USD/TRY`) → exchangerate-api → RuntimeError.

### B.2.3 GBp (Pence) Dönüşümü ✅ (Düzeltildi — 2026-04-30)
`api/v1/stocks.py::convert_to_tl` GBP/USD kuru (`aggregator.fetch_gbp_to_usd`) kullanır.
Eski "1 GBP = 1 USD" varsayımı kaldırıldı.
```python
# stocks.py::convert_to_tl — GBp dalı
if currency == "GBp":
    gbp = price / Decimal("100")          # pence → GBP
    usd = gbp * gbp_usd                    # GBP → USD
    return (usd * usd_tl).quantize(Decimal("0.0001"))  # USD → TL
```
`fetch_gbp_to_usd()` önceliği: TCMB (GBP/TRY ÷ USD/TRY oranı) → exchangerate-api → RuntimeError.
Test koruması: `test_stocks_currency.py`. (Detay: §B.10 #1.)

### B.2.4 Diğer Para Birimleri (Faz 3)
EUR, JPY, CHF gibi para birimleri için ECB veya TCMB ana kur tablosu entegre edilmeli.

## B.3 Kripto Değerleme

### B.3.1 Spot Fiyat
```python
# aggregator.py
async def fetch_spot_prices(symbols: list[str]) -> dict[str, Decimal]:
    # Binance USDT pair'leri (BTCUSDT, ETHUSDT vb.)
    # Symbol mapping: 'S' → 'SUSDT', 'AVAX' → 'AVAXUSDT' vb.
```

### B.3.2 Toplam Değer Formülü
```python
total_value_tl = (
    (liquid_quantity + staked_quantity) *   # toplam miktar
    unit_price_usd *                          # USD birim
    usd_tl                                    # TL kuru
).quantize(Decimal("0.01"))
```

### B.3.3 Pending Rewards
```python
rewards_value_tl = pending_rewards * unit_price_usd * usd_tl
```
Sonic SFC ödüllerini ve Avalanche P-Chain `potentialReward` alanını kapsar.

## B.4 Staking Hesabı

### B.4.1 Konsept
| Alan              | Anlamı                        |
| ----------------- | ----------------------------- |
| `liquid_quantity` | Cüzdandaki çekilebilir miktar |
| `staked_quantity` | Validator'da kilitli miktar   |
| `pending_rewards` | Henüz claim edilmemiş ödüller |

### B.4.2 Sonic SFC
- Validator sayısı: ~20 (sürekli değişiyor)
- `Semaphore(20)` ile paralel sorgu (rate limit korumalı)
- Hesap: `getStake(addr, validatorID)` + `pendingRewards(addr, validatorID)`

### B.4.3 Avalanche P-Chain
- REST API: `platform.getStake`
- `staked` ve `unlockedOutputs` ayrımı yapılır

### B.4.4 Avalanche C-Chain
EVM zinciri; staking C-Chain'de yok, sadece liquid balance.

## B.5 Portföy Toplam Değeri ve Ağırlık

### B.5.1 Snapshot Toplamı
```python
total_value_tl = sum(asset.total_value_tl for asset in all_assets)
```

### B.5.2 Ağırlık Yüzdesi
```python
weight_pct = (asset.total_value_tl / snapshot.total_value_tl) * Decimal("100")
weight_pct = weight_pct.quantize(Decimal("0.01"))
# Tüm weight_pct toplamı ≈ 100.00 (küsurat farkı kabul edilebilir)
```

### B.5.3 Breakdown (Varlık Türü Dağılımı)
```python
crypto_pct        = sum(weights for assets where asset_type == "crypto")
staked_crypto_pct = sum(weights for assets where asset_type == "staked_crypto")
fund_pct          = sum(weights for assets where asset_type == "fund")
pension_pct       = sum(weights for assets where asset_type == "pension")
cash_pct          = 100 - crypto - staked_crypto - fund - pension
```

## B.6 Haftalık/Aylık Değişim

### B.6.1 Snapshot Mantığı
APScheduler her **Pazar 23:00** (Europe/Istanbul) çalışır:
- Son snapshot = bu hafta
- 1 önceki = geçen hafta (WoW)
- 4 önceki = geçen ay (MoM, ~4 hafta)

### B.6.2 Hesaplama
```python
# aggregator.py::calculate_changes — snapshots[0] en güncel (DESC sıralı)
def calculate_changes(snapshots: list[PortfolioSnapshot]) -> PortfolioChanges:
    current = snapshots[0]
    wow_change_tl = wow_change_pct = mom_change_tl = mom_change_pct = Decimal(0)

    if len(snapshots) >= 2:                      # WoW: 1 önceki snapshot
        prev_week = snapshots[1]
        wow_change_tl = current.total_value_tl - prev_week.total_value_tl
        wow_change_pct = (wow_change_tl / prev_week.total_value_tl * 100) if prev_week.total_value_tl else Decimal(0)

    if len(snapshots) >= 5:                       # MoM: 4 önceki snapshot (~4 hafta)
        prev_month = snapshots[4]
        mom_change_tl = current.total_value_tl - prev_month.total_value_tl
        mom_change_pct = (mom_change_tl / prev_month.total_value_tl * 100) if prev_month.total_value_tl else Decimal(0)

    return PortfolioChanges(
        current_value_tl=current.total_value_tl,
        wow_change_tl=wow_change_tl,
        wow_change_pct=wow_change_pct.quantize(Decimal("0.01")),
        mom_change_tl=mom_change_tl,
        mom_change_pct=mom_change_pct.quantize(Decimal("0.01")),
        snapshot_date=current.snapshot_date,
    )
```

## B.7 TEFAS Fon Fiyatı

### B.7.1 API
```
POST https://www.tefas.gov.tr/api/DB/BindHistoryInfo
Body: fontip=YAT&bastarih=DD.MM.YYYY&bittarih=DD.MM.YYYY&fonkod=GO3
```

### B.7.2 Birim Fiyat Hesabı
```python
unit_price_tl = sonPortfoyDegeri / sonPayAdedi
```
- `sonPortfoyDegeri`: fonun toplam piyasa değeri (TL)
- `sonPayAdedi`: dolaşımdaki pay sayısı

### B.7.3 Hafta Sonu Sorunu
TEFAS hafta sonu yeni fiyat döndürmez → API son işgününü döner. Frontend'de "Son güncelleme: Cuma" gibi bilgi gösterilmeli (Faz 3).

## B.8 Hisse Fiyatı (Yahoo Finance)

### B.8.1 API
```
GET https://query1.finance.yahoo.com/v8/finance/chart/{ticker}
```

### B.8.2 Para Birimi Mapping
| Borsa | Suffix | Para Birimi | Dönüşüm |
|-------|--------|-------------|---------|
| BIST | `.IS` (THYAO.IS) | TRY | Direkt |
| ABD | (yok) | USD | × usd_tl |
| Londra | `.L` | GBp (pence) | ÷100 × gbp_usd × usd_tl |
| Frankfurt | `.DE` | EUR | × eur_tl |
| Tokyo | `.T` | JPY | × jpy_tl |

### B.8.3 Fallback Sembol Bilgisi
Yahoo `chart.result[0].meta.symbol` veya `meta.exchangeName` döner; bunlardan ticker doğrulaması yapılır.

## B.9 Precision Kuralları

```python
# Para tutarları
total_value_tl = ....quantize(Decimal("0.01"))    # 2 ondalık (kuruş)

# Birim fiyat
unit_price_tl  = ....quantize(Decimal("0.0001"))  # 4 ondalık (küçük değerler için)

# Yüzde
weight_pct     = ....quantize(Decimal("0.01"))    # 2 ondalık %

# Kripto miktarı (DB)
quantity = NUMERIC(20, 8)  # 8 ondalık (kripto için yeterli; satoshi precision)

# Hisse miktarı (DB)
quantity = NUMERIC(20, 8)  # 8 ondalık (kesirli pay desteği)
```

**KESINLIKLE FLOAT KULLANMA.** Decimal precision finansal sistemde yasal gereklilik.

## B.10 Bilinen Sorunlar

### ✅ Düzeltildi (2026-04-30)
1. **GBp dönüşümü** — `api/v1/stocks.py::convert_to_tl` artık GBP/USD kuru kullanıyor (`fetch_gbp_to_usd`). Test koruması: `test_stocks_currency.py` (7 test).

### ✅ Düzeltildi (2026-04-30, sürüm 3.3)
2. **USD/TRY fallback sabit** — `aggregator.py` TCMB primary + exchangerate-api fallback ile baştan yazıldı; 5 dk in-memory cache, kritik fail'de 503. Test koruması: `test_exchange_rates.py` (9 test) + `test_snapshot.py` (2 yeni test).

### ⚠️ Hâlâ Düzeltilecek
3. **Cache yok** — her istek dış API çağrısı, rate limit riski (Faz 2 — Redis)
4. **Hafta sonu TEFAS** — kullanıcıya bilgilendirme yok (Faz 2 — frontend)
5. **Kripto coin map'i hardcoded** — yeni coin desteği için kod değişikliği gerekiyor (Faz 3)
6. ~~Model adı `advisor.py`'de hardcoded~~ ✅ 2026-05-01 — `settings.claude_model`

---

## C. Eksik / Eklenecek (TODO)

### AI Tavsiye
- [x] Model adı config'den (advisor.py — 2026-05-01)
- [x] Hata yönetimi (timeout, rate limit) — AI-001, exception→HTTP mapping
- [x] Cache metrikleri DB'ye kayıt — AI-002 (`cache_read_tokens` / `cache_creation_tokens`)
- [ ] Cache hit oranı dashboard/alert (`GET /metrics/ai`) — backlog (ai-notes #2)
- [ ] Prompt versiyonlama (`investment_advice.prompt_version`) — backlog (ai-notes #4)
- [ ] Streaming yanıt (Faz 4)
- [x] Anthropic için açık rıza akışı — AI-005 (`anthropic_consent_at` → 403)
- [x] Kredi tüketimi — AI-007 (`credit_balance` / `credits_used` atomik düşüm)
- [ ] AI çıktısı sanitization (XSS riski — `rehype-sanitize`)

### Finansal Hesaplama
- [x] GBp → GBP/USD/TL dönüşümü düzeltme
- [x] TCMB kuru entegrasyonu (USD/TRY + GBP/USD fallback, 5 dk in-memory cache)
- [ ] Redis cache (TEFAS 1 saat, Yahoo 5dk — USD/TRY için TCMB cache yeterli)
- [ ] EUR, JPY, CHF gibi diğer kurların entegrasyonu (Faz 3)
- [ ] Kripto sembol → ticker mapping config'den (yeni coin için kod değişikliği gerekmesin)
- [ ] TEFAS hafta sonu uyarısı (frontend)
- [ ] Backtest desteği — geçmiş tarihte portföy değeri (Faz 4)
