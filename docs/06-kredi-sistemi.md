# Kredi Sistemi ve Ödeme Akışı

**Sahip ajanlar:** `architect`, `finance-expert`
**Faz:** 3 (kısmen uygulandı — aşağıdaki durum tablosuna bakın)
**İlgili:** [api-referansi.md](./api-referansi.md), [uyumluluk-kvkk.md](./uyumluluk-kvkk.md)

---

## 0. Uygulama Durumu (Önemli — Uygulanan vs Planlanan)

Bu doküman **hem mevcut kredi defteri (ledger) hem de planlanan ödeme akışını** kapsar.
Karışmaması için net ayrım:

| Bileşen | Durum |
| ------- | ----- |
| `users.credit_balance` (INT, default 0) | ✅ **Uygulandı** — migration `d4e5f6a7b8c9` |
| `CHECK (credit_balance >= 0)` constraint | ✅ **Uygulandı** — `ck_users_credit_balance_nonnegative` |
| `users.anthropic_consent_at` + `anthropic_consent_version` | ✅ **Uygulandı** — KVKK m.9 rıza |
| `investment_advice.credits_used` (INT) | ✅ **Uygulandı** — AI-007 |
| Kredi **tüketim** akışı (`/advice/generate`, tavsiye başına 1 kredi atomik düşüm) | ✅ **Uygulandı** — AI-007, bkz. §4.2 |
| Yetersiz bakiye → 402 Payment Required | ✅ **Uygulandı** |
| `credit_transactions` tablosu (ledger/audit trail) | ❌ **Planlanan** — kod yok |
| `GET /credits`, `POST /credits/checkout`, `POST /credits/webhook` endpoint'leri | ❌ **Planlanan** — router yok |
| iyzico ödeme entegrasyonu (checkout, webhook, HMAC, idempotency) | ❌ **Planlanan** — kod yok |
| `core/credits.py` `deduct_credits()` helper | ❌ **Planlanan** — düşüm şu an doğrudan `advice.py`'de |
| Kredi paketleri / fiyatlandırma | ❌ **Planlanan** — tasarım |
| Frontend: bakiye göstergesi, satın alma, geçmiş, modal | ❌ **Planlanan** |
| e-Arşiv fatura, cayma hakkı, refund | ❌ **Planlanan** |

> **Özet:** Bakiye düşürülebiliyor ama bakiye **yüklenemiyor** (ödeme yok). Şu an krediler
> yalnızca manuel/seed yoluyla artar. §1–§3 ve §5.2 sonrası ile §6–§11 **tasarım**'dır;
> mevcut tüketim mantığı §4.2 ile §5.1'de anlatılır.
>
> **Mevcut tüketim maliyeti farkı:** Aşağıdaki tasarım tablolarında AI tavsiye 5–10 kredi
> olarak planlanmıştır; **uygulanan** kod `advice.py::ADVICE_COST = 1` (tavsiye başına 1
> kredi, vade ayrımı yok). Fiyatlandırma kesinleşince hizalanacak.

---

## 1. Genel Konsept

KFinans **kredi tabanlı SaaS** modeli hedefler (kısmen uygulandı — bkz. §0). Temel takip
ücretsiz; AI tavsiye, kripto/blockchain otomatik senkronizasyon ve gelişmiş analiz **kredi
tüketir**. Hedef akışta kullanıcı kredi paketi satın alır; her ücretli işlem bakiyeden düşer.
Şu an yalnızca AI tavsiye tüketimi (1 kredi/tavsiye) uygulanmıştır; satın alma akışı planlıdır.

### 1.1 Avantajlar (vs Abonelik)
- **Düşük giriş bariyeri** — 29₺'lik başlangıç paketi
- **Kullanım kadar öde** — yatırımcının aktivite seviyesine uygun
- **Kullanılmayan kredi yanmaz** — kullanıcı dostu
- **Stripe/iyzico'da abonelik karmaşıklığı yok**

### 1.2 Dezavantajlar (Bilinçli Tradeoff)
- Aylık öngörülebilir gelir (MRR) yok → Faz 4'te aylık abonelik opsiyonu eklenebilir
- Kullanıcı kredi azaldıkça uyarı görmek zorunda

---

## 2. Kredi Paketleri

| Paket | Kredi | Fiyat (₺) | Birim Maliyet | Hedef Profil |
|-------|-------|-----------|---------------|--------------|
| Başlangıç | 50 | 29 | 0.58 ₺/kredi | Yeni kullanıcı, deneme |
| **Standart** ⭐ | 150 | 69 | 0.46 ₺/kredi | Aktif yatırımcı |
| Profesyonel | 500 | 199 | 0.40 ₺/kredi | Yoğun kullanım |

> Fiyatlar KDV dahil. Faz 4'te uluslararası (USD/EUR) paketler eklenecek.

---

## 3. Kredi Tüketim Kuralları

| İşlem | Maliyet | Gerekçe |
|-------|---------|---------|
| AI portföy tavsiyesi (orta vade) | 5 kredi | Anthropic API maliyeti ~$0.01-0.02 |
| AI portföy tavsiyesi (uzun vade) | 10 kredi | Daha uzun analiz, opsiyonel Opus model kullanımı |
| Kripto senkronizasyonu (Binance/iCrypex/BinanceTR) | 1 kredi/çekim | Exchange API rate limit'i koruma |
| Blockchain bakiye sorgusu (Sonic/Avalanche/Ethereum) | 1 kredi/sorgu | RPC node maliyeti (Infura/Alchemy) |
| Gelişmiş harcama analizi (Faz 3 — harcama takibi) | 3 kredi | AI kategorizasyon |
| TEFAS preview | 0 kredi (ücretsiz) | TEFAS API ücretsiz, koruma slowapi rate limit |
| Hisse fiyat çekme | 0 kredi (ücretsiz) | Yahoo Finance ücretsiz |
| Excel import/export | 0 kredi (ücretsiz) | Lokal işlem |

### 3.1 Karmaşıklık Çarpanı (Faz 4)
Portföydeki varlık sayısı çok fazlaysa (20+) AI tavsiye 1 ek kredi tüketebilir:
```python
def calculate_advice_cost(horizon: str, asset_count: int) -> int:
    base = {"medium": 5, "long": 10}[horizon]
    return base + (1 if asset_count >= 20 else 0)
```

---

## 4. Kredi Akışı

### 4.1 Yükleme (Satın Alma)

```
Kullanıcı /credits/checkout
  ↓ paket seç (başlangıç/standart/profesyonel)
  ↓ idempotency_key gönder (uuid v4)

Backend
  ↓ POST iyzico/checkout/initialize
    ↓ amount, currency=TRY, callback_url, conversation_id=idempotency_key
  ↓ iyzico checkout URL döner

Frontend
  ↓ kullanıcıyı iyzico sayfasına redirect

Kullanıcı kart bilgilerini girer
  ↓ iyzico ödeme alır
  ↓ webhook → POST /credits/webhook { conversation_id, status, payment_id }

Backend webhook
  ↓ HMAC imza doğrula
  ↓ idempotency_key kontrolü (zaten işlendi mi?)
  ↓ status == 'success' ise:
    ↓ INSERT credit_transactions (amount: +50/+150/+500, reason: "purchase")
    ↓ UPDATE users SET credit_balance = credit_balance + amount
    ↓ commit transaction

Frontend (callback URL'den geri döndüğünde)
  ↓ GET /credits → güncel bakiye
```

### 4.2 Tüketim (AI Tavsiye) ✅ Uygulanan akış

`api/v1/advice.py::generate_advice` — şu an **uygulanan** mantık (AI-007):
```
Frontend POST /advice/generate { horizon: "medium" }   (slowapi 5/saat)

Backend
  ↓ 1) anthropic_consent_at IS NULL → 403 (KVKK m.9)
  ↓ 2) credit_balance < ADVICE_COST (=1) → 402 Payment Required   (LLM çağrısından ÖNCE)
  ↓ 3) son snapshot çek (yoksa 404)
  ↓ AdvisorService.generate(...) → Anthropic API
  ↓    AI başarısız → advisor.generate() HTTPException fırlatır, aşağı gelinmez (kredi düşmez)
  ↓ advice.credits_used = 1
  ↓ user.credit_balance -= 1
  ↓ db.add(advice) + audit log (ADVICE_GENERATE)
  ↓ db.commit()   (tek transaction — advice + bakiye birlikte)
  ↓ return advice
```

**Uygulanan ile tasarım arasındaki farklar (kasıtlı / Faz 3 backlog):**
- Maliyet sabiti `ADVICE_COST = 1` (vade ayrımı yok); tasarım 5/10 kredi öneriyordu.
- `credit_transactions` ledger insert'i **yok** — düşüm yalnızca `users.credit_balance` ve
  `investment_advice.credits_used` üzerinden izleniyor. Ledger tablosu planlı (§5.2).
- `SELECT ... FOR UPDATE` satır kilidi **yok**; tek kullanıcı (sahip) senaryosunda yarış
  durumu pratik risk değil. Multi-user satın alma akışı geldiğinde §8.3'teki kilit eklenmeli.

> **Tasarım (hedef ledger akışı):** `credit_transactions` insert + `SELECT FOR UPDATE`
> ile aşağıdaki desen hedeflenir (henüz uygulanmadı):
> ```
> SELECT credit_balance FROM users WHERE id=X FOR UPDATE
> if balance < cost → ROLLBACK + 402
> AI çağrısı → fail ise ROLLBACK + 503
> INSERT investment_advice + INSERT credit_transactions (amount: -cost)
> UPDATE users SET credit_balance = credit_balance - cost
> COMMIT
> ```

**Kritik:** AI çağrısı başarısız olursa kredi düşmez (exception commit'ten önce fırlar).

---

## 5. Veritabanı Şeması

### 5.1 `users` Tablosu (Mevcut)
✅ `credit_balance INT NOT NULL DEFAULT 0` — migration `d4e5f6a7b8c9` ile eklendi.
✅ `CHECK (credit_balance >= 0)` constraint (`ck_users_credit_balance_nonnegative`) — DB seviyesinde negatif bakiye koruması.
✅ `anthropic_consent_at TIMESTAMPTZ` + `anthropic_consent_version VARCHAR(10)` — eklendi (Anthropic için açık rıza, KVKK m.9; bkz. doc 05 §A.6).

Ayrıca `investment_advice.credits_used INT NOT NULL DEFAULT 0` — her tavsiyenin tükettiği kredi (AI-007).

### 5.2 Yeni Tablo: `credit_transactions`
```sql
CREATE TABLE credit_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount          INT NOT NULL,                       -- pozitif: yükleme, negatif: tüketim
    reason          TEXT NOT NULL,                      -- 'purchase', 'ai_advice_medium', 'crypto_sync' vb.
    reference_id    TEXT,                               -- iyzico paymentId, advice UUID vb.
    idempotency_key TEXT UNIQUE,                        -- çift ödeme/işlem koruması
    metadata        JSONB,                              -- {"package": "standard", "iyzico_status": "..."}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX ix_credit_transactions_created_at ON credit_transactions(created_at DESC);
```

### 5.3 Audit Trail Garantisi
- `ON DELETE RESTRICT`: kullanıcı silinemez eğer kredi işlemi varsa (TTK m.82, 10 yıl saklama)
- KVKK soft delete: `users.deleted_at` set edilir, `credit_transactions` korunur (anonim — `user_id` referans kalır ama kullanıcı PII silinir)

---

## 6. API Endpoint'leri

> ⚠️ **Planlanan (henüz uygulanmadı).** Aşağıdaki `/credits*` endpoint'lerinin hiçbiri kodda
> yoktur (`app/api/v1/credits.py` mevcut değil — sadece `credit_cards.py` var, o ayrı bir
> özellik). Tüketim akışı `/advice/generate` üzerinden çalışır (bkz. §4.2). Bu bölüm Faz 3
> ödeme entegrasyonu tasarımıdır.

### 6.1 `GET /api/v1/credits`
```json
200 OK
{
  "balance": 145,
  "transactions": [
    {
      "id":         "uuid",
      "amount":     -5,
      "reason":     "ai_advice_medium",
      "metadata":   { "advice_id": "uuid" },
      "created_at": "2026-04-29T..."
    },
    {
      "id":         "uuid",
      "amount":     +150,
      "reason":     "purchase",
      "reference_id": "iyzico-payment-id-12345",
      "metadata":   { "package": "standard", "amount_tl": "69.00" },
      "created_at": "2026-04-25T..."
    }
  ],
  "pagination": { "limit": 50, "offset": 0, "total": 23 }
}
```

### 6.2 `POST /api/v1/credits/checkout`
```json
// Request
{
  "package":         "standard",            // 'starter'|'standard'|'professional'
  "idempotency_key": "uuid-v4-from-client"  // çift submit koruması
}

// 200 OK
{
  "checkout_url": "https://sandbox-cpaymentwf.iyzipay.com/payment/...",
  "conversation_id": "uuid-v4",
  "expires_at": "2026-04-29T..."  // 30 dk
}

// 400 Bad Request
{ "detail": "Geçersiz paket: 'foo'" }

// 409 Conflict
{ "detail": "Bu idempotency_key ile zaten bir checkout başlatıldı" }
```

**Rate limit:** 3/dakika (ödeme spam'i önleme)

### 6.3 `POST /api/v1/credits/webhook`
iyzico'dan gelen callback. **Public endpoint** — auth yok, ama HMAC imza ile doğrulanır.

```json
// iyzico body (özet)
{
  "paymentId":      "12345",
  "conversationId": "uuid-v4",
  "status":         "success" | "failure" | "init",
  "paidPrice":      "69.00",
  "currency":       "TRY",
  "signature":      "..."
}

// 200 OK (webhook her zaman 200 döner — iyzico retry'ı durdurmak için)
{ "received": true }
```

**Webhook İşleme:**
1. iyzico HMAC imzasını doğrula (X-IYZ-SIGNATURE header)
2. Idempotency: bu `conversationId` zaten işlenmiş mi? `credit_transactions.idempotency_key` kontrol et
3. status == "success" ise:
   - `credit_transactions` insert (pozitif amount)
   - `users.credit_balance` arttır
4. status == "failure" ise:
   - log kayıt, kullanıcıya bildirim (frontend polling veya WebSocket)

### 6.4 `POST /api/v1/credits/refund` (Admin only — Faz 4)
Manuel iade için yönetim paneli endpoint'i.

---

## 7. iyzico Entegrasyonu

### 7.1 Ortamlar
- **Sandbox:** `sandbox-api.iyzipay.com` (test kartlar)
- **Production:** `api.iyzipay.com` (gerçek kart işlemi)

### 7.2 Konfigürasyon (.env)
```
IYZICO_API_KEY=...
IYZICO_SECRET_KEY=...
IYZICO_BASE_URL=https://sandbox-api.iyzipay.com  # prod'da değişir
IYZICO_CALLBACK_URL=https://app.kfinans.com/credits/callback
IYZICO_WEBHOOK_URL=https://api.kfinans.com/api/v1/credits/webhook
```

### 7.3 SDK Seçimi
- `iyzipay` resmi Python SDK var ama **sync only** → async wrapper yazılacak
- Alternatif: HTTPx ile direkt REST API çağrısı (önerilir; SDK overhead yok)

### 7.4 Test Kartları (Sandbox)
| Kart No | Senaryo |
|---------|---------|
| 5528790000000008 | Başarılı ödeme |
| 5528790000000016 | Yetersiz bakiye |
| 5528790000000024 | 3D Secure |

---

## 8. Güvenlik Kontrolleri

### 8.1 İdempotency
**Çift ödeme önleme:**
- Frontend her checkout'ta yeni `idempotency_key` (UUID v4) üretir
- Backend bu key ile checkout'u DB'ye kaydeder (`credit_transactions` veya ayrı `pending_payments` tablosu)
- Aynı key ile ikinci istek gelirse: önceki sonucu döner (yeni iyzico oturumu açmaz)

### 8.2 Webhook Imza Doğrulama
```python
import hmac, hashlib, base64

def verify_iyzico_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)
```

### 8.3 Race Condition Önleme
Kredi tüketimi mutlaka **`SELECT ... FOR UPDATE`** ile kilitlenmeli:
```python
async with db.begin():
    user = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one()
    if user.credit_balance < cost:
        raise HTTPException(402, "Yetersiz kredi")
    user.credit_balance -= cost
    db.add(CreditTransaction(user_id=user_id, amount=-cost, reason=...))
    # AI çağrısı
    # commit
```

### 8.4 Negatif Bakiye Koruma
- `CHECK (credit_balance >= 0)` constraint (DB seviyesinde)
- Backend'de de Pydantic validation
- Üç katmanlı koruma: frontend disable button + backend check + DB constraint

### 8.5 KDV
Türkiye %20 KDV hesabı:
- 29 ₺ KDV dahil → 24.17 ₺ KDV hariç + 4.83 ₺ KDV
- Fatura kesimi (e-Arşiv) — Faz 3'te muhasebe entegrasyonu

---

## 9. Kullanıcı Deneyimi (UX)

### 9.1 Bakiye Göstergesi (Header)
```
[KFinans logo]   ...   💰 145 kredi   [Profil ▾]
```

### 9.2 Yetersiz Bakiye Modal
```
⚠️ Yetersiz kredi
Bu işlem için 5 kredi gerekiyor, bakiyenizde 2 kredi var.
[Kredi Satın Al] [İptal]
```

### 9.3 Kullanım Geçmişi Sayfası
```
📊 Kredi İşlemleri (Son 30 gün)

📅 29 Nisan 2026
   AI tavsiye (orta vade)              -5 kredi   ✓ alındı
   AI tavsiye (uzun vade)             -10 kredi   ✓ alındı

📅 25 Nisan 2026
   Kredi paketi (Standart, 69 ₺)     +150 kredi   ✓ ödendi

[Tüm geçmişi göster]
```

### 9.4 Düşük Bakiye Uyarısı
- Bakiye < 10 kredi → header'da kırmızı badge
- Bakiye < 5 kredi → e-posta bildirimi (Faz 4)

### 9.5 Cayma Hakkı (6502 Kanun)
**14 gün içinde** kullanılmamış kredi paketinin iadesi. Frontend'de:
```
14 gün içinde, kullanılmamış paketler için iade hakkınız vardır.
[İade talep et]
```
Manuel inceleme: yönetim paneli (Faz 4).

---

## 10. Raporlama ve Muhasebe

### 10.1 Aylık Gelir Raporu (Yönetim — Faz 4)
```sql
SELECT
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) AS purchase_count,
    SUM((metadata->>'amount_tl')::NUMERIC) AS total_revenue_tl
FROM credit_transactions
WHERE reason = 'purchase'
GROUP BY 1
ORDER BY 1 DESC;
```

### 10.2 Kullanım Analitiği
```sql
SELECT reason, COUNT(*), SUM(ABS(amount)) AS total_credits
FROM credit_transactions
WHERE amount < 0  -- tüketim
  AND created_at >= now() - INTERVAL '30 days'
GROUP BY reason;
```

### 10.3 e-Arşiv Fatura (Yasal — Faz 3)
- Her satın alma için e-Arşiv fatura kesilmeli
- Entegrasyon: GİB (Gelir İdaresi) onaylı bir e-fatura entegratörü (Logo, Mikro, Paraşüt)
- KDV beyan döneminde otomatik raporlama

---

## 11. Ölçek ve Performans

### 11.1 Yük Hesabı (Faz 3)
**Hedef:** 1000 aktif kullanıcı, ayda ortalama 20 kredi tüketim, 30 satın alma

- Webhook trafiği: ~30/ay = 1/gün → çok düşük
- Kredi tüketim transaction'ı: ~20K/ay = ~700/gün → düşük
- DB index'leri yeterli; özel optimizasyon gerekmez

### 11.2 Faz 4 Ölçeği
**10K aktif kullanıcı:**
- Webhook spike: aylık 300 satın alma
- Kredi tüketim: 200K/ay = 6.7K/gün = ~5/dakika
- iyzico webhook idempotency için Redis cache eklenebilir (DB hit'i azaltma)

---

## 12. Eksik / Eklenecek (TODO)

### Faz 3 (Implement Edilecek)
- [x] `users.credit_balance` migration — `d4e5f6a7b8c9`
- [x] `users.anthropic_consent_at` + `anthropic_consent_version` (KVKK m.9 rıza)
- [x] `investment_advice.credits_used` kolonu
- [x] `POST /api/v1/advice/generate` — kredi düşme akışı (AI-007, tavsiye başına 1 kredi)
- [ ] `credit_transactions` migration (ledger / audit trail)
- [ ] `core/credits.py` — `deduct_credits(user_id, amount, reason, ref_id)` helper (şu an düşüm doğrudan `advice.py`'de)
- [ ] iyzico SDK / HTTPx wrapper
- [ ] `GET /api/v1/credits` endpoint
- [ ] `POST /api/v1/credits/checkout` endpoint
- [ ] `POST /api/v1/credits/webhook` endpoint
- [ ] Frontend: kredi bakiye header componenti
- [ ] Frontend: kredi geçmişi sayfası
- [ ] Frontend: paket satın alma sayfası
- [ ] Frontend: yetersiz bakiye modal
- [ ] e-Arşiv fatura entegrasyonu (GİB)
- [ ] Cayma hakkı manuel iade akışı (Faz 4 yönetim paneli)

### Faz 4 (İleri Optimizasyon)
- [ ] Aylık abonelik paketi (öngörülebilir gelir)
- [ ] Stripe entegrasyonu (uluslararası)
- [ ] Kupon kodu sistemi (kampanya, lansman)
- [ ] Kredi hediye etme (referral programı)
- [ ] Yönetim paneli (refund, kupon yönetimi, gelir raporu)
- [ ] Düşük bakiye e-posta bildirimi
