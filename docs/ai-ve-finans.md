# AI Tavsiye Motoru ve Finansal Hesaplamalar

**Sahip ajanlar:** `ai-expert`, `finance-expert`
**İlgili:** [api-referansi.md](./api-referansi.md), [kredi-sistemi.md](./kredi-sistemi.md)

---

# Bölüm A — AI Tavsiye Motoru

## A.1 Mevcut Fonksiyonel Gereksinimler

| Bileşen | Durum |
|---------|-------|
| Anthropic SDK entegrasyonu (`AsyncAnthropic`) | ✅ Aktif |
| `claude-sonnet-4-6` model kullanımı | ✅ Aktif |
| System prompt + prompt caching (`cache_control: ephemeral`) | ✅ Aktif |
| Token sayımı `investment_advice` tablosuna kayıt | ✅ Aktif |
| Türkçe Markdown çıktı | ✅ Aktif |
| Risk profili + portföy dağılımı + staking pozisyonları prompt'a dahil | ✅ Aktif |
| Vade etiketi (`medium` / `long`) | ✅ Aktif |
| Kredi tüketimi | ❌ Eksik (Faz 3) |
| Endpoint aktif (`POST /advice/generate`) | ⚠️ Kodda var ama frontend kullanmıyor |

**Bu davranışlar regresyon kabul etmez.**

---

## A.2 Mimari

```
Frontend
  ↓ POST /api/v1/advice/generate { horizon: "medium" }
api/v1/advice.py
  ↓ kredi kontrolü (Faz 3)
  ↓ son snapshot'ı çek
services/advisor.py: AdvisorService.generate(user, snapshot, horizon)
  ↓ calculate_breakdown(snapshot) — yüzde hesabı
  ↓ user prompt formatla
  ↓ AsyncAnthropic.messages.create(...)
    ↓ system prompt (cached, ephemeral)
    ↓ user prompt (per-call)
  ↓ InvestmentAdvice modelini oluştur (token sayımı dahil)
  ↓ DB'ye kaydet
  ↓ kredi düş (Faz 3)
  ↓ JSON response
```

## A.3 Model Seçimi

| Görev | Model | Gerekçe |
|-------|-------|---------|
| Standart tavsiye, vade analizi | `claude-sonnet-4-6` | Hız + kalite dengesi, maliyet uygun |
| Karmaşık portföy (20+ varlık) | `claude-opus-4-7` | Çok varlık + staking + döviz; derin akıl yürütme |
| Hızlı sınıflandırma, etiketleme | `claude-haiku-4-5-20251001` | Düşük maliyet, basit görev |

**Mevcut sorun:** Model adı `advisor.py`'de hardcoded (`"claude-sonnet-4-6"`). Config'e taşınmalı:
```python
# config.py — eklenecek
advice_model: str = "claude-sonnet-4-6"
advice_max_tokens: int = 1024
```

## A.4 Prompt Tasarımı

### A.4.1 System Prompt (Cache'li)
```
Deneyimli bir portföy danışmanısın.
Türk yatırımcısı için gerçekçi, uygulanabilir tavsiyeler üretiyorsun.
Yanıtını Türkçe, Markdown formatında ver: başlıklar ve madde listeleri kullan.
Tavsiyelerini net, somut ve pratik tut.
```
- ~80 token
- Her çağrıda aynı → `cache_control: ephemeral` (5 dk TTL)
- Tasarruf: input token'ın %95'i cache'den okunur

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
| Bileşen | Token |
|---------|-------|
| System prompt (cache hit) | ~5 (cache okuma) |
| User prompt | ~200 |
| Output (max) | 1024 |
| **Toplam (cache hit)** | ~1230 |
| **Toplam (cache miss)** | ~1305 |

## A.5 Eklenecek İyileştirmeler

### A.5.1 Hata Yönetimi (Yapılacak)
```python
try:
    message = await self._client.messages.create(...)
except anthropic.APITimeoutError:
    raise HTTPException(503, "AI servisi yanıt vermiyor, tekrar deneyin")
except anthropic.RateLimitError:
    raise HTTPException(429, "AI rate limit; lütfen bekleyin")
except anthropic.APIError as e:
    logger.error("Anthropic API hatası: %s", e)
    raise HTTPException(500, "AI servis hatası")
```

### A.5.2 Cache Hit Oranı İzleme
```python
return InvestmentAdvice(
    ...,
    prompt_tokens=message.usage.input_tokens,
    completion_tokens=message.usage.output_tokens,
    cache_read_tokens=message.usage.cache_read_input_tokens or 0,  # YENİ
)
```
Maliyet optimizasyonu için cache hit oranı dashboard'da izlenmeli.

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

### Açık Rıza (Yapılacak — Faz 3)
İlk tavsiye talebinde modal:
```
KFinans, AI tavsiyenizi üretebilmek için anonimleştirilmiş
portföy bilgilerinizi (yüzdeler, sembollar) Anthropic ABD'ye
göndermek zorundadır. Onaylıyor musunuz?
```
Onay zaman damgası `users.anthropic_consent_at` kolonuna kayıt.

---

# Bölüm B — Finansal Hesaplamalar

## B.1 Mevcut Fonksiyonel Gereksinimler

| Hesaplama | Durum |
|-----------|-------|
| USD/TRY kuru çekme (Binance USDTTRY) | ✅ Aktif |
| Spot fiyat çekme (Binance) | ✅ Aktif |
| Kripto pozisyonu TL değer hesabı | ✅ Aktif |
| Staking + pending rewards ayrımı | ✅ Aktif |
| TEFAS fon fiyatı (sonPortfoyDegeri/sonPayAdedi) | ✅ Aktif |
| Yahoo Finance hisse fiyatı (TRY/USD/GBp) | ✅ Aktif |
| WoW + MoM değişim hesabı | ✅ Aktif |
| Varlık türü dağılımı (breakdown) | ✅ Aktif |
| Ağırlık yüzdesi (`weight_pct`) | ✅ Aktif |

## B.2 Para Birimi Normalizasyonu

### B.2.1 Hedef Para Birimi: TL
Tüm sunum, kıyaslama ve snapshot **TL** üzerinden yapılır. USD/EUR/GBP fiyatları işlem anında dönüştürülür.

### B.2.2 USD/TRY Kuru
```python
# aggregator.py
async def fetch_usd_to_tl() -> Decimal:
    # Birinci öncelik: Binance USDTTRY spot
    # Fallback: Sabit kur (33.50) — production'da kabul edilemez
```
**TODO:** Fallback'i TCMB API'sine bağla:
```
https://www.tcmb.gov.tr/kurlar/today.xml
```
Üç katmanlı strateji: Binance → TCMB → cached last-good (max 24 saat).

### B.2.3 GBp (Pence) Dönüşümü
**Mevcut hata:**
```python
price_tl = (price_gbp / 100 * usd_tl)  # ❌ YANLIŞ
```
GBp → GBP → USD → TL dönüşümü için **GBP/USD kuru** gerekli. Şu an 1 GBP = 1 USD varsayılıyor.

**Doğru hesap:**
```python
gbp_usd = await fetch_gbp_usd()   # ~1.27 (2026 nisan)
price_tl = (price_gbp / 100) * gbp_usd * usd_tl
```

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
| Alan | Anlamı |
|------|--------|
| `liquid_quantity` | Cüzdandaki çekilebilir miktar |
| `staked_quantity` | Validator'da kilitli miktar |
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
def calculate_changes(snapshots: list[PortfolioSnapshot]):
    current = snapshots[0]
    last_week = snapshots[1] if len(snapshots) > 1 else None
    month_ago = snapshots[4] if len(snapshots) > 4 else None

    wow_change_tl  = current.total - last_week.total if last_week else Decimal(0)
    wow_change_pct = (wow_change_tl / last_week.total * 100) if last_week else Decimal(0)

    mom_change_tl  = current.total - month_ago.total if month_ago else Decimal(0)
    mom_change_pct = (mom_change_tl / month_ago.total * 100) if month_ago else Decimal(0)

    return PortfolioChanges(
        current_value_tl=current.total,
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

### ⚠️ Hâlâ Düzeltilecek
2. **USD/TRY fallback sabit** — TCMB entegrasyonu yapılmalı (Faz 2)
3. **Cache yok** — her istek dış API çağrısı, rate limit riski (Faz 2 — Redis)
4. **Hafta sonu TEFAS** — kullanıcıya bilgilendirme yok (Faz 2 — frontend)
5. **Kripto coin map'i hardcoded** — yeni coin desteği için kod değişikliği gerekiyor (Faz 3)
6. **Model adı `advisor.py`'de hardcoded** — `claude-sonnet-4-6` config'e taşınmalı (Faz 2)

---

## C. Eksik / Eklenecek (TODO)

### AI Tavsiye
- [ ] Model adı config'den (advisor.py hardcoded)
- [ ] Hata yönetimi (timeout, rate limit)
- [ ] Cache hit oranı izleme
- [ ] Prompt versiyonlama
- [ ] Streaming yanıt (Faz 4)
- [ ] Anthropic için açık rıza akışı (Faz 3)
- [ ] AI çıktısı sanitization (XSS riski — `rehype-sanitize`)

### Finansal Hesaplama
- [ ] GBp → GBP/USD/TL dönüşümü düzeltme
- [ ] TCMB kuru entegrasyonu (USD/TRY fallback)
- [ ] Redis cache (USD/TRY 60sn, TEFAS 1 saat, Yahoo 5dk)
- [ ] EUR, JPY, CHF gibi diğer kurların entegrasyonu (Faz 3)
- [ ] Kripto sembol → ticker mapping config'den (yeni coin için kod değişikliği gerekmesin)
- [ ] TEFAS hafta sonu uyarısı (frontend)
- [ ] Backtest desteği — geçmiş tarihte portföy değeri (Faz 4)
