# Sistem Mimarisi ve Veritabanı Şeması

**Sahip ajanlar:** `architect`, `dba`
**İlgili dokümanlar:** [api-referansi.md](./api-referansi.md), [altyapi-test.md](./altyapi-test.md)

---

## 1. Mimari Felsefe

KFinans **modüler monolit** mimarisi kullanır. Mevcut ölçekte (Faz 1-3 hedef: ~10K kullanıcı) mikroservis karmaşıklığı (service mesh, distributed tracing, inter-service auth) gereksizdir. Modüler yapı kod içinde net sınırlar çizer ve gelecekte servis ayırımı gerekirse refactor maliyetini düşürür.

### Karar Çerçevesi

| Kriter | Monolit (✓) | Mikroservis |
|--------|------------|-------------|
| Takım büyüklüğü | 1-3 kişi | 5+ takım |
| Trafik | <100 RPS sürekli | >1K RPS sürekli |
| Servis sayısı | 1 backend yeterli | Bağımsız ölçeklenecek 3+ alan |
| Karmaşıklık bütçesi | Düşük | Yüksek (k8s + service mesh + observability) |

KFinans tüm "monolit ✓" kriterlerine uyuyor; ölçek değişene kadar bu mimaride kalınacak.

---

## 2. Yüksek Seviyeli Mimari

```
┌──────────────────────────────────────────────────────────────────┐
│                         İstemci Katmanı                          │
│   ┌────────────────┐                       ┌─────────────────┐   │
│   │  Next.js Web   │                       │ Flutter Android │   │
│   │  app.kfinans.x │                       │  (Play Store)   │   │
│   └────────┬───────┘                       └────────┬────────┘   │
└────────────┼────────────────────────────────────────┼────────────┘
             │ HTTPS / REST (api.kfinans.x)           │
┌────────────▼─────────────────────────────────────────▼───────────┐
│                       Kubernetes Cluster                          │
│                       namespace: kfinans                          │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │           nginx-ingress + cert-manager                  │    │
│   │   api.kfinans.x → backend-svc:80                        │    │
│   │   app.kfinans.x → frontend-svc:80                       │    │
│   └────────┬───────────────────────┬──────────────────────-─┘    │
│            │                        │                             │
│   ┌────────▼─────────┐    ┌────────▼─────────┐                   │
│   │  backend Deploy  │    │ frontend Deploy  │                   │
│   │  FastAPI+uvicorn │    │  Next.js (SSR)   │                   │
│   │  replicas: 2     │    │  replicas: 2     │                   │
│   └────────┬─────────┘    └──────────────────┘                   │
│            │                                                      │
│   ┌────────▼─────────────────────────────────────────────┐       │
│   │  PostgreSQL StatefulSet (bitnami/postgresql Helm)   │       │
│   │  Persistent Volume Claim (50Gi)                     │       │
│   └─────────────────────────────────────────────────────┘       │
│                                                                   │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  APScheduler (AsyncIOScheduler, backend pod içinde)  │       │
│   │  Europe/Istanbul, Pazar 23:00 (CronTrigger)          │       │
│   │  → services/snapshot.py::compute_and_save_snapshot() │       │
│   │  → portfolio_snapshots + asset_positions             │       │
│   └──────────────────────────────────────────────────────┘       │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTPS (giden trafik)
       ┌──────────────────────────────────────────┐
       │  Anthropic API (Claude)                  │
       │  Binance, iCrypex (CCXT)                 │
       │  Sonic/Avalanche/Ethereum RPC            │
       │  Yahoo Finance, TEFAS                    │
       │  iyzico ödeme (Faz 3)                    │
       └──────────────────────────────────────────┘
```

---

## 3. Backend İç Yapısı (Modüler Monolit)

```
backend/app/
├── main.py                # FastAPI app, lifespan, CORS, slowapi, /health
├── config.py              # pydantic-settings (Settings class)
├── scheduler.py           # APScheduler — Pazar 23:00 haftalık snapshot
│
├── api/v1/                # HTTP arayüz katmanı
│   ├── router.py          # Tüm router'ları birleştirir
│   ├── auth.py            # /auth (login, register, refresh, logout, verify-email, resend-verification) + rate limit + JWT blacklist
│   ├── portfolio.py       # /portfolio (snapshot, crypto, wallets, staking) + POST /snapshot manuel tetik
│   ├── tefas.py           # /portfolio/tefas/* (CRUD + Excel)
│   ├── stocks.py          # /portfolio/stocks/* (CRUD + Excel)
│   ├── bes.py             # /portfolio/bes/* (manuel giriş + Excel)
│   ├── wallets.py         # /wallets (blockchain adres CRUD + Excel)
│   ├── integrations.py    # /integrations (exchange API key)
│   └── advice.py          # /advice (AI tavsiye — Faz 3'te kredi tüketir)
│
├── core/                  # Çekirdek altyapı
│   ├── deps.py            # get_db, get_current_user (RevokedToken jti kontrolü dahil)
│   ├── security.py        # JWT (jti=uuid4.hex), bcrypt, Fernet encrypt/decrypt
│   └── limiter.py         # slowapi Limiter (paylaşılan instance)
│
├── services/              # İş mantığı katmanı
│   ├── exchange/
│   │   ├── base.py        # BaseExchangeIntegration
│   │   ├── binance.py     # CCXT wrapper
│   │   ├── binancetr.py   # Session token (cid cookie) ile özel istemci
│   │   └── icrypex.py     # CCXT wrapper
│   ├── blockchain/
│   │   ├── sonic.py       # SFC staking contract, Semaphore(20) paralel
│   │   ├── avalanche.py   # P-Chain (REST) + C-Chain (EVM)
│   │   └── ethereum.py    # EVM RPC + Etherscan
│   ├── tefas.py           # TefasService (httpx + JSON API)
│   ├── stocks.py          # Yahoo Finance Chart API
│   ├── aggregator.py      # TL normalize, USD/TRY kuru, calculate_changes/breakdown
│   ├── snapshot.py        # compute_and_save_snapshot() — tüm kaynakları paralel toplayıp DB'ye yazar (TEFAS, kripto, blockchain, hisse, BES)
│   ├── email.py           # Resend SDK — verify_email + HTML şablon
│   └── advisor.py         # Anthropic SDK — model + max_tokens settings'ten
│
├── models/                # SQLAlchemy ORM
│   ├── user.py            # users (+ credit_balance, email_verified)
│   ├── integration.py     # integrations + wallet_addresses
│   ├── tefas.py           # tefas_holdings
│   ├── stock.py           # stock_holdings
│   ├── bes.py             # bes_holdings (plan_name, total_value_tl)
│   ├── revoked_token.py   # revoked_tokens (jti PK, JWT blacklist)
│   ├── portfolio.py       # portfolio_snapshots + asset_positions
│   ├── advice.py          # investment_advice
│   └── credit.py          # credit_transactions (Faz 3)
│
└── schemas/               # Pydantic — request/response sözleşmeleri
    ├── auth.py            # RegisterRequest, LoginRequest, RefreshRequest, LogoutRequest
    ├── portfolio.py       # SnapshotOut, PortfolioChanges, CryptoPositionOut, WalletPositionOut
    ├── tefas.py           # TefasHolding, TefasPositionOut
    ├── stocks.py          # StockHolding, StockPositionOut
    ├── bes.py             # BesHolding (plan_name, total_value_tl)
    └── integration.py
```

### Katman Sınırları

```
api/v1/         ← HTTP istekleri, validation, response model
   ↓
services/       ← İş mantığı, dış API çağrıları
   ↓
models/         ← Veritabanı erişimi (SQLAlchemy)
```

**Kural:** `models/` `services/`'i, `services/` `api/`'yi import edemez (bağımlılık tek yönlü).

---

## 4. Veri Akışı

### 4.1 Anlık Pozisyon Sorgulama (Cache yok, gerçek zamanlı)

```
GET /api/v1/portfolio/crypto
  ↓
api/v1/portfolio.py: get_crypto_positions()
  ↓
SELECT integrations WHERE user_id=X AND is_active
  ↓
For each integration (paralel: asyncio.gather):
  decrypt_secret(encrypted_key) → API key
  BinanceService.fetch() → Asset list
  ↓
fetch_usd_to_tl() → güncel kur
  ↓
Her asset için: total_value_tl = (liquid + staked) * unit_price_usd * usd_tl
  ↓
JSON response
```

### 4.2 Haftalık Snapshot (APScheduler — implement edildi)

```
Her Pazar 23:00 (Europe/Istanbul)
  ↓ AsyncIOScheduler + CronTrigger(day_of_week='sun', hour=23, minute=0)
  ↓ misfire_grace_time=3600s (pod restart toleransı)
  ↓
Tüm aktif kullanıcılar için döngü:
  ↓
services/snapshot.py::compute_and_save_snapshot(user_id, db)
  ↓ asyncio.gather (paralel, hata izolasyonu):
  ├── Binance (CCXT)
  ├── Binance TR (session token)
  ├── iCrypex (CCXT)
  ├── Sonic (web3 + SFC)
  ├── Avalanche P-Chain (REST)
  ├── Avalanche C-Chain (web3)
  ├── Ethereum (web3 + Etherscan)
  ├── TEFAS (httpx)
  ├── Hisse senedi (Yahoo Finance)
  └── BES (DB — manuel giriş, _gather_bes_assets())
  ↓
fetch_usd_to_tl() (TCMB → exchangerate-api fallback)
fetch_gbp_to_usd() (TCMB derive → exchangerate-api fallback) — opsiyonel
TL normalize (aggregator.calculate_breakdown)
  ↓ İdempotent: aynı gün eskiyi DELETE → yeniyi INSERT
INSERT portfolio_snapshots (user_id, snapshot_date, total_value_tl)
INSERT asset_positions (snapshot_id, source_type, asset_type, ...)
  ↓
calculate_changes() WoW/MoM hesaplaması bu tablo üzerinden
```

**Manuel tetikleme:** `POST /api/v1/portfolio/snapshot` — aynı `compute_and_save_snapshot()` fonksiyonunu çağırır (test/UI için). Frontend dashboard'da "Snapshot al" butonu mevcut.

**Hata izolasyonu:** Bir kaynak fail olursa (örn. Binance timeout), diğer kaynaklar devam eder; başarısız kaynak loglanır. Tüm kaynaklar fail olursa snapshot yazılmaz, 502 döner.

**Döviz kuru:** `aggregator.py` `asyncio.gather(..., return_exceptions=True)` ile USD/TL ve GBP/USD ayrı ayrı kontrol edilir.
- **USD/TL kritik:** TCMB → exchangerate-api → ikisi de fail ise `RuntimeError` → snapshot iptal (503).
- **GBP/USD opsiyonel:** Aynı zincir; fail ise 0 ile devam (UK hisseleri 0 değer, log warning).
- TCMB XML'i 5 dakika in-memory cache'lenir; aynı snapshot içinde tekrar HTTP çağrısı yapılmaz.

### 4.3 Kullanıcı Kayıt + E-posta Doğrulama Akışı

```
POST /auth/register {email, password, risk_profile}
  ↓ bcrypt(password)
  ↓ secrets.token_urlsafe(32) → verify_token
  ↓ INSERT users (email_verified=False, verify_token, verify_token_expires_at=now+24h)
  ↓ services/email.py::send_verification_email() — Resend SDK + HTML şablon
  ↓ 201 Created (mail fail olsa bile user oluşur)

GET /auth/verify-email?token=...
  ↓ SELECT users WHERE verify_token=? AND verify_token_expires_at > now()
  ↓ UPDATE users SET email_verified=True, verify_token=NULL
  ↓ 200 OK

POST /auth/login (email_verified=False ise)
  ↓ verify_password OK
  ↓ user.email_verified == False → 403 hard block
  ↓ "E-posta adresiniz henüz doğrulanmadı..."

POST /auth/resend-verification {email}
  ↓ Her zaman 202 (bilgi sızdırmamak için)
  ↓ Eğer user mevcut ve doğrulanmamışsa: yeni token + mail gönder
```

### 4.4 Logout + Token İptali (JWT Blacklist)

```
POST /auth/logout {refresh_token?}   (Authorization: Bearer <access>)
  ↓ get_current_user(access) → user (zaten doğrulandı)
  ↓ INSERT revoked_tokens (jti, user_id, token_type='access', expires_at)
  ↓ Eğer body'de refresh varsa ve sub eşleşiyorsa:
  ↓   INSERT revoked_tokens (jti, user_id, token_type='refresh', expires_at)
  ↓ PK çakışmasında rollback (idempotent)
  ↓ Bozuk refresh → sessizce yutulur (bilgi sızdırma yok)
  ↓ 200 OK { "message": "Çıkış yapıldı" }

Sonraki istek (Authorization: Bearer <iptal-edilmiş-access>):
  ↓ decode_token() OK
  ↓ get_current_user: SELECT 1 FROM revoked_tokens WHERE jti=?
  ↓ Bulunduysa → 401
  ↓ (Eski jti'siz tokenlar geriye dönük uyumlu — jti yoksa kontrol atlanır)

POST /auth/refresh {refresh_token=<iptal-edilmiş>}
  ↓ decode_token() OK
  ↓ jti blacklist'te → 401 "Token iptal edilmiş"
```

---

## 5. Veritabanı Şeması

### 5.1 Genel Kurallar
- Tüm primary key'ler **UUID** (`gen_random_uuid()` PostgreSQL default)
- Tüm timestamp'ler **timezone-aware** (`TIMESTAMPTZ`)
- Para tutarları **NUMERIC** (asla FLOAT) — kayıp kabul edilmez
- Soft delete yok (Faz 3'te `deleted_at` eklenecek — KVKK 30 gün bekleme için)

### 5.2 Tablolar

#### `users`
```sql
id                       UUID PRIMARY KEY DEFAULT gen_random_uuid()
email                    TEXT UNIQUE NOT NULL
password_hash            TEXT NOT NULL                    -- bcrypt
risk_profile             TEXT                              -- 'conservative'|'balanced'|'aggressive'
credit_balance           INT NOT NULL DEFAULT 0           -- CHECK (credit_balance >= 0)
email_verified           BOOLEAN NOT NULL DEFAULT FALSE
verify_token             TEXT                              -- e-posta doğrulama tokeni (secrets.token_urlsafe(32))
verify_token_expires_at  TIMESTAMPTZ                       -- token ömrü (default 24 saat)
deleted_at               TIMESTAMPTZ                       -- soft delete (Faz 3'te aktif)
created_at               TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_users_email (email)
INDEX ix_users_verify_token (verify_token)
```

#### `integrations` (Exchange API key'ler)
```sql
id               UUID PK
user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
provider         TEXT NOT NULL                   -- 'binance'|'binancetr'|'icrypex'
encrypted_key    TEXT NOT NULL                   -- Fernet
encrypted_secret TEXT                             -- Fernet
encrypted_extra  TEXT                             -- Fernet — Binance TR session token
is_active        BOOLEAN NOT NULL DEFAULT TRUE
last_synced_at   TIMESTAMPTZ
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_integrations_user_id (user_id)
UNIQUE (user_id, provider)
```

#### `wallet_addresses` (Blockchain cüzdanları)
```sql
id         UUID PK
user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
chain      TEXT NOT NULL                         -- 'sonic'|'avalanche_p'|'avalanche_c'|'ethereum'
address    TEXT NOT NULL
label      TEXT
is_active  BOOLEAN NOT NULL DEFAULT TRUE
created_at TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (user_id, chain, address)
INDEX ix_wallet_addresses_user_id (user_id)
```

#### `tefas_holdings`
```sql
id       UUID PK
user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
code     VARCHAR(10) NOT NULL                    -- 'GO3', 'TI2' vb.
quantity NUMERIC(20, 8) NOT NULL
name     TEXT NOT NULL DEFAULT ''

INDEX ix_tefas_holdings_user_id (user_id)
```

#### `stock_holdings`
```sql
id       UUID PK
user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
ticker   VARCHAR(20) NOT NULL                    -- 'THYAO.IS', 'AAPL', 'BP.L'
quantity NUMERIC(20, 8) NOT NULL
name     TEXT NOT NULL DEFAULT ''

INDEX ix_stock_holdings_user_id (user_id)
```

> Hisse fiyatları **DB'de saklanmaz**. Her preview/dashboard isteğinde Yahoo Finance'tan çekilir; TRY dışı fiyatlar Binance USDTTRY kuru ile normalize edilir.

#### `bes_holdings`
```sql
id              UUID PK
user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
plan_name       VARCHAR(200) NOT NULL                  -- 'AgeSA Klasik' vb.
total_value_tl  NUMERIC(18, 2) NOT NULL CHECK (total_value_tl >= 0)

INDEX ix_bes_holdings_user_id (user_id)
```

> BES manuel giriştir; otomatik scraping yok. Snapshot servisi `_gather_bes_assets()` ile her kaydı `asset_type="pension"`, `provider="bes"`, `source_type="bes"`, `liquid_quantity=1`, `unit_price_tl=total_value_tl` olacak şekilde `AssetData`'ya dönüştürür.

#### `revoked_tokens` (JWT blacklist)
```sql
jti          TEXT PRIMARY KEY                       -- JWT'nin jti claim'i (uuid4.hex)
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
token_type   TEXT NOT NULL                          -- 'access' | 'refresh'
expires_at   TIMESTAMPTZ NOT NULL                   -- token doğal son kullanma; cleanup job için
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_revoked_tokens_expires_at (expires_at)
```

> `POST /auth/logout` access (zorunlu) ve refresh (opsiyonel) tokenları bu tabloya yazar. `get_current_user` decode sonrası `jti`'yi sorgular; blacklist'teyse 401. PK çakışmasında rollback ile sessiz idempotency (aynı token tekrar logout edilirse hata değil — ikinci `get_current_user` zaten 401 döndürür). Eski (jti'siz) tokenlar geriye dönük uyumlu — `jti` yoksa kontrol atlanır. Cleanup için `expires_at` index'i kullanılır (Faz 3 cron job).

#### `portfolio_snapshots` + `asset_positions`
```sql
portfolio_snapshots
  id              UUID PK
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  snapshot_date   DATE NOT NULL
  total_value_tl  NUMERIC(18, 2) NOT NULL
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

  UNIQUE (user_id, snapshot_date)
  INDEX ix_portfolio_snapshots_user_date (user_id, snapshot_date DESC)

asset_positions
  id                UUID PK
  snapshot_id       UUID NOT NULL REFERENCES portfolio_snapshots(id) ON DELETE CASCADE
  source_type       TEXT NOT NULL  -- 'exchange'|'blockchain'|'fund'|'manual'
  provider          TEXT NOT NULL  -- 'binance', 'sonic', 'tefas' vb.
  asset_type        TEXT NOT NULL  -- 'crypto'|'staked_crypto'|'fund'|'pension'|'cash'|'manual'
  symbol            TEXT NOT NULL
  name              TEXT NOT NULL
  liquid_quantity   NUMERIC(28, 8) NOT NULL
  staked_quantity   NUMERIC(28, 8) NOT NULL DEFAULT 0
  pending_rewards   NUMERIC(28, 8) NOT NULL DEFAULT 0
  unit_price_tl     NUMERIC(18, 4) NOT NULL
  total_value_tl    NUMERIC(18, 2) NOT NULL
  weight_pct        NUMERIC(5, 2) NOT NULL
  wallet_address_id UUID REFERENCES wallet_addresses(id) ON DELETE SET NULL

  INDEX ix_asset_positions_snapshot_id (snapshot_id)
```

#### `investment_advice` (AI tavsiyeler)
```sql
id                UUID PK
user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
snapshot_id       UUID REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
horizon           TEXT NOT NULL                  -- 'medium'|'long'
content           TEXT NOT NULL                  -- Markdown
credits_used      INT NOT NULL                   -- 5 (medium) | 10 (long)
prompt_tokens     INT NOT NULL
completion_tokens INT NOT NULL
generated_at      TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_investment_advice_user_id (user_id)
```

#### `credit_transactions` (Faz 3 — henüz yok)
```sql
id           UUID PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT
amount       INT NOT NULL                        -- pozitif: yükleme, negatif: kullanım
reason       TEXT NOT NULL                       -- 'purchase'|'ai_advice_medium'|'crypto_sync'
reference_id TEXT                                 -- iyzico/Stripe işlem ID
idempotency_key TEXT UNIQUE                       -- çift ödeme koruması
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_credit_transactions_user_id (user_id)
INDEX ix_credit_transactions_created_at (created_at DESC)
```

> Detaylı kredi sistemi: [kredi-sistemi.md](./kredi-sistemi.md)

---

## 6. Mevcut Migration'lar

| Revision | Açıklama |
|----------|----------|
| `876bd62e282c` | İlk şema (users, integrations, wallet_addresses, portfolio_snapshots, asset_positions, investment_advice) |
| `a1b2c3d4e5f6` | `tefas_holdings` tablosu |
| `b2c3d4e5f6a7` | `integrations.encrypted_extra` kolonu (Binance TR session token) |
| `c3d4e5f6a7b8` | `stock_holdings` tablosu |
| `d4e5f6a7b8c9` | ✅ `users` lifecycle kolonları: `email_verified`, `verify_token`, `deleted_at`, `credit_balance` (CHECK >=0) |
| `e5f6a7b8c9d0` | ✅ `investment_advice.credits_used` kolonu |
| `f6a7b8c9d0e1` | ✅ Performans index'leri + `integrations(user_id, provider)` UNIQUE |
| `9a8b7c6d5e4f` | ✅ `users.verify_token_expires_at` + `ix_users_verify_token` |
| `1f2e3d4c5b6a` | ✅ `bes_holdings` tablosu (plan_name, total_value_tl) + `ix_bes_holdings_user_id` |
| `2a3b4c5d6e7f` | ✅ `revoked_tokens` tablosu (jti PK, user_id, token_type, expires_at) + `ix_revoked_tokens_expires_at` (JWT blacklist) |

### Mevcut Index'ler
- `ix_users_email` (UNIQUE)
- `ix_users_verify_token`
- `ix_integrations_user_id`
- `ix_wallet_addresses_user_id`
- `ix_tefas_holdings_user_id`
- `ix_stock_holdings_user_id`
- `ix_bes_holdings_user_id`
- `ix_revoked_tokens_expires_at`
- `ix_investment_advice_user_id`
- `ix_portfolio_snapshots_user_date` (user_id + snapshot_date DESC)
- `ix_asset_positions_snapshot_id`
- `uq_integrations_user_provider` (UNIQUE)
- `uq_snapshot_user_date` (UNIQUE)
- `uq_wallet_user_chain_address` (UNIQUE)

### Eksik (Faz 2-3'te Yapılacak)
- [ ] `credit_transactions` tablosu (Faz 3 — kredi sistemi)
- [ ] `expense_categories` + `expenses` tabloları (Faz 3 — harcama takibi)
- [ ] `audit_logs` tablosu (Faz 3 — KVKK uyum)
- [x] `revoked_tokens` tablosu (Faz 2 — JWT blacklist) — migration `2a3b4c5d6e7f` ile eklendi
- [ ] `revoked_tokens` cleanup cron job (`expires_at < now()` olanları sil — Faz 3)
- [ ] Soft delete cron — 30 gün sonra hard delete

---

## 7. Veri Kaynakları ve Servisler

### 7.1 BaseIntegration Pattern

Her dış veri kaynağı `services/` altında `BaseIntegration` (veya `BaseExchangeIntegration`) sınıfından türer ve `async def fetch()` metodunu implement eder. Dönen veri **standart `Asset` veri yapısı** ile normalize edilir.

```python
# Standart Asset şeması
@dataclass
class Asset:
    provider: str          # 'binance', 'sonic' vb.
    symbol: str            # 'BTC', 'AVAX'
    name: str
    liquid_quantity: Decimal
    staked_quantity: Decimal
    pending_rewards: Decimal
    unit_price_usd: Decimal
```

### 7.2 Servis Detayları

| Servis | Sınıf | Notlar |
|--------|-------|--------|
| Binance | `BinanceService` | CCXT, fetch_balance + savings/locked |
| Binance TR | `BinanceTRService` | Özel istemci, session token (cid cookie); GeeTest CAPTCHA nedeniyle programatik login YOK |
| iCrypex | `ICrypexService` | CCXT wrapper |
| Sonic | `SonicService` | web3.py + SFC staking contract; `Semaphore(20)` ile paralel validator sorgu |
| Avalanche P-Chain | `AvalanchePChainService` | `platform.getStake` REST API, httpx |
| Avalanche C-Chain | `AvalancheCChainService` | EVM RPC, web3.py |
| Ethereum | `EthereumService` | EVM RPC + Etherscan |
| TEFAS | `TefasService` | httpx + JSON API |
| Yahoo Finance | `fetch_stock_quotes()` | httpx (`v8/finance/chart/{ticker}`) |
| BES | `_gather_bes_assets()` (snapshot.py içinde) | DB'den okur — `bes_holdings` → `AssetData(asset_type="pension", provider="bes")` |
| Aggregator | `aggregator.py` | `fetch_usd_to_tl`, `fetch_gbp_to_usd`, `fetch_spot_prices`, `calculate_changes`, `calculate_breakdown` — TCMB primary + exchangerate-api fallback, 5 dk in-memory TCMB cache |
| Snapshot | `snapshot.py::compute_and_save_snapshot()` | Tüm kaynakları paralel topla (BES dahil), TL normalize, DB'ye yaz (idempotent) |
| E-posta | `email.py::send_verification_email()` | Resend SDK + HTML şablon |

> Detaylı API entegrasyon mantığı, prompt'lar, hata yönetimi: [api-referansi.md](./api-referansi.md), [ai-ve-finans.md](./ai-ve-finans.md)

### 7.3 E-posta Servisi (Resend)

`services/email.py` Resend SDK ile HTML mail gönderir. Kullanım: kullanıcı kaydı sonrası doğrulama linki, yeniden gönderim.

**Env değişkenleri:**
```
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@kfinans.app
FRONTEND_URL=https://app.kfinans.app    # Verify linki için (host)
VERIFY_TOKEN_EXPIRE_HOURS=24
```

**Şablon:** `send_verification_email(to_email, verify_token)` — `{FRONTEND_URL}/verify-email?token={token}` linki ile HTML mail. Hata durumunda exception fırlatmaz, loglar (kullanıcı kaydı bloklamamak için).

---

## 8. Performans ve Ölçeklenebilirlik

### 8.1 Mevcut Bottleneck'ler
- **Anlık fiyat çekimi:** Her dashboard render'ı dış API çağrısı yapıyor → cache eklenmeli (Redis veya in-memory TTL)
- **Sonic SFC validator sorgusu:** ~20 validator için Semaphore(20) paralel — daha fazlası rate limit riski
- **Crypto fetch'ler sıralı integration için:** `asyncio.gather` ile paralelleştirilebilir

### 8.2 İyileştirme Önerileri (Faz 3 Önce)
- ✅ USD/TRY ve GBP/USD için 5 dk in-memory TCMB cache (Faz 2 — tamamlandı)
- TEFAS fiyatları için günlük cache (gün içinde değişmez)
- Yahoo Finance quotes için 5 dakika cache
- PostgreSQL connection pool: `pool_size=10, max_overflow=20` (default'tan artır)

---

## 9. Dış Bağımlılıklar (Failure Modes)

| Servis | Failure Etkisi | Mitigation |
|--------|----------------|------------|
| Binance API | Kripto pozisyon görünmez | Try/except + errors response field |
| Sonic RPC | Sonic cüzdan görünmez | Per-wallet error tracking |
| TEFAS API | Fon fiyatı eski kalır | Last known price gösterilir |
| Yahoo Finance | Hisse fiyatı yok | 422 + ticker doğrulama uyarısı |
| Anthropic API | Tavsiye üretilmez | Kredi tüketilmez (transaction rollback) |
| iyzico | Ödeme alınmaz | İdempotency + retry; Stripe fallback (Faz 4) |
| PostgreSQL | Sistem çöker | StatefulSet replikası + PITR backup (Faz 3) |

---

## 10. Mimari Değişiklik Kontrol Listesi

Yeni özellik / refactor öncesi şunları kontrol et:
- [ ] Yeni servis `BaseIntegration` pattern'ine uyuyor mu?
- [ ] DB migration eklendi mi (Alembic)?
- [ ] Yeni endpoint'te `response_model` ve `status_code` belirli mi?
- [ ] Inline Pydantic model yok, `schemas/` altında mı?
- [ ] Auth gerekli mi? `Depends(get_current_user)` var mı?
- [ ] Rate limit gerekli mi? `@limiter.limit(...)` eklendi mi?
- [ ] Logging eklendi mi (önemli olaylar için)?
- [ ] Index gerekecek query'ler için DBA'ya danışıldı mı?
