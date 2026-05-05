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

### 1.4 Rate Limiting (slowapi, in-memory)
| Endpoint              | Limit                                |
| --------------------- | ------------------------------------ |
| `POST /auth/login`    | 10/dakika                            |
| `POST /auth/register` | 5/dakika                             |
| `POST /auth/refresh`  | 30/dakika                            |
| Diğer                 | Henüz limit yok (Faz 3'te eklenecek) |

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
Yeni access + refresh token üretir. Rate limit: 30/dk. Refresh token'ın `jti`'si `revoked_tokens` tablosundaysa **401 "Token iptal edilmiş"** döner.
```json
{ "refresh_token": "eyJ..." }

// 401 Unauthorized — token logout ile iptal edilmiş
{ "detail": "Token iptal edilmiş" }
```

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

## 17. Eksik / Eklenecek (TODO)

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
- [ ] Harcama analizi AI (`/expenses/analysis/generate`) — Faz 3 (3 kredi)
- [ ] `/user/data-export` (KVKK) — Faz 3
- [ ] Pagination (cursor-based) `/portfolio/history` ve `/advice` için
- [ ] Server-Sent Events `/portfolio/stream` (anlık fiyat) — Faz 4
