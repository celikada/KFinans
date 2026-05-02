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

### `GET /portfolio/wallets`
**Anlık** blockchain pozisyonları (Sonic, Avalanche, Ethereum).
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

---

## 5. TEFAS (`/api/v1/portfolio/tefas`)

### `GET /portfolio/tefas/holdings`
Kayıtlı holding listesi.
```json
[{ "code": "GO3", "quantity": 1500.5, "name": "Garanti Portföy 3" }]
```

### `PUT /portfolio/tefas/holdings`
Tüm holdinglari değiştir (replace-all). Body: holding listesi.

### `POST /portfolio/tefas/preview`
TEFAS'tan **anlık fiyat** çek, kaydetme.
```json
// Request: holding listesi
// Response
[{
  "code":           "GO3",
  "name":           "Garanti Portföy 3",
  "quantity":       "1500.5",
  "unit_price_tl":  "1.2345",
  "total_value_tl": "1852.42"
}]
422: { "detail": "Geçersiz fon kodu: XYZ" }
```

### `GET /portfolio/tefas/export`
Tüm holdinglari xlsx olarak indir (canlı fiyat dahil).

### `POST /portfolio/tefas/import`
xlsx yükle, mevcut holdinglari **siler**, yenilerini ekler.
```
multipart/form-data: file=tefas.xlsx
422: "Sadece .xlsx dosyası kabul edilir" | "Geçerli holding bulunamadı"
```

---

## 6. Hisse Senedi (`/api/v1/portfolio/stocks`)

API yapısı TEFAS ile aynı:
- `GET    /portfolio/stocks/holdings` — listele
- `PUT    /portfolio/stocks/holdings` — replace-all
- `POST   /portfolio/stocks/preview` — Yahoo Finance anlık fiyat
- `GET    /portfolio/stocks/export` — xlsx indir
- `POST   /portfolio/stocks/import` — xlsx yükle

```json
// Holding
{ "ticker": "THYAO.IS", "quantity": 100, "name": "Türk Hava Yolları" }

// Preview response
{
  "ticker":              "AAPL",
  "name":                "Apple Inc.",
  "quantity":            "10",
  "currency":            "USD",
  "unit_price_original": "180.50",
  "unit_price_tl":       "6318.00",
  "total_value_tl":      "63180.00"
}
```

> Ticker formatı: BIST = `THYAO.IS`, ABD = `AAPL`, UK = `BP.L` (GBp döner, ÷100 → GBP).

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
  "chain":   "sonic",       // 'ethereum'|'sonic'|'avalanche_p'|'avalanche_c'
  "address": "0x...",
  "label":   "Ana cüzdan"
}
409: { "detail": "Bu cüzdan zaten kayıtlı" }
```

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

---

## 12. Geliştirme İpuçları

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

## 13. Eksik / Eklenecek (TODO)

- [x] `POST /auth/register` testleri (14 yeni test test_auth.py'da)
- [x] `GET /auth/verify-email`, `POST /auth/resend-verification` endpoint'leri
- [x] `POST /portfolio/snapshot` manuel tetikleme endpoint'i
- [x] `POST /auth/logout` (JWT blacklist) + `POST /auth/refresh` revoked token kontrolü
- [ ] `POST /auth/forgot-password` / `POST /auth/reset-password` — Faz 2 sonraki adım
- [x] BES manuel giriş endpoint'leri (`/portfolio/bes/*` — GET, PUT, export, import)
- [ ] Kredi endpoint'leri (`/credits/*`) — Faz 3
- [x] Harcama endpoint'leri (`/expenses/*`) — Faz 3 MVP (5 endpoint: list/create/update/delete/summary)
- [ ] Harcama analizi AI (`/expenses/analysis/generate`) — Faz 3 (3 kredi)
- [ ] `/me/data-export` (KVKK) ve `/me/account` (DELETE) endpoint'leri
- [ ] Pagination (cursor-based) `/portfolio/history` ve `/advice` için
- [ ] Server-Sent Events `/portfolio/stream` (anlık fiyat) — Faz 4
