# API Referansı

**Sahip ajan:** `backend-expert`
**Base URL:** `http://localhost:8000` (dev) | `https://api.kfinans.app` (prod)
**API Prefix:** `/api/v1`

---

## 1. Genel Kurallar

### 1.1 Kimlik Doğrulama
Auth gerektiren endpoint'ler `Authorization: Bearer {access_token}` header'ı bekler. Token süresi dolduğunda 401 döner; istemci `/auth/refresh` ile yeniler.

### 1.2 Hata Formatı
```json
{ "detail": "İnsan okunabilir Türkçe açıklama" }
```

> **422 Validation Logger:** `main.py` `RequestValidationError` exception handler 422 hata detayını (`exc.errors()`) sunucu log'una yazar — frontend response formatı değişmez. Geliştirme sırasında schema doğrulama hatasının hangi alandan kaynaklandığı log'dan görülebilir.

### 1.3 Standart HTTP Kodları
| Kod | Anlamı               | Örnek                                   |
| --- | -------------------- | --------------------------------------- |
| 200 | OK                   | Veri döndü                              |
| 201 | Created              | Yeni kayıt eklendi (register)           |
| 401 | Unauthorized         | Token yok/geçersiz                      |
| 404 | Not Found            | Snapshot yok                            |
| 409 | Conflict             | E-posta zaten kayıtlı                   |
| 422 | Unprocessable Entity | Geçersiz girdi (Pydantic validation)    |
| 429 | Too Many Requests    | slowapi rate limit aşıldı               |
| 402 | Payment Required     | Yetersiz kredi (Faz 3)                  |
| 500 | Internal Error       | Beklenmeyen hata (loglanır)             |
| 502 | Bad Gateway          | Snapshot — tüm kaynaklar fail           |
| 503 | Service Unavailable  | Snapshot — kritik USD/TL kuru alınamadı |

### 1.4 Rate Limiting (slowapi)

> **SEC-003 (FAZ H):** `settings.redis_url` set ise distributed Redis backend
> (multi-replica güvenli); yoksa MemoryStorage. Production K8s şu an
> `replicas: 1` (Redis enable olunca artırılabilir).

| Endpoint                                  | Limit       | Sebep |
| ----------------------------------------- | ----------- | ----- |
| `POST /auth/login`                        | 10/dakika   | Brute-force koruması |
| `POST /auth/register`                     | 5/dakika    | Spam hesap engeli |
| `POST /auth/refresh`                      | 30/dakika   | Token rotation |
| `POST /auth/forgot-password`              | 3/dakika    | Token spam engeli (SEC-001) |
| `POST /auth/reset-password`               | 5/dakika    | Token brute-force engeli (SEC-001) |
| `GET /auth/verify-email`                  | 20/dakika   | E-posta tıklama hızı |
| `POST /auth/resend-verification`          | 3/dakika    | E-posta abuse engeli |
| `POST /advice/generate`                   | 5/saat      | Anthropic API maliyet (AI-007) |
| `POST /portfolio/snapshot`                | 6/saat      | 14 dış API tetikler (SEC-005) |
| `POST /portfolio/snapshot/preview`        | 6/saat      | Aynı (SEC-005) |
| `POST /portfolio/stocks/preview`          | 30/dakika   | Yahoo Finance rate limit (SEC-005) |
| `POST /portfolio/tefas/preview`           | 30/dakika   | TEFAS API hızı (SEC-005) |
| `POST /user/email/request`                | 3/dakika    | Token guess + spam (SEC-005) |
| `GET  /user/data-export`                  | 5/saat      | Büyük JSON DoS koruma (SEC-005) |
| `POST /user/anthropic-consent`            | 10/saat     | KVKK abuse engeli (SEC-005) |
| `DELETE /user/anthropic-consent`          | 10/saat     | Aynı (SEC-005) |
| Diğer                                     | Limitsiz    | Read-only veya hafif endpoint'ler |

---

## 2. Sistem Endpoint'leri

### `GET /health`
Health check. Auth gerektirmez. Kubernetes liveness/readiness için.
```json
200 OK
{ "status": "ok", "version": "0.1.0" }
```

---

## 3. Auth (`/api/v1/auth`)

### `POST /auth/register`
Yeni kullanıcı kaydı. Rate limit: 5/dk. Kayıt sonrası **doğrulama maili** otomatik tetiklenir (Resend SDK), `email_verified=False` olur ve `verify_token` üretilir (24 saat ömürlü).
```json
// Request — RegisterRequest
{
  "email":        "user@example.com",
  "password":     "12345678",
  "risk_profile": "balanced"        // 'conservative'|'balanced'|'aggressive' (opsiyonel)
}

// 201 Created
{ "id": "uuid", "email": "user@example.com", "created_at": "2026-04-29T..." }

// 409 Conflict
{ "detail": "Bu e-posta zaten kayıtlı" }
```

> Mail gönderimi başarısız olsa bile kullanıcı oluşturulur — kullanıcı `POST /auth/resend-verification` ile yeniden talep edebilir.

### `POST /auth/login`
Giriş. Rate limit: 10/dk. **E-posta doğrulanmamışsa hard block (403).**
```json
// Request
{ "email": "user@example.com", "password": "12345678" }

// 200 OK
{
  "access_token":  "eyJ...",  // JWT, 480 dk
  "refresh_token": "eyJ...",  // JWT, 7 gün
  "token_type":    "bearer"
}

// 401 Unauthorized
{ "detail": "E-posta veya şifre hatalı" }

// 403 Forbidden — email doğrulanmamış (hard block)
{ "detail": "E-posta adresiniz henüz doğrulanmadı. Lütfen e-postanızı kontrol edin veya yeni doğrulama linki isteyin." }
```

### `POST /auth/refresh`
Yeni access + refresh token üretir. **Refresh token rotation aktif (FAZ C4):** Her başarılı refresh çağrısında **eski refresh token'ın `jti`'si `revoked_tokens` blacklist'ine atılır** ve yeni refresh token üretilir. Sızan refresh token ikinci kez kullanılırsa 401 döner. Rate limit: 30/dk.

```json
// Request
{ "refresh_token": "eyJ..." }

// 200 OK — yeni access + yeni refresh
{ "access_token": "eyJNEW...", "refresh_token": "eyJNEW..." }

// 401 Unauthorized — eski refresh ikinci kez kullanildı veya logout ile iptal
{ "detail": "Token iptal edilmiş" }
```

**Güvenlik notu:** Saldırgan ele geçirdiği refresh token'ı kullansa bile, gerçek kullanıcı bir sonraki refresh'inde saldırganın token'ını invalidate eder (rotation). Tüm refresh token'lar `revoked_tokens` cleanup cron (FAZ C5) ile expires_at sonrası DB'den silinir.

### `POST /auth/logout`
Mevcut access token'ı (header'dan) ve opsiyonel olarak body'deki refresh token'ı `revoked_tokens` tablosuna ekler. Auth gerektirir (token'sız 401). **İdempotent** — aynı token tekrar logout edilirse `get_current_user` zaten 401 döner. Bilgi sızdırmamak için bozuk/geçersiz refresh token sessizce yutulur (access token yine blacklist'e alınır).
```json
// Request — LogoutRequest (body opsiyonel)
{ "refresh_token": "eyJ..." }   // veya {} / null

// 200 OK
{ "message": "Çıkış yapıldı" }

// 401 Unauthorized — auth header yok / geçersiz / blacklist'te
{ "detail": "..." }
```

> Frontend şu an `localStorage`'da yalnızca access token tutuyor; bu nedenle pratikte sadece access token blacklist'e alınıyor. Refresh akışı eklendiğinde refresh token da gönderilmeli.

### `GET /auth/verify-email?token=...`
E-posta doğrulama linki. Token DB'deki `users.verify_token` ile eşleşmeli ve `verify_token_expires_at` geçmemiş olmalı. Başarıda `email_verified=True` set edilir, token sıfırlanır.
```json
// 200 OK
{ "message": "E-posta adresiniz doğrulandı." }

// 400 Bad Request
{ "detail": "Geçersiz veya süresi dolmuş doğrulama linki." }
```

### `POST /auth/resend-verification`
Doğrulama linkini yeniden gönderir. **Bilgi sızdırmamak için her zaman 202 döner** (e-posta kayıtlı mı, doğrulanmış mı bilgisi response'tan çıkarılamaz).
```json
// Request
{ "email": "user@example.com" }

// 202 Accepted (her durumda)
{ "message": "E-posta adresiniz kayıtlıysa doğrulama linki gönderildi." }
```

### `POST /auth/forgot-password` / `POST /auth/reset-password` (Faz 2 — sonraki adım)
Şifre sıfırlama akışı.

---

## 4. Portföy Snapshot (`/api/v1/portfolio`)

### `GET /portfolio`
Son haftalık snapshot.
```json
200 OK
{
  "id": "uuid",
  "snapshot_date": "2026-04-26",
  "total_value_tl": "150000.00",
  "asset_positions": [...]
}
404: { "detail": "Henüz portföy verisi yok" }
```

### `GET /portfolio/history?limit=12`
Son N snapshot (en yeniden eskiye sıralı). Frontend `/dashboard/history` line chart'ı bu endpoint'i kullanır.
```json
200 OK
[
  {
    "id":              "uuid",
    "snapshot_date":   "2026-04-26",
    "total_value_tl":  "150000.00",
    "asset_positions": [
      {
        "asset_type":     "crypto",   // 'crypto'|'fund'|'stock'|'pension'|'cash'
        "provider":       "binance",
        "symbol":         "BTC",
        "total_value_tl": "...",
        ...
      }
    ]
  }
]
```
> `limit` opsiyonel (varsayılan 12). Pagination yok — Faz 2 cursor-based pagination TODO'su.

### `GET /portfolio/changes`
WoW (haftalık) ve MoM (aylık) değişim.
```json
{
  "current_value_tl": "150000.00",
  "wow_change_tl":    "5000.00",
  "wow_change_pct":   "3.45",
  "mom_change_tl":    "12000.00",
  "mom_change_pct":   "8.70",
  "snapshot_date":    "2026-04-26"
}
```

### `GET /portfolio/breakdown`
Varlık türü dağılımı.
```json
{
  "crypto_pct":         "35.50",
  "staked_crypto_pct":  "10.00",
  "fund_pct":           "40.00",
  "pension_pct":        "10.00",
  "cash_pct":            "4.50",
  "top_assets": [...]
}
```

### `POST /portfolio/snapshot/preview`
Snapshot ön kontrolü — gather yapar, issues + toplam döndürür ama **DB'ye yazmaz** (sorunlar varsa kullanıcıya popup gösterip onay almak için).
```json
200 OK
{
  "total_value_tl": "8164975.87",
  "asset_count": 163,
  "issues": [
    { "source": "wallet", "chain": "ethereum", "address": "0x6d6be9eBE75De3…", "code": "fetch_failed", "msg": "..." }
  ],
  "usd_try_rate": "44.969200",
  "saved": false
}
```
- `saved=false`: issues vardı, DB'ye yazılmadı; frontend kullanıcıya popup gösterir, onay sonrası `POST /portfolio/snapshot?force=true` çağrılır.
- `saved=true`: issues yoktu, snapshot zaten kaydedildi.

### `POST /portfolio/snapshot?force=false|true`
`force=true` query parametresi: kullanıcı uyarıları onayladıktan sonra bu endpoint çağrılır. issues olsa bile `health_issues` JSONB kolonuna kaydedilip snapshot saklanır.

### `GET /portfolio/usd-rate`
Anlık USD/TRY kuru (TCMB → Yahoo Finance fallback). Frontend `TLValue` bileşeni USD karşılığı göstermek için kullanır. 5 dk in-memory cache (aggregator katmanı).
```json
200 OK
{ "usd_try": "33.45" }
```

### `GET /portfolio/staking`
Tüm staking pozisyonları (Sonic, Avalanche).
```json
[{
  "provider":         "sonic",
  "symbol":           "S",
  "name":             "Sonic",
  "staked_quantity":  "1500.0",
  "pending_rewards":  "12.5",
  "staked_value_tl":  "...",
  "rewards_value_tl": "..."
}]
```

### `GET /portfolio/crypto`
**Anlık** kripto pozisyonlar (DB'den değil, exchange'den çeker).
```json
{
  "positions": [{
    "provider":         "binance",
    "symbol":           "BTC",
    "liquid_quantity":  "0.05",
    "staked_quantity":  "0",
    "unit_price_usd":   "95000.00",
    "unit_price_tl":    "3325000.00",
    "total_value_tl":   "166250.00"
  }],
  "errors": { "icrypex": "Bağlantı zaman aşımı" }
}
```

### `POST /portfolio/snapshot`
Manuel snapshot tetikleyici. Tüm kaynaklardan (Binance, BinanceTR, iCrypex, Sonic, Avalanche P/C, Ethereum, TEFAS, hisse) paralel veri çeker, TL'ye normalize eder, `portfolio_snapshots` + `asset_positions` kayıtlarını yazar. **İdempotent** — aynı gün içinde tekrar çalıştırılırsa eski snapshot silinip yenisi yazılır.

```json
// 200 OK
{
  "id":             "uuid",
  "snapshot_date":  "2026-04-30",
  "total_value_tl": "150000.00",
  "asset_positions": [...]
}

// 502 Bad Gateway — hiçbir kaynaktan veri alınamadı
{ "detail": "Snapshot hesaplanamadı: tüm kaynaklar başarısız" }

// 503 Service Unavailable — kritik USD/TL kuru alınamadı (TCMB + exchangerate-api ikisi de fail)
{ "detail": "Snapshot alinamadi: ..." }
```

> Hata izolasyonu: bir kaynak başarısız olursa diğerleri devam eder, başarısız kaynak loglanır.
> Döviz kuru: USD/TL kritik — TCMB primary, exchangerate-api fallback; ikisi de fail ise snapshot iptal (503). GBP/USD opsiyonel — fail ise UK hisseleri 0 değerle devam eder (201).
> **Tarih (timezone):** `snapshot_date` `Europe/Istanbul` saatine göre belirlenir. Backend Docker container UTC'de çalışsa bile `datetime.now(ZoneInfo("Europe/Istanbul")).date()` kullanıldığı için Türkiye gece yarısı sonrası (00:00–03:00) alınan snapshot'lar doğru güne yazılır.

### `DELETE /portfolio/snapshot/{snapshot_date}`
Belirtilen tarihteki snapshot'ı siler. Yanlış kaydedilmiş snapshot'ları (timezone bug, hatalı manuel tetikleme vb.) temizlemek için kullanılır. Cascade ile `asset_positions` kayıtları da otomatik silinir.

| Path param      | Tür  | Açıklama                                  |
| --------------- | ---- | ----------------------------------------- |
| `snapshot_date` | date | ISO format (`YYYY-MM-DD`, örn. `2026-05-04`) |

```
DELETE /api/v1/portfolio/snapshot/2026-05-04
Authorization: Bearer eyJ...

204 No Content

404: { "detail": "Snapshot bulunamadı" }
```

> **IDOR koruması:** Sorgu `current_user.id` ile filtrelenir; başka kullanıcının snapshot'ı silinemez (yoksa 404 döner — bilgi sızdırma yok).
> Frontend `/dashboard/history` sayfası altındaki "Snapshotlar" listesinde her satırın yanında "Sil" butonu vardır; tıklamada onay popup'ı çıkar (geri alınamaz uyarılı).

### `GET /portfolio/wallets`
**Anlık** blockchain pozisyonları (10 zincir: Bitcoin, Ethereum, Sonic, Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin).
```json
{
  "positions": [{
    "wallet_id":       "uuid",
    "chain":           "sonic",
    "address":         "0x...",
    "label":           "Ana cüzdan",
    "symbol":          "S",
    "liquid_quantity": "100.0",
    "staked_quantity": "1500.0",
    "pending_rewards": "12.5",
    "unit_price_usd":  "0.45",
    "unit_price_tl":   "15.75",
    "total_value_tl":  "25393.75"
  }],
  "errors": {}
}
```

> Aynı response'ta zincire göre çeşitli `symbol` değerleri görülebilir: native token (`BTC`, `ETH`, `S`, `AVAX`, `SOL`, `ADA`, `DOT`, `ALGO`, `LTC`) + ERC-20 token'lar (Ethplorer dinamik discovery: `LINK`, `USDT`, `USDC` vb.) + curated AVAX list (`sAVAX`, `USDT.e`, `USDC.e`). Spot fiyatlar `aggregator.fetch_spot_prices()` 12 sembol için çekilir (`S`, `AVAX`, `ETH`, `BTC`, `SOL`, `ADA`, `DOT`, `ALGO`, `LTC`, `LINK`, `USDT`, `USDC`).
> Solana için `staked_quantity` Stake program (`getProgramAccounts`) sonucuyla doldurulur.
> Bitcoin için 10 dk in-memory cache + single-flight pattern (paralel cache miss'lerde tek tarama paylaşılır).
> **`total_value_tl` formülü:** `(liquid_quantity + staked_quantity + pending_rewards) * unit_price_tl`. `pending_rewards` (Sonic SFC validator rewards, Avalanche P-Chain pending rewards) her zaman dahil edilir; snapshot servisi ile tutarlıdır.

---

## 5. TEFAS (`/api/v1/portfolio/tefas`)

### `GET /portfolio/tefas/holdings`
Kayıtlı holding listesi.
```json
[{
  "code":         "GO3",
  "quantity":     1500.5,
  "name":         "Garanti Portföy 3",
  "avg_cost_tl":  1.10,        // Opsiyonel, TRY/adet (Faz 3)
  "distributor": "Ziraat"      // Opsiyonel, aracı kurum (Faz 3)
}]
```

### `PUT /portfolio/tefas/holdings`
Tüm holdinglari değiştir (replace-all). Body: holding listesi (avg_cost_tl + distributor opsiyonel).

### `POST /portfolio/tefas/preview`
TEFAS'tan **anlık fiyat** çek, kaydetme. Avg cost girilmişse kâr/zarar hesaplanır.
```json
// Request: holding listesi
// Response
[{
  "code":           "GO3",
  "name":           "Garanti Portföy 3",
  "quantity":       "1500.5",
  "unit_price_tl":  "1.2345",
  "total_value_tl": "1852.42",
  "avg_cost_tl":    "1.10",       // Opsiyonel
  "cost_basis_tl":  "1650.55",    // qty * avg_cost
  "gain_loss_tl":   "201.87",     // total - cost_basis
  "gain_loss_pct":  12.23,        // (gain_loss / cost_basis) * 100
  "distributor":    "Ziraat"
}]
422: { "detail": "Geçersiz fon kodu: XYZ" }
```

### `GET /portfolio/tefas/export`
Tüm holdinglari xlsx olarak indir (canlı fiyat + Ort. Maliyet + Kâr/Zarar + Kurum kolonları dahil).

### `POST /portfolio/tefas/import`
xlsx yükle, mevcut holdinglari **siler**, yenilerini ekler.
```
multipart/form-data: file=tefas.xlsx
422: "Sadece .xlsx dosyası kabul edilir" | "Geçerli holding bulunamadı"
```

### `POST /portfolio/tefas/import-mkk` — MKK e-Yatırımcı Excel Import (Faz 3)
MKK e-Yatırımcı "Tüm Kıymetler" raporundan TEFAS fonlarını içe aktarır.

**Filtre:** `Kıymet Sınıfı = 'Fon'` (case-insensitive).
**Mapping:** `Üye` → `distributor`, `Menkul Kıymet Kodu` → `code`, `Adet` → `quantity`, `Fiyat (TL)` → `avg_cost_tl`, `Kıymet Adı` → `name`.

```
multipart/form-data: file=hesap-portfoy-bakiyesi.xls
200 OK — kaydedilen liste (replace-all)
422: "Sadece .xls veya .xlsx dosyası kabul edilir"
422: "MKK Excel dosyası okunamadı (.xls binary formatında olmalı)"
422: "MKK formatı tanınmadı: 'Üye' başlık satırı bulunamadı"
422: "Dosyada 'Fon' kıymet sınıfında geçerli kayıt bulunamadı"
```

> Import sonrası `compute_and_save_snapshot()` best-effort tetiklenir (fail olsa bile import korunur).

---

## 6. Hisse Senedi (`/api/v1/portfolio/stocks`)

API yapısı TEFAS ile aynı:
- `GET    /portfolio/stocks/holdings` — listele
- `PUT    /portfolio/stocks/holdings` — replace-all
- `POST   /portfolio/stocks/preview` — Yahoo Finance anlık fiyat (kâr/zarar dahil)
- `GET    /portfolio/stocks/export` — xlsx indir (Ort. Maliyet + Kâr/Zarar + Kurum kolonları dahil)
- `POST   /portfolio/stocks/import` — xlsx yükle
- `POST   /portfolio/stocks/import-mkk` — **MKK e-Yatırımcı .xls** dosyası direkt yükle (Faz 3)

```json
// Holding (Faz 3: avg_cost_tl + distributor opsiyonel)
{
  "ticker":      "THYAO.IS",
  "quantity":    100,
  "name":        "Türk Hava Yolları",
  "avg_cost_tl": 285.50,        // Opsiyonel, TRY/adet (0 → None)
  "distributor": "İş Yatırım"   // Opsiyonel, aracı kurum (max 50)
}

// Preview response
{
  "ticker":              "AAPL",
  "name":                "Apple Inc.",
  "quantity":            "10",
  "currency":            "USD",
  "unit_price_original": "180.50",
  "unit_price_tl":       "6318.00",
  "total_value_tl":      "63180.00",
  "avg_cost_tl":         "5500.00",      // Opsiyonel
  "cost_basis_tl":       "55000.00",     // qty * avg_cost
  "gain_loss_tl":         "8180.00",     // total - cost_basis
  "gain_loss_pct":        14.87,         // (gain_loss / cost_basis) * 100
  "distributor":         "İş Yatırım"
}
```

> Ticker formatı: BIST = `THYAO.IS`, ABD = `AAPL`, UK = `BP.L` (GBp döner, ÷100 → GBP).
> `avg_cost_tl=0` veya negatif girilince schema validator `None`'a çevirir (maliyet bilinmiyor).
> `distributor` aynı ticker'ı farklı kurumlardan ayrı satır olarak izlemek için kullanılır.

### `POST /portfolio/stocks/import-mkk` — MKK e-Yatırımcı Excel Import (Faz 3)
MKK e-Yatırımcı "Tüm Kıymetler" raporu (`.xls` binary) → hisse senedi pozisyonları.

**Filtre:** `Kıymet Sınıfı = 'HS'` AND `Ek Tanım = 'A'` (aktif tradeable pozisyonlar).
**Mapping:** `Üye` → `distributor`, `Menkul Kıymet Kodu` → `ticker` (otomatik `.IS` suffix), `Adet` → `quantity`, `Fiyat (TL)` → `avg_cost_tl`, `Kıymet Adı` → `name`.

```
multipart/form-data: file=hesap-portfoy-bakiyesi.xls
200 OK — kaydedilen liste (replace-all)
422: "Sadece .xls veya .xlsx dosyası kabul edilir"
422: "MKK Excel dosyası okunamadı (.xls binary formatında olmalı)"
422: "MKK formatı tanınmadı: 'Üye' başlık satırı bulunamadı"
422: "Dosyada 'HS' kıymet sınıfında ve 'A' ek tanımında geçerli kayıt bulunamadı"
```

> Import sonrası `compute_and_save_snapshot()` best-effort tetiklenir (fail olsa bile import korunur).

---

## 6.1 BES — Bireysel Emeklilik (`/api/v1/portfolio/bes`)

Manuel giriş modülü. Kullanıcı plan adı + toplam ₺ değer girer; otomatik scraping yok (Faz 2 sonrası planlanıyor).

### `GET /portfolio/bes/holdings`
Kayıtlı BES plan listesi.
```json
[{ "plan_name": "AgeSA Klasik", "total_value_tl": "45000.00" }]
```

### `PUT /portfolio/bes/holdings`
Tüm holding'leri değiştir (replace-all). **İdempotent** — eski kayıtlar silinir, yenileri yazılır.
```json
// Request
[{ "plan_name": "AgeSA Klasik", "total_value_tl": "45000.00" }]

// 200 OK — kaydedilen liste
[{ "plan_name": "AgeSA Klasik", "total_value_tl": "45000.00" }]

// 422 Unprocessable Entity
{ "detail": "plan_name boş olamaz" }       // min_length=1
{ "detail": "total_value_tl >= 0 olmalı" } // ge=0
```

### `GET /portfolio/bes/export`
`bes-holdingleri.xlsx` dosyasını indirir (plan adı + toplam ₺ kolonları).

### `POST /portfolio/bes/import`
xlsx yükle, mevcut BES kayıtlarını **siler**, yenilerini ekler.
```
multipart/form-data: file=bes.xlsx
422: "Sadece .xlsx dosyası kabul edilir" | "Geçerli BES kaydı bulunamadı"
```

> Snapshot entegrasyonu: `services/snapshot.py::_gather_bes_assets()` BES kayıtlarını `asset_type="pension"`, `provider="bes"`, `source_type="bes"`, `liquid_quantity=1`, `unit_price_tl=total_value_tl` ile `AssetData` listesine çevirir.

---

## 7. Exchange Entegrasyonları (`/api/v1/integrations`)

### `GET /integrations`
Aktif entegrasyonları listele (key'ler **dönmez**, sadece metadata).
```json
[{
  "id":             "uuid",
  "provider":       "binance",
  "is_active":      true,
  "last_synced_at": "2026-04-29T...",
  "has_extra":      false
}]
```

### `POST /integrations`
Yeni exchange API key ekle. Body Fernet ile şifrelenir, plaintext DB'ye yazılmaz.
```json
{
  "provider":    "binance",
  "api_key":     "...",
  "api_secret":  "...",
  "extra_token": "..."   // Opsiyonel — Binance TR cid cookie
}
```

### `DELETE /integrations/{provider}`
Entegrasyonu pasifleştirir (`is_active = false`); kalıcı silmek için `?hard=true`.

---

## 8. Blockchain Cüzdanları (`/api/v1/wallets`)

### `GET /wallets`
Tüm aktif cüzdan adresleri.

### `POST /wallets`
```json
{
  "chain":   "sonic",       // 10 zincir: 'bitcoin'|'ethereum'|'sonic'|'avalanche_c'|'avalanche_p'|'solana'|'cardano'|'algorand'|'polkadot'|'litecoin'
  "address": "...",         // Aşağıdaki tabloda zincir bazlı format
  "label":   "Ana cüzdan"
}
409: { "detail": "Bu cüzdan zaten kayıtlı" }
422: { "detail": "..." }   // Geçersiz chain veya format — main.py validation handler log'a yazar
```

**Chain başına adres formatı:**

| Chain | Format | Örnek |
|-------|--------|-------|
| `bitcoin` | `bc1q...` (Bech32) / `1...` / `3...` / `xpub...` / `zpub...` (HD) | `bc1q...` |
| `ethereum` | EVM `0x...` (40 hex) | `0x742d35Cc...` |
| `sonic` | EVM `0x...` (40 hex) | `0x...` |
| `avalanche_c` | EVM `0x...` (40 hex) | `0x...` |
| `avalanche_p` | `P-avax1...` (Bech32) | `P-avax1...` |
| `solana` | Base58 (32-44 karakter) | `So11111111111111111111111111111111111111112` |
| `cardano` | `addr1...` (Bech32) | `addr1q...` |
| `algorand` | Base32 (58 karakter) | `XYZ...` |
| `polkadot` | SS58 (`1...`) | `1FRMM8PE...` |
| `litecoin` | `ltc1...` / `L...` / `M...` | `ltc1q...` |

### `DELETE /wallets/{id}`

### `GET /wallets/export` / `POST /wallets/import`
xlsx indir/yükle (TEFAS pattern'i ile aynı).

---

## 8.1 Manuel Kripto (`/api/v1/manual-crypto`)

API erişimi olmayan borsalardaki (BinanceTR, iCrypex, BTCTurk, Paribu, Bybit, KuCoin, Bitget, Other) bakiyelerin manuel kayıt yoluyla portföye dahil edilmesini sağlar. Tüm endpoint'ler auth gerektirir; başka kullanıcının kaydına erişim 404 döner (IDOR koruması). Snapshot entegrasyonu `_gather_manual_crypto_assets()` ile sağlanır — `asset_type="crypto"`, `provider="manual:{exchange}"` (örn. `manual:icrypex`).

### `GET /manual-crypto`
Kullanıcının manuel kripto kayıtlarını listeler; her kayıt anlık fiyatla zenginleştirilir. Sembol Binance USDT spot listesinde yoksa `unknown_symbols` döner ve TL değer 0 olur.

```json
200 OK — ManualCryptoSummaryOut
{
  "positions": [{
    "id":             1,
    "exchange":       "icrypex",
    "label":          "iCrypex Ana",
    "symbol":         "BTC",
    "quantity":       "0.01250000",
    "avg_cost_tl":    "1850000.000000",
    "notes":          "2026 Mart alımı",
    "unit_price_usd": "95000.00",
    "unit_price_tl":  "4271574.00",
    "total_value_tl": "53394.68",
    "cost_basis_tl":  "23125.00",
    "gain_loss_tl":   "30269.68",
    "gain_loss_pct":   130.89,
    "created_at":     "2026-05-04T19:02:00Z",
    "updated_at":     "2026-05-05T08:40:00Z"
  }],
  "total_value_tl":  "53394.68",
  "unknown_symbols": []
}
```

> Bilinmeyen sembol akışı: `["FOOCOIN"]` → frontend banner uyarı; ilgili pozisyon `total_value_tl=0` olarak listelenir, toplama dahil edilmez.

### `POST /manual-crypto`
Yeni kayıt ekler.

```json
// Request — ManualCryptoCreate
{
  "exchange":    "icrypex",       // 'binancetr'|'icrypex'|'btcturk'|'paribu'|'bybit'|'kucoin'|'bitget'|'other'
  "label":       "iCrypex Ana",   // Opsiyonel, max 100
  "symbol":      "btc",           // Otomatik upper-case ('BTC')
  "quantity":    "0.0125",        // Decimal, gt=0 (28,12)
  "avg_cost_tl": "1850000.00",    // Opsiyonel TRY/adet (≤0 → None)
  "notes":       "2026 Mart alımı" // Opsiyonel serbest not
}

// 201 Created — ManualCryptoOut
{ "id": 1, "exchange": "icrypex", "symbol": "BTC", ... }

422: { "detail": "ensure this value is greater than 0" }   // quantity ≤ 0
422: { "detail": "Geçersiz borsa: ..." }                    // exchange enum dışı
```

### `PUT /manual-crypto/{id}`
Partial update — `ManualCryptoUpdate` tüm alanları opsiyonel; gönderilen alanlar değişir, diğerleri korunur. `updated_at` otomatik yenilenir.

```json
// Request — sadece quantity
{ "quantity": "0.0150" }

// 200 OK — güncellenmiş ManualCryptoOut

404: { "detail": "Manuel kripto kaydı bulunamadı" }   // başka kullanıcı veya yok (IDOR koruması)
422: { "detail": "..." }                              // schema doğrulama
```

### `DELETE /manual-crypto/{id}`
```
DELETE /api/v1/manual-crypto/1
Authorization: Bearer eyJ...

204 No Content
404: { "detail": "Manuel kripto kaydı bulunamadı" }   // IDOR korumalı
```

### `GET /manual-crypto/export`
Tüm manuel kripto kayıtlarını `manuel-kripto.xlsx` olarak indir (sütunlar: borsa, etiket, sembol, miktar, ortalama maliyet TL, notlar, oluşturulma).

```
200 OK
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="manuel-kripto.xlsx"
```

### `POST /manual-crypto/import`
Excel dosyasından **replace-all** import (mevcut kayıtlar silinir, yeniler eklenir).

```
multipart/form-data: file=manuel-kripto.xlsx

200 OK — kaydedilen liste (ManualCryptoOut[])
422: { "detail": "Sadece .xlsx dosyası kabul edilir" }
422: { "detail": "Geçerli manuel kripto kaydı bulunamadı" }
```

> Schema validator `avg_cost_tl ≤ 0 → None`, `symbol` otomatik upper-case. Replace-all davranışı kullanıcıyı uyarmak için frontend'de onay popup'ı gösterilir.

---

## 9. AI Tavsiye (`/api/v1/advice`) — Faz 3'te Kredi Tüketir

### `POST /advice/generate`
```json
{ "horizon": "medium" }   // 'medium' (5 kredi) | 'long' (10 kredi)

// 200 OK
{
  "id":                "uuid",
  "horizon":           "medium",
  "content":           "## Öneriler\n- ...",
  "credits_used":      5,
  "prompt_tokens":     250,
  "completion_tokens": 800,
  "generated_at":      "2026-04-29T..."
}

// 402 Payment Required (Faz 3)
{ "detail": "Yetersiz kredi. Bakiye: 2, gerekli: 5" }
```

### `GET /advice`
Kullanıcının tüm tavsiye geçmişi.

> Detaylı prompt tasarımı, model seçimi, token bütçesi: [ai-ve-finans.md](./ai-ve-finans.md)

---

## 10. Krediler (`/api/v1/credits`) — Faz 3

### `GET /credits`
Bakiye + son işlemler.
```json
{
  "balance": 145,
  "transactions": [{
    "amount":     -5,
    "reason":     "ai_advice_medium",
    "created_at": "2026-04-29T..."
  }]
}
```

### `POST /credits/checkout`
iyzico ödeme oturumu başlat. İdempotency key zorunlu.
```json
{ "package": "standard", "idempotency_key": "uuid-v4" }
// Response: iyzico checkout URL
```

### `POST /credits/webhook`
iyzico callback. İmza doğrulaması yapılır; başarılı ödemede `credit_transactions`'a pozitif kayıt eklenir, `users.credit_balance` güncellenir.

> Detaylı kredi/ödeme akışı: [kredi-sistemi.md](./kredi-sistemi.md)

---

## 11. Harcamalar (`/api/v1/expenses`) — Faz 3 MVP

Manuel harcama takibi modülü. 10 sabit kategori (`food`, `groceries`, `transport`, `bills`, `health`, `entertainment`, `clothing`, `home`, `tax`, `other`); kategori dışı değer 422 döndürür. Tüm endpoint'ler auth gerektirir; başka kullanıcının kaydına erişim 404 döner (IDOR koruması).

### `GET /expenses`
Kullanıcının harcamalarını listeler. Tarihe göre **azalan** sıralı.

| Query param | Tür | Açıklama |
|-------------|-----|----------|
| `year`      | int  | Opsiyonel — yıl filtresi |
| `month`     | int  | Opsiyonel — ay filtresi (1-12). `year` ile birlikte kullanılır |
| `category`  | enum | Opsiyonel — `ExpenseCategory` değeri; geçersizse 422 |

```json
200 OK
[{
  "id":          "uuid",
  "amount":      "245.50",
  "category":    "groceries",
  "date":        "2026-04-29",
  "description": "Migros haftalık alışveriş",
  "created_at":  "2026-04-29T18:32:00Z"
}]

422: { "detail": "value is not a valid enumeration member" }
```

### `POST /expenses`
Yeni harcama ekler.
```json
// Request — ExpenseCreate
{
  "amount":      "245.50",       // Decimal, gt=0
  "category":    "groceries",     // ExpenseCategory
  "date":        "2026-04-29",    // ISO date
  "description": "Migros"         // Opsiyonel, max_length=500
}

// 201 Created — ExpenseOut
{ "id": "uuid", "amount": "245.50", ... }

422: { "detail": "ensure this value is greater than 0" }     // amount <= 0
422: { "detail": "value is not a valid enumeration member" } // geçersiz kategori
```

### `PUT /expenses/{id}`
Partial update — `ExpenseUpdate` tüm alanları opsiyonel. Body'de gönderilen alanlar değişir, diğerleri korunur.
```json
// Request — ExpenseUpdate (örn. sadece tutar)
{ "amount": "260.00" }

// 200 OK — güncellenmiş ExpenseOut
404: { "detail": "Harcama bulunamadı" }   // başka kullanıcı veya yok
```

### `DELETE /expenses/{id}`
```
204 No Content
404: { "detail": "Harcama bulunamadı" }
```

### `GET /expenses/summary?year=&month=`
Belirli ayın toplamı + kategori kırılımı. `year` ve `month` zorunlu.
```json
200 OK — ExpenseSummary
{
  "year":   2026,
  "month":  4,
  "total":  "3450.75",
  "count":  18,
  "by_category": [
    { "category": "groceries", "total": "1250.00", "count": 6 },
    { "category": "bills",     "total":  "980.50", "count": 3 },
    { "category": "transport", "total":  "620.25", "count": 5 }
  ]
}
```

> Boş ayda `total="0"`, `count=0`, `by_category=[]` döner (404 değil).

### `GET /expenses/export?year=&month=`
Harcamaları Excel dosyası olarak indir (kırmızı başlık tema). `year` + `month` opsiyonel — verilirse o ayın kayıtları, verilmezse tüm geçmiş.

### `POST /expenses/import`
Excel dosyasından **append** (mevcut kayıtlar silinmez). Türkçe label haritası içerir (`yiyecek` → `food` vb.); geçersiz/parse edilemeyen satırlar atlanır.
```
multipart/form-data: file=harcamalar.xlsx
201 Created — eklenen kayıtlar
400: { "detail": "Geçersiz Excel dosyası" }
```

---

## 12. Gelirler (`/api/v1/income`) — Faz 3

Manuel gelir takibi modülü. 7 sabit kategori (`salary`, `freelance`, `rental`, `dividend`, `bonus`, `sale`, `other`); kategori dışı değer 422 döndürür. Auth + IDOR koruması.

### `GET /income`
Gelir listesi. Tarihe göre **azalan** sıralı. Opsiyonel filtreler: `year` + `month`, `category`.

### `POST /income`
```json
// Request — IncomeCreate
{
  "amount":      "45000.00",
  "category":    "salary",
  "date":        "2026-05-01",
  "description": "Mayıs maaşı"
}
// 201 Created — IncomeOut
```

### `PUT /income/{id}` — partial update (4 alan opsiyonel)
### `DELETE /income/{id}` — 204
### `GET /income/summary?year=&month=` — `IncomeSummary` (toplam + kategori kırılımı, harcama summary ile aynı yapı)
### `GET /income/export?year=&month=` — yeşil başlık temalı xlsx
### `POST /income/import` — Excel'den append, Türkçe label haritası (`maaş` → `salary` vb.)

---

## 13. Bütçe (`/api/v1/budgets`) — Faz 3

Kategori bazlı aylık bütçe. Kategori seti `Expense` ile aynı (10 sabit kategori).

### `GET /budgets`
Kullanıcının tanımlı bütçeleri (kategori sıralı).
```json
[{ "id": 1, "category": "groceries", "amount": "3500.00", "updated_at": "2026-05-01T10:00:00Z" }]
```

### `PUT /budgets/{category}`
**UPSERT** (PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`, hedef constraint `uq_budget_user_category`).
```json
// Request — BudgetUpsert
{ "amount": "3500.00" }   // Decimal, gt=0, le=99_999_999.99

// 200 OK — BudgetOut
{ "id": 1, "category": "groceries", "amount": "3500.00", "updated_at": "2026-05-03T..." }

422: { "detail": "Geçersiz kategori: ..." }   // EXPENSE_CATEGORIES dışı
```

### `DELETE /budgets/{category}`
```
204 No Content
404: { "detail": "Bütçe bulunamadı" }
```

### `GET /budgets/comparison?year=&month=`
Belirli ayın bütçe vs. gerçekleşen (bütçesi olan veya harcaması olan tüm kategoriler).
```json
200 OK
[{
  "category":      "groceries",
  "budget_amount": "3500.00",   // null → bütçe tanımlı değil ama harcama var
  "actual_amount": "4200.50",   // 0 olabilir
  "remaining":     "-700.50",   // null → budget_amount null
  "pct_used":       120.01,     // null → budget_amount null veya 0
  "over_budget":    true        // actual > budget
}]
```

---

## 14. Kıymetli Madenler (`/api/v1/portfolio/commodities`) — Faz 3

Altın ve gümüş varlık takibi. 3 birim tipi: `gram`, `biga` (5 + 8 = 13 standart kod), `coin` (6 sikke türü).

### `GET /portfolio/commodities`
Tüm varlıklar + anlık fiyatlar + summary.
```json
200 OK — CommoditySummaryOut
{
  "positions": [{
    "id":              1,
    "unit_type":       "gram",
    "metal":           "gold",
    "biga_code":       null,
    "coin_type":       null,
    "quantity":        "10.5000",
    "notes":           "Banka kasası",
    "created_at":      "...",
    "gram_equivalent": "10.5000",
    "total_value_tl":  "45120.50",
    "gold_price_tl":   "4297.19",
    "silver_price_tl": "53.42"
  }],
  "total_gold_gram":         "10.5000",
  "total_silver_gram":        "0.0000",
  "total_value_tl":         "45120.50",
  "gold_price_tl":           "4297.19",
  "silver_price_tl":           "53.42",
  "gold_price_available":      true,
  "silver_price_available":    true     // false → Yahoo fail; pozisyonlar toplama dahil değil
}
```

### `POST /portfolio/commodities`
```json
// Request — CommodityCreate (Pydantic model_validator unit/metal/biga/coin uyumu zorlar)
{
  "unit_type": "biga",     // 'gram' | 'biga' | 'coin'
  "metal":     "gold",     // 'biga' veya 'coin' için biga_code/coin_type'tan otomatik set
  "biga_code": "A05",      // Sadece biga için (A01-A08 altın, G01-G07 gümüş)
  "coin_type": null,       // Sadece coin için (ceyrek/yarim/tam/cumhuriyet/resat/ata)
  "quantity":  "2",
  "notes":     "100g BiGA"
}
// 201 Created — CommodityOut
422: { "detail": "Geçerli bir BiGA kodu girin" } | { "detail": "Geçerli bir sikke türü girin" }
```

### `PUT /portfolio/commodities/{id}`
Partial update — `quantity` + `notes` opsiyonel.

### `DELETE /portfolio/commodities/{id}` — 204
### `GET /portfolio/commodities/export` — altın sarısı başlık temalı xlsx
### `POST /portfolio/commodities/import` — Excel'den **append** (mevcut kayıtlar silinmez)

> Anlık fiyat servisi `services/commodity.py::fetch_metal_prices()` TCMB USD/TRY (kritik) + Yahoo Finance XAU=X→GC=F + XAG=X→SI=F fallback chain'i kullanır. 5 dakika in-memory cache; Yahoo başarısız olursa TTL 30 sn'ye düşer. TCMB başarısız olursa endpoint 500 döner; metal fiyatı 0 ise pozisyonlar toplama dahil edilmez ama listelenmeye devam eder.

---

## 15. Kullanıcı Hesap (`/api/v1/user`) — Faz 3

### `GET /user/me`
```json
200 OK — UserMeOut
{
  "email":           "user@example.com",
  "risk_profile":    "balanced",
  "created_at":      "2026-04-29T...",
  "email_verified":  true,
  "credit_balance":  0
}
```

### `PUT /user/profile`
Risk profili güncelle.
```json
// Request — ProfileUpdate
{ "risk_profile": "aggressive" }   // Literal['conservative','balanced','aggressive']
// 200 OK — UserMeOut (güncel)
```

### `PUT /user/password`
Mevcut şifre doğrulamalı şifre değiştirme.
```json
// Request — PasswordChange
{ "current_password": "...", "new_password": "12345678" }   // new_password min_length=8
// 200 OK
{ "detail": "Şifre güncellendi" }
// 400 Bad Request
{ "detail": "Mevcut şifre hatalı" }
```

### `DELETE /user/me`
Hesabı **soft-delete** eder (`users.deleted_at = now()`). Hard-delete cron job (Faz 3 TODO) `deleted_at + 30 gün` sonra fiziksel silme yapacak.
```json
200 OK
{ "detail": "Hesap silindi" }
```

> KVKK uyumu için `/me/data-export` (kullanıcı verisi indirme) ayrı endpoint olarak Faz 3'te eklenecek.

---

## 15.1 Nakit / Banka Hesabı (`/api/v1/cash`) — Faz 3

```
GET    /cash               → liste (CashSummaryOut: holdings + total_tl)
POST   /cash               → ekle (CashCreate: label, amount, currency)
PUT    /cash/{id}          → güncelle (partial: label/amount/currency/notes)
DELETE /cash/{id}          → sil (204)
```

**Currency:** `TRY | USD | EUR | GBP`. USD/EUR/GBP otomatik TCMB kuru ile TL'ye çevrilir (`amount_tl` response'ta dönülür).

**Validation:** `amount: Decimal(ge=0, le=999_999_999_999.99)`, `label: str(min_length=1, max_length=100)`.

**IDOR:** Tüm endpoint'lerde `user_id == current_user.id` filtresi.

```json
// POST /cash request
{ "label": "Garanti TL", "amount": "5000.00", "currency": "TRY" }

// 201 Created
{ "id": 1, "label": "Garanti TL", "amount": "5000.00", "currency": "TRY", "amount_tl": "5000.00", ... }
```

---

## 15.2 Nakit Akış Projeksiyonu (`/api/v1/cash-flow`) — Faz 3

```
GET /cash-flow?year=2026                  → 12 aylık projeksiyon
GET /cash-flow/report.xlsx?year=2026     → Excel rapor
GET /cash-flow/report.pdf?year=2026      → PDF rapor (DejaVu Sans, TR karakter)
```

**Hesaplama:**
- `income_actual`: `incomes` tablosundan gerçek aylık toplam
- `income_forecast`: `recurring_incomes` projeksiyonu (recurrence: monthly/quarterly/biannual/yearly/custom)
- `expense_actual`: `expenses` tablosundan (çift sayım filtresi: `or_(credit_card_id IS NULL, is_paid=false)`) + `credit_card_statements.due_date` o aydaysa
- `expense_forecast`: `planned_expenses` projeksiyonu + `credit_card_installments` aylık taksit
- `is_past`: bu ay'dan eski mi (UI farklı renk)

```json
// GET /cash-flow?year=2026
{
  "year": 2026,
  "months": [
    { "month": 1, "income_actual": "5000", "income_forecast": "8000", "expense_actual": "3500",
      "expense_forecast": "2000", "income_total": "13000", "expense_total": "5500", "net": "7500", "is_past": false },
    ...
  ],
  "total_income": "...", "total_expense": "...", "total_net": "..."
}
```

---

## 15.3 Kredi Kartları (`/api/v1/credit-cards`) — Faz 3 finans modülü

**Kart CRUD:**
```
GET    /credit-cards                        → kullanıcının kartları (liste)
POST   /credit-cards                        → yeni kart
GET    /credit-cards/{id}                   → detay (statements + installments tek seferde)
PUT    /credit-cards/{id}                   → güncelle
DELETE /credit-cards/{id}                   → sil (CASCADE statements + installments)
GET    /credit-cards/summary                → özet (toplam limit, kullanılan, kalan)
```

**Card alanları:** `name, bank_name, last_4, credit_limit, statement_day, payment_due_day, current_period_debt`.

> ⚠️ **PCI-DSS scope DIŞI**: Sadece `last_4` (son 4 hane) saklanır; PAN, CVV, expiry asla DB'ye yazılmaz.

**Aylık ekstre (statements):**
```
POST   /credit-cards/{id}/statements        → ekstre ekle (period_year, period_month, statement_amount, due_date, paid_at?)
PUT    /credit-cards/{id}/statements/{sid}  → güncelle (paid_at set)
DELETE /credit-cards/{id}/statements/{sid}  → sil
```

UNIQUE `(card_id, period_year, period_month)` — aynı dönem için tek ekstre.

**Taksitler (installments):**
```
POST   /credit-cards/{id}/installments       → ekle (description, total_amount, monthly_amount, installments_total/remaining, first_due_date)
PUT    /credit-cards/{id}/installments/{iid} → güncelle
DELETE /credit-cards/{id}/installments/{iid} → sil
```

Cash Flow projection (`/cash-flow`) installments'i otomatik dahil eder.

---

## 15.4 Asset Catalog — Manuel Kripto Autocomplete (`/api/v1/asset-catalog`) — Faz 3

```
GET /asset-catalog?q=BTC&source=binance&limit=20  → autocomplete
```

**Query params:**
- `q: str(max_length=100)` — arama terimi (boş = popüler ilkler)
- `source: "commodity"|"binance"|"coingecko"|"tefas"|None` — filtre (boş = hepsi)
- `limit: int(1-100, default 20)`

**Kaynaklar:**
- `commodity` (statik, 2 kalem): XAU = altın gr, XAG = gümüş gr
- `binance` (5 dk cache): USDT pariteli base symbol'leri (BTC, ETH, SOL, vb.)
- `coingecko` (24 saat cache): `/coins/list` (~17K coin); `COINGECKO_SYMBOL_OVERRIDES` map ile alias çakışmaları
- `tefas` (1 saat cache): aktif fon listesi (kod + isim)

```json
// GET /asset-catalog?q=BTC&source=binance
[
  { "source": "binance", "id": "BTC", "symbol": "BTC", "name": "BTC" }
]
```

---

## 15.5 Periyodik Gelir Realize (`/api/v1/income/recurring`) — Faz 3

```
POST   /income/recurring/{id}/realize          → tek dönem ({year, month}) → incomes'a kayıt
POST   /income/recurring/{id}/realize-past     → start_date'ten bugüne tüm dönemler
POST   /income/recurring/realize-all-past      → tüm aktif recurring'ler için
```

**Kural:** `incomes.recurring_income_id` (FK→recurring_incomes, ON DELETE SET NULL) + UNIQUE `(recurring_income_id, date)` — çift realize'ı engeller.

**Recurrence değerleri:** `monthly | quarterly | biannual | yearly | custom (months: int[])`.

```json
// POST /income/recurring/123/realize
{ "year": 2026, "month": 5 }

// 200 OK
{ "id": 456, "amount": "5000", "date": "2026-05-15", "category": "salary", "recurring_income_id": 123 }
```

UI'da realize'lı kayıtlarda mavi "↻ periyodik" rozeti.

---

## 15.6 Snapshot Raporu İndirme (`/api/v1/portfolio/snapshot/{date}/report.*`) — Faz 3

```
GET /portfolio/snapshot/2026-05-08/report.xlsx → Excel (tüm pozisyonlar)
GET /portfolio/snapshot/2026-05-08/report.pdf  → PDF (ilk 50 pozisyon, en büyük → küçük)
```

**Excel içeriği:** Tip, provider, sembol, isim, likit, stake, pending_rewards, fiyat, toplam_tl, ağırlık_yüzdesi.

**PDF içeriği:** İlk 50 pozisyon (büyük → küçük) + USD karşılığı + USD/TRY kuru. DejaVu Sans font (Türkçe karakter desteği — `backend/Dockerfile`'a yüklü).

**Yetki:** Sadece kullanıcının kendi snapshot'larına (`user_id == current_user.id` filtresi).

History sayfasında her snapshot satırında 📊 xlsx + 📄 pdf butonları.

---

## 16. Geliştirme İpuçları

### OpenAPI Dokümantasyonu
Otomatik Swagger UI: `http://localhost:8000/docs`
OpenAPI JSON: `http://localhost:8000/openapi.json`

### Test Etmek
```bash
# Login + token al
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"u@x.com","password":"12345678"}'

# Token ile pozisyon çek
curl http://localhost:8000/api/v1/portfolio/crypto \
  -H "Authorization: Bearer eyJ..."
```

### Rate Limit Test
slowapi `RemoteAddress`'e göre limit uygular; localhost'tan 10+ istek 429 dönecektir.

---

## 17. Audit Log (`/api/v1/audit-logs`) — FAZ C6 + PERF-001 pagination

### `GET /api/v1/audit-logs`
Kullanıcının kendi audit log kayıtlarını döner (en yeniden eskiye). IDOR korumalı: sadece `user_id == current_user.id` filtreli kayıtlar.

> **PERF-001 (FAZ H, 2026-05-10):** Response artık `PaginatedResponse[T]`
> formatında — `items + total_count + has_next + limit + offset`. Frontend
> sayfalama UI'ı için doğrudan kullanılabilir. **Geriye uyumsuz değişiklik:
> response array değil object**.

**Query params:**
- `action_prefix` (opsiyonel) — `auth.`, `wallet.`, `integration.`, `snapshot.`, `account.`, `kvkk.`, `user.` ile başlayanları filtreler
- `limit` (opsiyonel, default 50, min 1, max 500)
- `offset` (opsiyonel, default 0, min 0)

**Loglanan eylemler (`app/services/audit.py::AuditAction`):**

| Action | Trigger | Extra alanları |
|--------|---------|----------------|
| `auth.login` | Başarılı giriş | – |
| `auth.login_failed` | Yanlış şifre / mevcut olmayan e-posta | `extra.email`, `extra.failed_count`, `extra.locked` |
| `auth.logout` | `POST /auth/logout` | – |
| `auth.register` | Yeni kullanıcı kaydı | `extra.email`, `extra.risk_profile` |
| `auth.password_change` | `PUT /user/password` | – |
| `auth.password_reset_request` | `POST /auth/forgot-password` (SEC-001) | `extra.email`, `extra.user_exists` |
| `auth.password_reset_complete` | `POST /auth/reset-password` (SEC-001) | `extra.success`, `extra.email` |
| `user.email_change_request` | `POST /user/email/request` (COMP-029) | `extra.old_email`, `extra.new_email` |
| `user.email_change_complete` | `GET /user/email/confirm?token=...` | `extra.success`, `extra.old_email`, `extra.new_email` |
| `user.consent_revoke` | `DELETE /user/consent/{type}` (COMP-006) | `extra.consent_type` |
| `user.data_export` | `GET /user/data-export` (COMP-003) | `extra.snapshot_count`, `extra.audit_log_count`, `extra.wallet_count` |
| `kvkk.anthropic_consent_grant` | `POST /user/anthropic-consent` (AI-005) | `extra.version` |
| `kvkk.anthropic_consent_revoke` | `DELETE /user/anthropic-consent` (AI-005) | – |
| `wallet.add` | `POST /wallets` | `extra.chain`, `extra.label`, `resource: wallet:{uuid}` |
| `wallet.delete` | `DELETE /wallets/{id}` | `extra.chain`, `resource: wallet:{uuid}` |
| `wallet.export` | `GET /wallets/export` (COMP-024) | `extra.wallet_count`, `extra.include_full_address` |
| `integration.add` | `POST /integrations` | `extra.updated`, `resource: integration:{provider}` |
| `integration.delete` | `DELETE /integrations/{provider}` | `resource: integration:{provider}` |
| `snapshot.delete` | `DELETE /portfolio/snapshot/{date}` | `resource: snapshot:{date}` |
| `account.soft_delete` | `DELETE /user/me` | `resource: user:{uuid}` |
| `advice.generate` | `POST /advice/generate` (AI-004) | `extra.horizon`, `extra.model`, `extra.prompt_tokens`, `extra.credits_used` |

```json
// 200 OK — PaginatedResponse[AuditLogOut]
{
  "items": [
    {
      "id": "01H8X...",
      "action": "wallet.add",
      "resource": "wallet:550e8400-e29b-41d4-a716-446655440000",
      "ip_address": "192.168.1.50",
      "user_agent": "Mozilla/5.0 ...",
      "extra": { "chain": "bitcoin", "label": "Ana cüzdan" },
      "created_at": "2026-05-06T20:35:12.123Z"
    },
    {
      "id": "01H8Y...",
      "action": "auth.login",
      "resource": null,
      "ip_address": "192.168.1.50",
      "user_agent": "Mozilla/5.0 ...",
      "extra": null,
      "created_at": "2026-05-06T20:34:55.001Z"
    }
  ],
  "total_count": 247,
  "limit": 50,
  "offset": 0,
  "has_next": true
}
```

### Örnek Kullanım
```bash
# İlk sayfa (50 kayıt)
curl https://kfinans.app/api/v1/audit-logs \
  -H "Authorization: Bearer eyJ..."

# Sonraki sayfa
curl "https://kfinans.app/api/v1/audit-logs?offset=50" \
  -H "Authorization: Bearer eyJ..."

# Sadece wallet eylemleri (filtreli)
curl "https://kfinans.app/api/v1/audit-logs?action_prefix=wallet.&limit=20" \
  -H "Authorization: Bearer eyJ..."
```

> **COMP-022 (FAZ H):** Audit log'lar 365 gün retention sonrası
> `_purge_old_audit_logs_job` cron'u ile fiziksel silinir (KVKK m.7).
> Saklama detay: `docs/legal/incident-response-plan.md` §6.

---

## 18. Eksik / Eklenecek (TODO)

- [x] `POST /auth/register` testleri (14 yeni test test_auth.py'da)
- [x] `GET /auth/verify-email`, `POST /auth/resend-verification` endpoint'leri
- [x] `POST /portfolio/snapshot` manuel tetikleme endpoint'i
- [x] `POST /auth/logout` (JWT blacklist) + `POST /auth/refresh` revoked token kontrolü
- [ ] `POST /auth/forgot-password` / `POST /auth/reset-password` — Faz 2 sonraki adım
- [x] BES manuel giriş endpoint'leri (`/portfolio/bes/*` — GET, PUT, export, import)
- [ ] Kredi endpoint'leri (`/credits/*`) — Faz 3
- [x] Harcama endpoint'leri (`/expenses/*`) — Faz 3 MVP (5 endpoint: list/create/update/delete/summary + Excel export/import)
- [x] Gelir endpoint'leri (`/income/*`) — Faz 3
- [x] Bütçe endpoint'leri (`/budgets/*`) — Faz 3 (UPSERT + comparison)
- [x] Kıymetli maden endpoint'leri (`/portfolio/commodities/*`) — Faz 3
- [x] Kullanıcı yönetimi (`/user/me`, `PUT /user/profile`, `PUT /user/password`, `DELETE /user/me` soft-delete) — Faz 3
- [x] Finansal hedef (`/goals/me`) — Faz 3 (USD/EUR/GBP/TRY)
- [x] MKK e-Yatırımcı Excel import (`/portfolio/tefas/import-mkk` + `/portfolio/stocks/import-mkk`) — Faz 3
- [x] Manuel kripto endpoint'leri (`/manual-crypto/*`) — Faz 3 (API'siz borsalar için CRUD + Excel + anlık fiyat)
- [ ] Harcama analizi AI (`/expenses/analysis/generate`) — Faz 3 (3 kredi)
- [ ] `/user/data-export` (KVKK) — Faz 3
- [ ] Pagination (cursor-based) `/portfolio/history` ve `/advice` için
- [ ] Server-Sent Events `/portfolio/stream` (anlık fiyat) — Faz 4
