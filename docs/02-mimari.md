# Sistem Mimarisi ve Veritabanı Şeması

**Sahip ajanlar:** `architect`, `dba`
**İlgili dokümanlar:** [api-referansi.md](./api-referansi.md), [altyapi-test.md](./altyapi-test.md)

---

## 1. Mimari Felsefe

KFinans **modüler monolit** mimarisi kullanır. Mevcut ölçekte (Faz 1-3 hedef: ~10K kullanıcı) mikroservis karmaşıklığı (service mesh, distributed tracing, inter-service auth) gereksizdir. Modüler yapı kod içinde net sınırlar çizer ve gelecekte servis ayırımı gerekirse refactor maliyetini düşürür.

### Karar Çerçevesi

| Kriter              | Monolit (✓)       | Mikroservis                                 |
| ------------------- | ----------------- | ------------------------------------------- |
| Takım büyüklüğü     | 1-3 kişi          | 5+ takım                                    |
| Trafik              | <100 RPS sürekli  | >1K RPS sürekli                             |
| Servis sayısı       | 1 backend yeterli | Bağımsız ölçeklenecek 3+ alan               |
| Karmaşıklık bütçesi | Düşük             | Yüksek (k8s + service mesh + observability) |

KFinans tüm "monolit ✓" kriterlerine uyuyor; ölçek değişene kadar bu mimaride kalınacak.

---

## 2. Yüksek Seviyeli Mimari

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         İstemci Katmanı                                 │
│   ┌──────────────┐    ┌──────────────┐         ┌────────────────────┐  │
│   │  Next.js Web │    │ Flutter Mobile│         │  MCP Server        │  │
│   │ app.kfinans.x│    │ Android + iOS │         │ (Claude Desktop /  │  │
│   │   (Faz 1-3)  │    │   (Faz 4)     │         │  Workbench/Cursor) │  │
│   │              │    │               │         │     (Faz 5)        │  │
│   └──────┬───────┘    └───────┬───────┘         └─────────┬──────────┘  │
└──────────┼────────────────────┼───────────────────────────┼─────────────┘
           │ HTTPS / REST (api.kfinans.x)                   │ MCP/stdio
           ▼                    ▼                           ▼ (mcp-key auth)
┌─────────────────────────────────────────────────────────────────────────┐
│                       Kubernetes Cluster                                │
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
│   │  Europe/Istanbul — 4 cron job (advisory-lock leader): │       │
│   │   • Pazar 23:00 → snapshot.compute_and_save_snapshot()│       │
│   │   • 03:00 revoked_tokens cleanup                      │       │
│   │   • 04:00 hard-delete (30 gün soft-delete, KVKK)      │       │
│   │   • 04:30 audit_logs purge (365 gün retention)        │       │
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

> **K8s manifest'leri:** `k8s/` klasöründe (namespace, configmap, postgres StatefulSet, backend/frontend Deployment, nginx-ingress + cert-manager, kustomization). Deploy rehberi ve önkoşullar: [`k8s/README.md`](../k8s/README.md). Tek komut: `kubectl apply -k k8s/`.

---

## 3. Backend İç Yapısı (Modüler Monolit)

```
backend/app/
├── main.py                # FastAPI app, lifespan, CORS, slowapi, /health, SecurityHeaders + TrustedHost + RequestTiming middleware, generic exception handlers
├── config.py              # pydantic-settings (Settings class)
├── scheduler.py           # APScheduler — 4 cron job (Europe/Istanbul): Pazar 23:00 snapshot, 03:00 revoked_tokens cleanup, 04:00 hard-delete (KVKK), 04:30 audit_logs purge; pg_try_advisory_lock leader election
├── observability.py       # Sentry + OpenTelemetry init (opt-in)
│
├── api/v1/                # HTTP arayüz katmanı (23 router)
│   ├── router.py          # Tüm router'ları birleştirir
│   ├── auth.py            # /auth (login, register, refresh, logout, verify-email, resend-verification) + rate limit + JWT blacklist + refresh rotation + MFA login flow
│   ├── mfa.py             # /mfa (setup, enable, verify, disable) — TOTP RFC 6238
│   ├── user.py            # /user (me, profile, password, soft-delete) — Faz 3
│   ├── metrics.py         # /metrics/performance (X-Metrics-Token korumalı, p50/p95/p99 — PERF-004)
│   ├── portfolio.py       # /portfolio (snapshot, crypto, wallets, staking) + POST /snapshot manuel tetik
│   ├── tefas.py           # /portfolio/tefas/* (CRUD + Excel + import-mkk)
│   ├── stocks.py          # /portfolio/stocks/* (CRUD + Excel + import-mkk)
│   ├── bes.py             # /portfolio/bes/* (manuel giriş + Excel)
│   ├── commodity.py       # /portfolio/commodities/* (altın/gümüş — gram/BiGA/sikke + Excel) — Faz 3
│   ├── wallets.py         # /wallets (blockchain adres CRUD + Excel)
│   ├── integrations.py    # /integrations (exchange API key)
│   ├── expenses.py        # /expenses (manuel harcama CRUD + summary + Excel) — Faz 3 MVP
│   ├── planned_expenses.py # /planned-expenses (CRUD + 12 aylık tahmin) — Faz 3
│   ├── income.py          # /income (gelir CRUD + summary + Excel) — Faz 3
│   ├── budget.py          # /budgets (UPSERT + comparison) — Faz 3
│   ├── goal.py            # /goals/me (finansal hedef + para birimi) — Faz 3
│   ├── manual_crypto.py   # /manual-crypto (API'siz borsalar için manuel CRUD + Excel + anlık fiyat)
│   ├── cash.py            # /cash (nakit/banka hesabı CRUD, USD/EUR/GBP→TRY)
│   ├── cash_flow.py       # /cash-flow (12 aylık nakit akış projeksiyonu + Excel/PDF rapor)
│   ├── credit_cards.py    # /credit-cards (kart + ekstre + taksit nested CRUD)
│   ├── asset_catalog.py   # /asset-catalog (manuel kripto autocomplete: commodity/binance/coingecko/tefas)
│   ├── audit_logs.py      # /audit-logs (kullanıcı kendi log'ları, IDOR korumalı — FAZ C6)
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
│   │   ├── avalanche.py   # P-Chain (REST) + C-Chain (EVM, multi-RPC fallback)
│   │   ├── ethereum.py    # EVM RPC (multi-RPC fallback) + Etherscan + Ethplorer ERC-20 discovery
│   │   ├── bitcoin.py     # mempool.space (UTXO chain_stats) + xpub HD (bip-utils) + 10 dk cache + single-flight
│   │   ├── solana.py      # JSON-RPC `getBalance` + `getProgramAccounts` (Stake program filter offset 12=staker, 44=withdrawer) + 10 dk cache + single-flight + 429 retry/backoff
│   │   ├── algorand.py    # Algonode public API (`/v2/accounts/{addr}`) — native ALGO + pending rewards
│   │   ├── litecoin.py    # litecoinspace.org + Ltub→xpub version-byte swap (base58check) + bip-utils derivation + cache/single-flight
│   │   ├── cardano.py     # Koios `/account_info` ile stake1 üzerinden toplam — addr1 girilirse Bech32 ile içinden stake1 türetilir (utxo + rewards_available)
│   │   ├── polkadot.py    # substrate-interface ile Relay Chain + Asset Hub paralel sorgu (System.Account.data: free/reserved); spot DOT artık Asset Hub'da
│   │   └── evm_tokens.py  # ERC-20 discovery: Ethplorer (ETH dinamik) + curated AVAX list + spam filter
│   ├── tefas.py           # TefasService (httpx + JSON API)
│   ├── stocks.py          # Yahoo Finance Chart API
│   ├── commodity.py       # Altın/Gümüş — TCMB USD/TRY + Yahoo XAU/XAG fallback chain + 5 dk cache
│   ├── aggregator.py      # TL normalize, USD/TRY kuru, calculate_changes/breakdown
│   ├── snapshot.py        # compute_and_save_snapshot() — tüm kaynakları paralel toplayıp DB'ye yazar (TEFAS, kripto, blockchain, hisse, BES, kıymetli madenler, nakit). Her gather fonksiyonu issues listesine fail/0-değer kaynakları ekler → portfolio_snapshots.health_issues JSONB. usd_try_rate kayıt anındaki TCMB kuru (geçmiş USD eğimi için). MKK import sonrası best-effort tetiklenir
│   ├── email.py           # Resend SDK — verify_email + HTML şablon
│   ├── audit.py           # log_audit() + AuditAction Enum (best-effort — FAZ C6)
│   ├── reports.py         # reportlab + openpyxl — xlsx/pdf rapor üretimi (DejaVu Sans TR font)
│   └── advisor.py         # Anthropic SDK (Claude API) — aktif, prompt cache + SPK disclaimer
│
├── models/                # SQLAlchemy ORM
│   ├── user.py            # users (+ credit_balance, email_verified, deleted_at, goal_amount, goal_currency, anthropic_consent_at/version, totp_secret/enabled/recovery_codes — MFA)
│   ├── integration.py     # integrations + wallet_addresses (xpub Fernet — FAZ C1)
│   ├── tefas.py           # tefas_holdings (+ avg_cost_tl, distributor)
│   ├── stock.py           # stock_holdings (+ avg_cost_tl, distributor)
│   ├── bes.py             # bes_holdings (plan_name, 4 metric: paid_principal/returns, govt_contribution/returns)
│   ├── revoked_token.py   # revoked_tokens (jti PK, JWT blacklist)
│   ├── audit_log.py       # audit_logs (FAZ C6 — forensic)
│   ├── portfolio.py       # portfolio_snapshots (+ health_issues JSONB, usd_try_rate) + asset_positions
│   ├── advice.py          # investment_advice (+ credits_used)
│   ├── expense.py         # expenses (manuel harcama — Faz 3 MVP; + credit_card_id, is_paid)
│   ├── planned_expense.py # planned_expenses (Faz 3)
│   ├── income.py          # incomes (manuel gelir + recurring_income_id FK — Faz 3)
│   ├── recurring_income.py # recurring_incomes (periyodik gelir tahmini + realize — Faz 3)
│   ├── budget.py          # budgets (UPSERT: user_id+category UNIQUE — Faz 3)
│   ├── commodity.py       # commodity_holdings (gram/biga/coin — Faz 3)
│   ├── cash.py            # cash_holdings (nakit/banka — Faz 3)
│   ├── credit_card.py     # credit_cards + credit_card_statements + credit_card_installments (Faz 3)
│   └── manual_crypto.py   # manual_crypto_holdings (API'siz borsalar için manuel kayıt)
│
└── schemas/               # Pydantic — request/response sözleşmeleri
    ├── auth.py            # RegisterRequest, LoginRequest, RefreshRequest, LogoutRequest
    ├── user.py            # UserMeOut, ProfileUpdate, PasswordChange — Faz 3
    ├── portfolio.py       # SnapshotOut, PortfolioChanges, CryptoPositionOut, WalletPositionOut
    ├── tefas.py           # TefasHolding, TefasPositionOut (+ avg_cost_tl + distributor + gain_loss_*)
    ├── stocks.py          # StockHolding, StockPositionOut (+ avg_cost_tl + distributor + gain_loss_*)
    ├── bes.py             # BesHolding (plan_name, 4 metric)
    ├── expense.py         # ExpenseCategory, ExpenseCreate/Update/Out, ExpenseSummary, CategoryBreakdown
    ├── planned_expense.py # PlannedCategory, PlannedRecurrence, PlannedExpenseCreate/Out, PlannedForecast
    ├── income.py          # IncomeCategory (7), IncomeCreate/Update/Out, IncomeSummary
    ├── budget.py          # BudgetUpsert, BudgetOut, BudgetComparison
    ├── commodity.py       # CommodityCreate/Update/Out, CommodityPositionOut, CommoditySummaryOut
    ├── manual_crypto.py   # ManualCryptoCreate/Update/Out, ManualCryptoPositionOut, ManualCryptoSummaryOut
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

> **Wallet pricing tutarlılığı:** `GET /portfolio/wallets` endpoint'i `total_value_tl` hesaplarken `liquid + staked + pending_rewards` toplar (snapshot servisi ile aynı formül). Bu sayede dashboard kartlarındaki "Toplam Portföy" ile haftalık snapshot tutarı arasında pending_rewards farkı (Sonic SFC validator rewards, Avalanche P-Chain pending rewards) oluşmaz.

> **Avalanche P-Chain likit + stake (düzeltme):** `AvalanchePChainService.fetch()` daha önce sadece `platform.getStake` çağırıyordu; bu yüzden delegasyon dışındaki **likit (unlocked) bakiye 0 görünüyordu**. Şimdi `platform.getBalance` + `platform.getStake` paralel çağrılır, adres `P-` prefix'i ile gönderilir (`avax1...` → `P-avax1...`). `unlockeds` (yeni API: assetID→amount mapping) veya `unlocked` (eski API tekil) → `liquid_quantity`; `lockedStakeables` + `staked` → `staked_quantity`. `asset_type` staked > liquid ise `staked_crypto`, değilse `crypto`.

### 4.1.1 Manuel Kripto (API'siz Borsalar) Akışı

API erişimi olmayan borsalar (BinanceTR, iCrypex, BTCTurk, Paribu, Bybit, KuCoin, Bitget vb.) için kullanıcı bakiyelerini elle kaydeder.

```
Kullanıcı → POST /manual-crypto {exchange, symbol, quantity, avg_cost_tl?, notes?}
  ↓ INSERT manual_crypto_holdings
  ↓
GET /manual-crypto
  ↓ SELECT ... WHERE user_id=X
  ↓ aggregator.fetch_spot_prices(symbols)  → Binance USDT spot
  ↓ aggregator.fetch_usd_to_tl()           → TCMB
  ↓ Her kayıt: total_value_tl = quantity * unit_price_usd * usd_tl
  ↓ Bilinmeyen sembol → unknown_symbols listesi (TL=0)
  ↓
Snapshot:
  services/snapshot.py::_gather_manual_crypto_assets()
  → AssetData(asset_type="crypto", provider="manual:{exchange}", liquid_quantity=quantity)
  → fiyat enjekte edilmez; compute_and_save_snapshot()'taki ortak fiyat enrichment loop'u
    (SYMBOL_PRICE_ALIASES dahil) zincir/exchange kayıtlarıyla aynı pipeline'da yakalar
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
  ↓ asyncio.gather + Semaphore(5) (paralel, hata izolasyonu):
  ├── Binance / iCrypex (CCXT)
  ├── Sonic (web3 + SFC), Avalanche P (REST) + C (web3), Ethereum (web3 + Ethplorer)
  ├── Bitcoin (mempool.space), Solana, Cardano, Algorand, Polkadot, Litecoin (public API)
  ├── TEFAS (httpx) + Hisse senedi (Yahoo Finance) + Kıymetli madenler (commodity.py)
  ├── BES (_gather_bes_assets()), Nakit (_gather_cash_assets())
  └── Manuel kripto (_gather_manual_crypto_assets())
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

**Snapshot silme:** `DELETE /api/v1/portfolio/snapshot/{snapshot_date}` — yanlış kaydedilmiş snapshot'ları (timezone bug, hatalı manuel tetik vb.) temizlemek için. Cascade ile `asset_positions` de silinir; `current_user.id` filtresi IDOR koruması sağlar (başka kullanıcının kaydı 404 döner). Frontend `/dashboard/history` sayfasında snapshot listesi + "Sil" butonu (geri alınamaz onay popup'ı) sunulur.

**Snapshot tarihi (timezone):** `snapshot_date` her zaman `Europe/Istanbul` saatine göre belirlenir. Backend Docker container UTC'de çalıştığı için `services/snapshot.py` `date.today()` (UTC tabanlı) yerine `datetime.now(ZoneInfo("Europe/Istanbul")).date()` kullanır. Bu düzeltmeden önce Türkiye saatine göre 00:00–03:00 arası alınan ad-hoc snapshot'lar **bir önceki güne** yazılıyordu (UTC sapması). APScheduler zaten `Europe/Istanbul` ile çalışıyordu; `compute_and_save_snapshot()` fonksiyonundaki tutarsızlık giderildi — scheduler ve manuel tetikleme aynı tarih mantığını paylaşır.

**Hata izolasyonu:** Bir kaynak fail olursa (örn. Binance timeout), diğer kaynaklar devam eder; başarısız kaynak loglanır + `portfolio_snapshots.health_issues` (JSONB) listesine eklenir. Tüm kaynaklar fail olursa snapshot yazılmaz, 502 döner.

**Scheduler — 4 cron job (Europe/Istanbul):** Snapshot (Pazar 23:00) tek job değildir. APScheduler ayrıca her gün `_cleanup_revoked_tokens_job` (03:00, FAZ C5), `_hard_delete_expired_users_job` (04:00, COMP-004 / KVKK m.7), `_purge_old_audit_logs_job` (04:30, COMP-022) çalıştırır. Snapshot job'u multi-replica ortamda `pg_try_advisory_lock` ile leader election yapar (ARC-011 — yalnızca tek pod yürütür); `SCHEDULER_ENABLED=false` ile tamamen kapatılabilir. Snapshot içi paralellik `asyncio.gather + Semaphore(5)` (ARC-003).

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
- Soft delete: `users.deleted_at` (`DELETE /user/me`) + 30 gün sonra hard-delete cron (04:00, COMP-004 / KVKK m.7)

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
deleted_at               TIMESTAMPTZ                       -- soft delete (DELETE /user/me); 30 gün sonra hard-delete cron siler
goal_amount              NUMERIC(18, 2)                   -- finansal hedef (pasif gelir hedefi)
goal_currency            VARCHAR(3) NOT NULL DEFAULT 'TRY' -- 'TRY'|'USD'|'EUR'|'GBP'
anthropic_consent_at     TIMESTAMPTZ                       -- KVKK m.9 açık rıza (AI tavsiye için zorunlu)
anthropic_consent_version VARCHAR(10)                      -- rıza metni sürümü
totp_secret              TEXT                              -- MFA: Fernet ciphertext (plaintext base32)
totp_enabled             BOOLEAN NOT NULL DEFAULT FALSE    -- MFA aktif mi
totp_recovery_codes      TEXT                              -- MFA: JSON list[str], bcrypt-hashed 10 kod
created_at               TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_users_email (email)
INDEX ix_users_verify_token (verify_token)
```

> Migration `6e7f8a9b0c1d` ilk hâli `monthly_expense_goal` ekledi; `7f8a9b0c1d2e` bunu `goal_amount` + `goal_currency` (TRY/USD/EUR/GBP) lehine değiştirdi (mevcut TRY değerleri otomatik taşınır). `DELETE /user/me` `deleted_at = now()` set eder; `_hard_delete_expired_users_job` (04:00) 30 gün geçmiş kayıtları fiziksel siler. `anthropic_consent_*` AI tavsiye KVKK rızası için (migration ile eklendi). `totp_*` kolonları MFA TOTP için (migration `e2f3a4b5c6d7`).

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

#### `wallet_addresses` (Blockchain cüzdanları) — FAZ C1: Fernet encrypted
```sql
id                    UUID PK
user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
chain                 VARCHAR(20) NOT NULL    -- 'bitcoin'|'ethereum'|'sonic'|'avalanche_c'|'avalanche_p'|'solana'|'cardano'|'algorand'|'polkadot'|'litecoin'
address_encrypted     TEXT NOT NULL           -- Fernet ciphertext of plaintext address/xpub
address_fingerprint   VARCHAR(64) NOT NULL    -- SHA-256 hex of lowercase address (lookup + uniqueness)
label                 TEXT
is_active             BOOLEAN NOT NULL DEFAULT TRUE
created_at            TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (user_id, chain, address_fingerprint)   -- case-insensitive (EVM checksum varyasyonları aynı)
INDEX ix_wallet_addresses_user_id (user_id)
INDEX ix_wallet_addresses_fingerprint (address_fingerprint)
```

**Migration `b3c4d5e6f7a8`:** Plaintext `address` kolonu Fernet'e taşındı. `WalletAddress.address` artık Python `@hybrid_property` — getter `decrypt_secret()`, setter `encrypt_secret()` + `address_fingerprint()` hesaplar. Service ve API kodu hiç değişmedi.

**Sebep:** Bitcoin xpub'tan **tüm child public key'ler türetilebilir** (BIP-32 deterministic derivation). DB sızıntısında saldırgan kullanıcının BTC bakiye geçmişini blockchain'den görebilirdi.

#### `tefas_holdings`
```sql
id           BIGSERIAL PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
code         VARCHAR(10) NOT NULL                    -- 'GO3', 'TI2' vb.
quantity     NUMERIC(18, 6) NOT NULL
name         TEXT NOT NULL DEFAULT ''
avg_cost_tl  NUMERIC(18, 6)                          -- TRY/adet ortalama maliyet (nullable; 0 → None)
distributor  VARCHAR(50)                             -- Aracı kurum (örn. 'Ziraat', 'Foneria') — aynı fonun farklı kurumlardan ayrı satırı

INDEX ix_tefas_holdings_user_id (user_id)
```

> Migration `b1c2d3e4f5a6`: `avg_cost_tl` eklendi. Migration `c2d3e4f5a6b7`: `distributor` eklendi. Schema validator: kullanıcı 0 girerse `avg_cost_tl` `None`'a çevrilir (maliyet bilinmiyor).

#### `stock_holdings`
```sql
id           BIGSERIAL PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
ticker       VARCHAR(20) NOT NULL                    -- 'THYAO.IS', 'AAPL', 'BP.L'
quantity     NUMERIC(18, 6) NOT NULL
name         TEXT NOT NULL DEFAULT ''
avg_cost_tl  NUMERIC(18, 6)                          -- TRY/adet ortalama maliyet (nullable; 0 → None)
distributor  VARCHAR(50)                             -- Aracı kurum (örn. 'İş Yatırım', 'Garanti BBVA Yatırım')

INDEX ix_stock_holdings_user_id (user_id)
```

> Hisse fiyatları **DB'de saklanmaz**. Her preview/dashboard isteğinde Yahoo Finance'tan çekilir; TRY dışı fiyatlar TCMB USD/TRY (ve gerekirse GBP/USD) kuru ile normalize edilir. `avg_cost_tl` girilmişse preview response'unda `cost_basis_tl`, `gain_loss_tl`, `gain_loss_pct` döner.

#### `bes_holdings`
```sql
id                  BIGSERIAL PK
user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
plan_name           TEXT NOT NULL                          -- 'AgeSA Klasik' vb.
contract_number     TEXT                                   -- sözleşme no (opsiyonel)
paid_principal      NUMERIC(18, 2) NOT NULL DEFAULT 0       -- yatırılan ana para
paid_returns        NUMERIC(18, 2) NOT NULL DEFAULT 0       -- ana para getirisi
govt_contribution   NUMERIC(18, 2) NOT NULL DEFAULT 0       -- devlet katkısı
govt_returns        NUMERIC(18, 2) NOT NULL DEFAULT 0       -- devlet katkısı getirisi

INDEX ix_bes_holdings_user_id (user_id)
```

> Migration `1f2e3d4c5b6a` (ilk hâl: plan_name + total_value_tl) → `3b4c5d6e7f8a` (4 metric + contract_number; eski `total_value_tl` kolonu kaldırıldı). Toplam değer model property olarak 4 metrik toplamından hesaplanır. BES manuel giriştir; otomatik scraping yok. Snapshot servisi `_gather_bes_assets()` ile her kaydı `asset_type="pension"`, `provider="bes"`, `source_type="bes"`, `liquid_quantity=1`, `unit_price_tl=` 4 metrik toplamı olacak şekilde `AssetData`'ya dönüştürür.

#### `expenses` (Faz 3 MVP — manuel harcama takibi)
```sql
id           UUID PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
amount       NUMERIC(18, 2) NOT NULL CHECK (amount > 0)
category     TEXT NOT NULL                        -- ExpenseCategory enum (10 sabit kategori)
date         DATE NOT NULL
description  VARCHAR(500)
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_expenses_user_date (user_id, date)       -- aylık liste/summary sorguları için
```

> 10 sabit kategori: `food`, `groceries`, `transport`, `bills`, `health`, `entertainment`, `clothing`, `home`, `tax`, `other`. Schema'da `Literal` tipi ile zorlanır; kategori dışı değer 422 döner. `User.expenses` ilişkisi cascade all, delete-orphan.

#### `planned_expenses` (Faz 3 — planlı ödemeler & nakit akışı tahmini)
```sql
id              UUID PK
user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
title           TEXT NOT NULL                         -- ödeme başlığı
amount          NUMERIC(18, 2) NOT NULL CHECK (amount > 0)
is_estimated    BOOLEAN NOT NULL DEFAULT FALSE        -- tahmini tutar bayrağı
category        TEXT NOT NULL                         -- PlannedCategory enum (7 kategori)
recurrence      TEXT NOT NULL                         -- PlannedRecurrence enum (6 tekrar tipi)
months          INTEGER[]                             -- custom recurrence için ay listesi (1-12)
day_of_month    INTEGER                               -- ayın hangi günü (1-31)
start_date      DATE NOT NULL                         -- geçerlilik başlangıcı
end_date        DATE                                  -- geçerlilik sonu (opsiyonel)
remaining_count INTEGER                               -- aylık kredi taksit sayısı; end_date'e otomatik dönüştürülür
notes           VARCHAR(500)                          -- serbest not (opsiyonel)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_planned_expenses_user_id (user_id)
```

> 7 kategori: `loan`, `tax`, `insurance`, `subscription`, `rent`, `utility`, `other`. 6 tekrar tipi: `one_time`, `monthly`, `quarterly`, `biannual`, `yearly`, `custom`. Schema'da `Literal` tipi ile zorlanır. `_applies_in_month()` fonksiyonu `start_date`, `end_date`, `recurrence`, `months` değerlerini birlikte değerlendirerek 12 aylık nakit akışı breakdown'ı üretir. `User.planned_expenses` ilişkisi cascade all, delete-orphan.

#### `incomes` (Faz 3 — manuel gelir takibi)
```sql
id           BIGSERIAL PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
amount       NUMERIC(18, 2) NOT NULL CHECK (amount > 0)
category     VARCHAR(20) NOT NULL                    -- IncomeCategory enum (7 sabit kategori)
date         DATE NOT NULL
description  TEXT
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_incomes_user_date (user_id, date)
```

> 7 kategori: `salary`, `freelance`, `rental`, `dividend`, `bonus`, `sale`, `other`. Şablon `expenses` ile birebir paralel; aylık summary ve Excel import/export desteklenir. `User.incomes` ilişkisi cascade all, delete-orphan.

#### `budgets` (Faz 3 — kategori bazlı aylık bütçe)
```sql
id          BIGSERIAL PK
user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
category    VARCHAR(20) NOT NULL                     -- ExpenseCategory enum (10 kategori)
amount      NUMERIC(18, 2) NOT NULL
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()       -- onupdate=now()

UNIQUE (user_id, category) -- uq_budget_user_category
```

> Migration `9b0c1d2e3f4a`. `PUT /budgets/{category}` PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` ile UPSERT yapar (`uq_budget_user_category` constraint'i hedefler). `GET /budgets/comparison?year=&month=` her kategori için bütçe vs. gerçekleşen + kalan + yüzde + over_budget flag döndürür. `User.budgets` ilişkisi cascade all, delete-orphan.

#### `commodity_holdings` (Faz 3 — altın/gümüş)
```sql
id          BIGSERIAL PK
user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
unit_type   VARCHAR(10) NOT NULL                     -- 'gram'|'biga'|'coin'
metal       VARCHAR(10) NOT NULL                     -- 'gold'|'silver' (sikke için her zaman 'gold')
biga_code   VARCHAR(5)                               -- 'A01'..'A08' (altın), 'G01'..'G07' (gümüş) — sadece unit_type='biga'
coin_type   VARCHAR(20)                              -- 'ceyrek'|'yarim'|'tam'|'cumhuriyet'|'resat'|'ata' — sadece unit_type='coin'
quantity    NUMERIC(18, 4) NOT NULL                  -- gram için gram, BiGA/sikke için adet
notes       TEXT
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_commodity_holdings_user_id (user_id)
```

> Migration `a0b1c2d3e4f5`. Pydantic `model_validator` `unit_type`, `metal`, `biga_code`, `coin_type` uyumunu zorlar. Anlık fiyat: `services/commodity.py::fetch_metal_prices()` TCMB USD/TRY (kritik) + Yahoo Finance XAU=X→GC=F + XAG=X→SI=F fallback. 5 dakikalık in-memory cache; Yahoo fail durumunda TTL 30 saniyeye düşer. Metal fiyatı 0 ise dashboard banner uyarı gösterir, etkilenen pozisyonlar `total_value_tl` toplama dahil edilmez. `User.commodity_holdings` ilişkisi cascade all, delete-orphan.

#### `manual_crypto_holdings` (API'siz borsalar — manuel kripto kayıt)
```sql
id           BIGSERIAL PK
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
exchange     VARCHAR(40) NOT NULL                    -- 'binancetr'|'icrypex'|'btcturk'|'paribu'|'bybit'|'kucoin'|'bitget'|'other'
label        VARCHAR(100)                            -- Opsiyonel kullanıcı etiketi
symbol       VARCHAR(20) NOT NULL                    -- 'BTC', 'AVAX' vb. (otomatik upper-case)
quantity     NUMERIC(28, 12) NOT NULL                -- adet
avg_cost_tl  NUMERIC(18, 6)                          -- TRY/adet ortalama maliyet (nullable; ≤0 → None)
notes        TEXT                                    -- Opsiyonel serbest not
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()      -- onupdate=now()

INDEX ix_manual_crypto_holdings_user_exchange (user_id, exchange)
```

> Migration `f5a6b7c8d9e0`; `a6b7c8d9e0f1` ile `price_source` enum ('auto'/'manual'/'linked') + `manual_unit_price_tl`; `b7c8d9e0f1a2` ile `linked_source` + `linked_id` (asset catalog bağlama). API erişimi olmayan borsalardaki bakiyeleri portföye dahil etmek için. Anlık fiyat: `aggregator.fetch_combined_prices()` (Binance USDT + CoinGecko fallback) + `fetch_usd_to_tl()` (TCMB); bulunmayan semboller `unknown_symbols` listesinde döner (TL=0). Snapshot entegrasyonu `_gather_manual_crypto_assets()` → `asset_type="crypto"`, `provider="manual:{exchange}"`. `User.manual_crypto_holdings` ilişkisi cascade all, delete-orphan.

#### `cash_holdings` (Faz 3 — nakit ve banka hesabı bakiyesi)
```sql
id          BIGSERIAL PK
user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
label       VARCHAR(100) NOT NULL                  -- 'Garanti TL', 'Wise EUR' vb.
amount      NUMERIC(18, 2) NOT NULL
currency    VARCHAR(3)  NOT NULL DEFAULT 'TRY'     -- TRY|USD|EUR|GBP
notes       TEXT
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_cash_holdings_user_id (user_id)
```

> Migration `d3e4f5a6b7c8`. Manuel bakiyeler — TCMB döviz kuruyla TL'ye çevrilir. Snapshot servisi `_gather_cash_assets()` ile `asset_type="cash"`, `provider="cash:{currency}"` olarak entegre eder. **FIN-007 (FAZ H):** TCMB GBP/USD opsiyonel, fail durumunda `health_issues`'a kaydedilip 0 yerine son cache değeri kullanılır.

#### `recurring_incomes` (Faz 3 — periyodik gelir tahminleri)
```sql
id            BIGSERIAL PK
user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
title         VARCHAR(100) NOT NULL                       -- 'Maaş', 'Kira A daire'
amount        NUMERIC(18, 2) NOT NULL
category      VARCHAR(20)  NOT NULL                       -- salary|rental|dividend|bonus|freelance|other
recurrence    VARCHAR(20)  NOT NULL                       -- one_time|monthly|quarterly|biannual|yearly|custom
months        INTEGER[]                                    -- custom için [1-12] aylar
day_of_month  INTEGER NOT NULL DEFAULT 1
start_date    DATE  NOT NULL
end_date      DATE                                         -- NULL = süresiz
notes         TEXT
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```

> Migration `c8d9e0f1a2b3`. Tek seferlik gelirler `incomes` tablosunda kalır; bu tablo sadece "yıl sonuna kadar X kazanmayı bekliyorum" tahmini için. **Realize akışı:** `POST /income/recurring/{id}/realize` (tek dönem), `realize-past` (start_date'ten bugüne), `realize-all-past` (toplu) → `incomes` satırı üretir; `incomes.recurring_income_id` (FK→recurring_incomes, ON DELETE SET NULL, migration `d9e0f1a2b3c4`) ve `(recurring_income_id, date)` UNIQUE çift realize'ı engeller.

#### `credit_cards` + `credit_card_statements` + `credit_card_installments` (Faz 3 — kart borcu + ekstre + taksit)
```sql
credit_cards
  id                   BIGSERIAL PK
  user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  name                 VARCHAR(100) NOT NULL                -- 'Garanti Bonus'
  bank_name            VARCHAR(60)
  last_4               VARCHAR(4)                            -- son 4 hane (PCI dışı sayım)
  credit_limit         NUMERIC(18, 2)
  statement_day        INTEGER NOT NULL DEFAULT 1            -- ay içi kesim günü
  payment_due_day      INTEGER NOT NULL DEFAULT 10
  current_period_debt  NUMERIC(18, 2) NOT NULL DEFAULT 0     -- ekstreye düşmemiş tutar (manuel)
  notes                TEXT
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()

credit_card_statements
  id                BIGSERIAL PK
  card_id           BIGINT NOT NULL REFERENCES credit_cards(id) ON DELETE CASCADE
  period_year       INTEGER NOT NULL
  period_month      INTEGER NOT NULL
  statement_amount  NUMERIC(18, 2) NOT NULL
  statement_date    DATE NOT NULL
  due_date          DATE NOT NULL
  paid_at           TIMESTAMPTZ                              -- NULL = ödenmedi
  notes             TEXT
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

  UNIQUE (card_id, period_year, period_month) AS uq_statement_card_period
  INDEX ix_credit_card_statements_card_id (card_id)

credit_card_installments
  id                       BIGSERIAL PK
  card_id                  BIGINT NOT NULL REFERENCES credit_cards(id) ON DELETE CASCADE
  description              VARCHAR(200) NOT NULL              -- 'Buzdolabı 12 taksit'
  total_amount             NUMERIC(18, 2) NOT NULL
  monthly_amount           NUMERIC(18, 2) NOT NULL
  installments_total       INTEGER NOT NULL
  installments_remaining   INTEGER NOT NULL                   -- her ay otomatik düşmez (manuel)
  first_due_date           DATE NOT NULL
  notes                    TEXT
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()

  INDEX ix_credit_card_installments_card_id (card_id)
```

> Migration'lar `e0f1a2b3c4d5` (credit_cards) + `f1a2b3c4d5e6` (statements + installments). **Çift sayım kuralı:** Kredi kartından ödenen ve gerçekleşmiş bir `expenses` kaydı (`credit_card_id IS NOT NULL AND is_paid = true`) zaten kart borcu/ekstresiyle sayıldığı için **`/expenses/summary`, `/budgets/comparison`, `/planned-expenses/forecast`** toplamlarından hariç tutulur (filtre: `or_(credit_card_id IS NULL, is_paid = false)`). Liste endpoint'leri (`/expenses`, `/planned-expenses`) tüm kayıtları gösterir; frontend rozetlerle (`💳 kart`, `✓ ödendi`) durumu belirtir. **Cash flow projeksiyonu:** Aylık gider tahmininde her aktif `installments_remaining > 0` olan installment için `monthly_amount` katkı düşülür; statement `due_date < ay sonu` ve `paid_at IS NULL` ise gerçekleşmiş gider hesabına alınır.

#### `revoked_tokens` (JWT blacklist)
```sql
jti          TEXT PRIMARY KEY                       -- JWT'nin jti claim'i (uuid4.hex)
user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
token_type   TEXT NOT NULL                          -- 'access' | 'refresh'
expires_at   TIMESTAMPTZ NOT NULL                   -- token doğal son kullanma; cleanup job için
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_revoked_tokens_expires_at (expires_at)
```

> `POST /auth/logout` access (zorunlu) ve refresh (opsiyonel) tokenları bu tabloya yazar. `POST /auth/refresh` (FAZ C4) **rotation** ile her refresh çağrısında eski refresh `jti`'sini buraya ekler. `get_current_user` decode sonrası `jti`'yi sorgular; blacklist'teyse 401. PK çakışmasında rollback ile sessiz idempotency. Eski (jti'siz) tokenlar geriye dönük uyumlu. **Cleanup cron (FAZ C5):** APScheduler her gün 03:00 Europe/Istanbul `expires_at < now` kayıtları siler.

#### `audit_logs` (FAZ C6) — KVKK m.12 + Veri İhlali Bildirim için forensic
```sql
id           UUID PK DEFAULT gen_random_uuid()
user_id      UUID NULL REFERENCES users(id) ON DELETE SET NULL  -- user silinince log korunur (forensic)
action       VARCHAR(64) NOT NULL                                -- 'auth.login', 'wallet.add', 'integration.delete', vb.
resource     VARCHAR(128) NULL                                   -- 'wallet:<uuid>', 'integration:binance'
ip_address   VARCHAR(45) NULL                                    -- IPv6 max 45 char (X-Forwarded-For desteği)
user_agent   VARCHAR(512) NULL                                   -- truncated
extra        JSONB NULL                                          -- ek context (chain, email, vs.)
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()

INDEX ix_audit_logs_user_created   (user_id, created_at DESC)    -- user kendi log'larını hızlı görür
INDEX ix_audit_logs_action_created (action, created_at DESC)     -- admin/security tipe göre arama
```

> **8 kritik eyleme hook'lanmış:** auth (login, login_failed, logout, register, password_change), wallet (add, delete), integration (add, delete), snapshot (delete), account (soft_delete). `app/services/audit.py::log_audit()` best-effort (try/except yutar — ana endpoint bozulmaz). `GET /api/v1/audit-logs?action_prefix=&limit=` IDOR korumalı endpoint. Migration `c4d5e6f7a8b9`. Detay: [03-api-referansi.md §17](./03-api-referansi.md), [07-guvenlik.md §10.2](./07-guvenlik.md).

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

> **Toplam 39 migration. Head: `e2f3a4b5c6d7`** (MFA TOTP `user.totp_*` kolonları). Yeni migration `down_revision = "e2f3a4b5c6d7"`. Aşağıdaki tablo kronolojik özet; tam zincir `backend/alembic/versions/`.

| Revision       | Açıklama                                                                                                                                                        |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `876bd62e282c` | İlk şema (users, integrations, wallet_addresses, portfolio_snapshots, asset_positions, investment_advice)                                                       |
| `a1b2c3d4e5f6` | `tefas_holdings` tablosu                                                                                                                                        |
| `b2c3d4e5f6a7` | `integrations.encrypted_extra` kolonu (Binance TR session token)                                                                                                |
| `c3d4e5f6a7b8` | `stock_holdings` tablosu                                                                                                                                        |
| `d4e5f6a7b8c9` | ✅ `users` lifecycle kolonları: `email_verified`, `verify_token`, `deleted_at`, `credit_balance` (CHECK >=0)                                                     |
| `e5f6a7b8c9d0` | ✅ `investment_advice.credits_used` kolonu                                                                                                                       |
| `f6a7b8c9d0e1` | ✅ Performans index'leri + `integrations(user_id, provider)` UNIQUE                                                                                              |
| `9a8b7c6d5e4f` | ✅ `users.verify_token_expires_at` + `ix_users_verify_token`                                                                                                     |
| `1f2e3d4c5b6a` | ✅ `bes_holdings` tablosu (plan_name, total_value_tl) + `ix_bes_holdings_user_id`                                                                                |
| `2a3b4c5d6e7f` | ✅ `revoked_tokens` tablosu (jti PK, user_id, token_type, expires_at) + `ix_revoked_tokens_expires_at` (JWT blacklist)                                           |
| `3b4c5d6e7f8a` | ✅ `bes_holdings` 4 metric genişletme (paid_principal, paid_returns, govt_contribution, govt_returns + contract_number; eski `total_value_tl` kolonu kaldırıldı) |
| `4c5d6e7f8a9b` | ✅ `expenses` tablosu (id, user_id, amount, category, date, description?, created_at) + `ix_expenses_user_date` — Faz 3 MVP harcama takibi                       |
| `5d6e7f8a9b0c` | ✅ `planned_expenses` tablosu (id, user_id, title, amount, is_estimated, category, recurrence, months[], day_of_month, start_date, end_date, remaining_count, notes, created_at) + `ix_planned_expenses_user_id` — Faz 3 planlı ödemeler & nakit akışı tahmini |
| `6e7f8a9b0c1d` | ✅ `users.monthly_expense_goal` (NUMERIC 18,2 nullable) — Faz 3 finansal hedef (ilk hâl, sonra yerine `goal_amount` + `goal_currency` eklendi) |
| `7f8a9b0c1d2e` | ✅ `users.goal_amount` + `users.goal_currency` (VARCHAR 3 default 'TRY') — `monthly_expense_goal` kaldırılır, mevcut TRY değerleri taşınır |
| `8a9b0c1d2e3f` | ✅ `incomes` tablosu (id, user_id, amount, category, date, description?, created_at) + `ix_incomes_user_date` — Faz 3 gelir takibi |
| `9b0c1d2e3f4a` | ✅ `budgets` tablosu (id, user_id, category, amount, updated_at) + `uq_budget_user_category` UNIQUE — Faz 3 kategori bazlı aylık bütçe |
| `a0b1c2d3e4f5` | ✅ `commodity_holdings` tablosu (id, user_id, unit_type, metal, biga_code?, coin_type?, quantity, notes?, created_at) + `ix_commodity_holdings_user_id` — Faz 3 altın/gümüş |
| `b1c2d3e4f5a6` | ✅ `tefas_holdings.avg_cost_tl` + `stock_holdings.avg_cost_tl` (NUMERIC 18,6 nullable) — Faz 3 maliyet bazı / kâr-zarar |
| `c2d3e4f5a6b7` | ✅ `tefas_holdings.distributor` + `stock_holdings.distributor` (VARCHAR 50 nullable) — Faz 3 aracı kurum (aynı varlığı farklı kurumlardan ayrı satır) |
| `f5a6b7c8d9e0` | ✅ `manual_crypto_holdings` tablosu (id, user_id, exchange, label?, symbol, quantity 28,12, avg_cost_tl?, notes?, created_at, updated_at) + `ix_manual_crypto_holdings_user_exchange` — API'siz borsalar için manuel kripto kayıt |
| `a6b7c8d9e0f1` | ✅ `manual_crypto_holdings.price_source` enum ('auto'/'manual'/'linked') + `manual_unit_price_tl` |
| `b7c8d9e0f1a2` | ✅ `manual_crypto_holdings.linked_source` + `linked_id` (asset catalog bağlama) |
| `c8d9e0f1a2b3` | ✅ `recurring_incomes` tablosu (periyodik gelir tahmini) |
| `d9e0f1a2b3c4` | ✅ `incomes.recurring_income_id` FK (ON DELETE SET NULL) + `(recurring_income_id, date)` UNIQUE (çift realize engeli) |
| `d3e4f5a6b7c8` | ✅ `cash_holdings` tablosu (nakit/banka — TRY/USD/EUR/GBP) |
| `e0f1a2b3c4d5` | ✅ `credit_cards` tablosu (+ current_period_debt) |
| `f1a2b3c4d5e6` | ✅ `credit_card_statements` + `credit_card_installments` tabloları |
| `a2b3c4d5e6f7` | ✅ `expenses` + `planned_expenses` `credit_card_id` + `is_paid` (çift sayım kuralı) |
| `e4f5a6b7c8d9` | ✅ `portfolio_snapshots.health_issues` (JSONB) + `usd_try_rate` (geçmiş USD eğimi) |
| `e5f6a7b8c9d0` | ✅ `investment_advice.credits_used` |
| `e6f7a8b9c0d1` | ✅ `investment_advice` prompt cache + token metrics kolonları |
| `d4e5f6a7b8c9` | ✅ `users` lifecycle kolonları (email_verified, verify_token, deleted_at, credit_balance) |
| `d5e6f7a8b9c0` | ✅ `asset_positions` unit_price precision genişletme |
| `d1e2f3a4b5c6` | ✅ PERF-003 ek user_id index'leri |
| `b3c4d5e6f7a8` | ✅ FAZ C1 — `wallet_addresses` xpub Fernet (`address_encrypted` + `address_fingerprint`) |
| `c4d5e6f7a8b9` | ✅ FAZ C6 — `audit_logs` tablosu |
| `b9c0d1e2f3a4` | ✅ KVKK hakları kolonları (age_confirmed vb.) |
| `c0d1e2f3a4b5` | ✅ AI-005 — `users.anthropic_consent_at` + `anthropic_consent_version` |
| `a8b9c0d1e2f3` | ✅ SEC-001 — `password_reset_tokens` tablosu |
| `f7a8b9c0d1e2` | ✅ DBA-001 FK CASCADE düzeltmeleri + SEC-002 hesap kilitleme kolonları |
| `e2f3a4b5c6d7` | ✅ MFA — `users.totp_secret` + `totp_enabled` + `totp_recovery_codes` |
| `f3a4b5c6d7e8` | ✅ Faz 3 kredi sistemi — `credit_transactions` ledger tablosu |
| `a7b8c9d0e1f2` | ✅ **(HEAD)** Periyodik gerçekleşme — `recurring_skips` tablosu + `expenses.planned_expense_id` (FK + partial UNIQUE `(planned_expense_id, date)`) |

### Mevcut Index'ler
- `ix_users_email` (UNIQUE)
- `ix_users_verify_token`
- `ix_integrations_user_id`
- `ix_wallet_addresses_user_id`
- `ix_tefas_holdings_user_id`
- `ix_stock_holdings_user_id`
- `ix_bes_holdings_user_id`
- `ix_expenses_user_date` (user_id + date)
- `ix_planned_expenses_user_id` (user_id)
- `ix_incomes_user_date` (user_id + date)
- `ix_commodity_holdings_user_id` (user_id)
- `ix_manual_crypto_holdings_user_exchange` (user_id + exchange)
- `ix_revoked_tokens_expires_at`
- `ix_investment_advice_user_id`
- `ix_portfolio_snapshots_user_date` (user_id + snapshot_date DESC)
- `ix_asset_positions_snapshot_id`
- `uq_integrations_user_provider` (UNIQUE)
- `uq_snapshot_user_date` (UNIQUE)
- `uq_wallet_user_chain_fp` (UNIQUE — `(user_id, chain, address_fingerprint)`)
- `ix_wallet_addresses_fingerprint`
- `ix_audit_logs_user_created` + `ix_audit_logs_action_created`
- `ix_cash_holdings_user_id`, `ix_credit_card_statements_card_id`, `ix_credit_card_installments_card_id`
- `uq_budget_user_category` (UNIQUE — `(user_id, category)`)

### Durum
- [ ] `credit_transactions` tablosu (Faz 2/3 — kredi sistemi; **kodda henüz YOK**, backlog)
- [x] `expenses` tablosu (migration `4c5d6e7f8a9b`; 10 sabit kategori `Literal`)
- [x] `planned_expenses` tablosu (migration `5d6e7f8a9b0c`; 7 kategori + 6 tekrar tipi)
- [x] `incomes` tablosu (migration `8a9b0c1d2e3f`; 7 sabit kategori) + `recurring_incomes` (`c8d9e0f1a2b3`)
- [x] `budgets` tablosu (migration `9b0c1d2e3f4a`; UPSERT pattern, kategori UNIQUE)
- [x] `commodity_holdings` tablosu (migration `a0b1c2d3e4f5`; gram/BiGA/sikke)
- [x] `cash_holdings` (migration `d3e4f5a6b7c8`) + `credit_cards`/`statements`/`installments` (`e0f1a2b3c4d5` + `f1a2b3c4d5e6`)
- [x] `users.goal_amount` + `goal_currency` (migration `7f8a9b0c1d2e`; USD/EUR/GBP/TRY)
- [x] TEFAS + Stocks `avg_cost_tl` + `distributor` (migration `b1c2d3e4f5a6` + `c2d3e4f5a6b7`)
- [x] `audit_logs` tablosu (FAZ C6 — migration `c4d5e6f7a8b9`; KVKK uyum)
- [x] `revoked_tokens` tablosu (migration `2a3b4c5d6e7f`) + cleanup cron (03:00, FAZ C5)
- [x] Soft delete hard-delete cron — 30 gün (04:00, COMP-004) + audit_logs purge cron (04:30, COMP-022)
- [x] MFA TOTP `users.totp_*` (migration `e2f3a4b5c6d7`)

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

| Servis            | Sınıf                                       | Notlar                                                                                                                                                                       |
| ----------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Binance           | `BinanceService`                            | CCXT, fetch_balance + savings/locked                                                                                                                                         |
| Binance TR        | `BinanceTRService`                          | Özel istemci, session token (cid cookie); GeeTest CAPTCHA nedeniyle programatik login YOK                                                                                    |
| iCrypex           | `ICrypexService`                            | CCXT wrapper                                                                                                                                                                 |
| Sonic             | `SonicService`                              | web3.py + SFC staking contract; `Semaphore(20)` ile paralel validator sorgu                                                                                                  |
| Avalanche P-Chain | `AvalanchePChainService`                    | `platform.getBalance` + `platform.getStake` paralel (httpx, `P-` prefix gerekli); likit (`unlockeds`/`unlocked`) + stake (`lockedStakeables`+`staked`) ayrı çekilir |
| Avalanche C-Chain | `AvalancheCChainService`                    | EVM RPC, web3.py — multi-RPC fallback (settings → public-rpc → drpc → 1rpc); curated 3 ERC-20 (sAVAX, USDT.e, USDC.e)                                                       |
| Ethereum          | `EthereumService`                           | EVM RPC (multi-RPC fallback: settings → publicnode → merkle → 1rpc → ankr) + Etherscan + Ethplorer ERC-20 discovery                                                          |
| Solana            | `SolanaService`                             | `api.mainnet-beta.solana.com` JSON-RPC; liquid (native SOL `getBalance`) + staked (`getProgramAccounts` Stake program, offset 12=staker, 44=withdrawer)                       |
| Cardano / Algorand / Polkadot / Litecoin | (Faz A — public REST API'ler) | Adres bakiyesi tek query; staking ayrımı yok                                                                                                                                |
| ERC-20 token discovery | `evm_tokens.py`                       | `fetch_ethereum_tokens_via_ethplorer()` (free key='freekey', ~50 istek/gün); `fetch_token_balances()` curated AVAX list — sequential `balanceOf` + 3 retry + 0.5 sn backoff; `_looks_like_spam()` filter |
| TEFAS             | `TefasService`                              | httpx + JSON API                                                                                                                                                             |
| Yahoo Finance     | `fetch_stock_quotes()`                      | httpx (`v8/finance/chart/{ticker}`)                                                                                                                                          |
| BES               | `_gather_bes_assets()` (snapshot.py içinde) | DB'den okur — `bes_holdings` → `AssetData(asset_type="pension", provider="bes")`                                                                                             |
| Manuel kripto     | `_gather_manual_crypto_assets()` (snapshot.py içinde) | DB'den okur — `manual_crypto_holdings` → `AssetData(asset_type="crypto", provider="manual:{exchange}")`; fiyat `compute_and_save_snapshot()` ortak enrichment loop'unda enjekte edilir |
| Kıymetli madenler | `commodity.py::fetch_metal_prices()`        | TCMB USD/TRY (kritik) + Yahoo Finance Chart API XAU=X→GC=F + XAG=X→SI=F fallback chain. 5 dk in-memory cache; Yahoo fail durumunda TTL 30 sn'ye düşer; metaller best-effort (0 dönerse UI banner) |
| Aggregator        | `aggregator.py`                             | `fetch_usd_to_tl`, `fetch_gbp_to_usd`, `fetch_spot_prices`, `calculate_changes`, `calculate_breakdown` — TCMB primary + exchangerate-api fallback, 5 dk in-memory TCMB cache |
| Snapshot          | `snapshot.py::compute_and_save_snapshot()`  | Tüm kaynakları paralel topla (BES dahil), TL normalize, DB'ye yaz (idempotent). MKK import endpoint'lerinden best-effort tetiklenir                                          |
| E-posta           | `email.py::send_verification_email()`       | Resend SDK + HTML şablon                                                                                                                                                     |
| Ekstre import     | `statement_import/` (`detect_parser` + banka parser'ları) | PDF→metin (`extract_text`, pdfplumber) → `ParsedStatement`; pluggable `PARSERS` (Ziraat/Enpara/VakıfBank/Akbank). `_utils.parse_amount` TR+EN sayı otomatik tespit. Fail-safe: tanınmayan/değişmiş format → ValueError → endpoint 422 (kayıt yok) |
| Recurrence        | `recurrence.py` (`applies_in_month` + `date_for_period` + `iter_due_periods`) | Periyodik gelir/gider ortak dönem hesabı (duck-typed `RecurringIncome`/`PlannedExpense`); income + planned_expenses realize ve `/recurring/pending` bunu kullanır (DRY) |

> Detaylı API entegrasyon mantığı, prompt'lar, hata yönetimi: [api-referansi.md](./api-referansi.md), [ai-ve-finans.md](./ai-ve-finans.md)

#### Ekstre (PDF) import parser mimarisi (Faz 3)

Kredi kartı ekstresi PDF'ini parse edip `credit_cards` + `statements` + `installments` tablolarına aktarır (`/credit-cards/import-statement/preview` + `commit`). Pluggable tasarım: her banka için `StatementParser` Protocol'ü (`base.py`) implement eden bir sınıf `PARSERS` listesine eklenir; `detect_parser(text)` ilk `matches()` true olanı seçer. Parser'lar saf-metin üzerinde çalışır (pdfplumber'dan bağımsız → unit test edilebilir).

- **Ziraat/Enpara/VakıfBank:** temiz metin katmanı; regex ile alan çıkarımı. Banka başına sayı formatı farkı (`500.000,00` TR vs `17,495.87` EN) `_utils.parse_amount` ile otomatik çözülür. VakıfBank taksitleri değişken formatlı → yalnız net "Nx tutar" deseni alınır + uyarı.
- **Akbank/Axess:** PDF metin katmanı custom font encoding nedeniyle pdfplumber'da `(cid:NNN)` glyph token'ları + dağınık Latin karakter olarak çıkar (ToUnicode CMap yok). `_decode` rakam + finansal sembolleri çözer: `(cid:240..249)`→0..9 (CID = ASCII + `0xC0`), Latin rakam glyph'leri `æ`=1/`ı`=5/`ł`=8/`ø`=9, `k`=binlik nokta / `K`=ondalık virgül / `\`=`*`, `GGaAAaYYYY`→`GG/AA/YYYY`. Harf glyph'leri context-dependent (güvenilmez) → etiketler decode edilmez; bunun yerine **cid'den bağımsız format işaretleri** kullanılır: maskeli kart (`5218@07**@****@6072`) + "ekstre dönemi" tarih aralığı (`25/04/2026‘23/05/2026`) birlikte → Akbank (`matches`). Değerler konumdan: ilk tarih = son ödeme, dönem aralığı sonu = hesap kesim, ilk tutar = dönem borcu, en büyük tutar = kart limiti. Format değişirse bulunamaz → fail-safe.
- **Fail-safe ilkesi:** Hiçbir parser eşleşmezse "banka tanınmadı", eşleşip alan bulunamazsa "format değişmiş" → 422; asla tahmini/yanlış veri yazılmaz. İki adımlı preview→commit ile kullanıcı önizleyip düzeltir/onaylar.
- **Gelecek:** Bilinmeyen bankalar / bozuk PDF'ler için opsiyonel `AIStatementParser` (Claude PDF/vision, `document` content block — OCR'sız görselden okur; KVKK consent + kredi düşümü gerektirir).

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

## 8.3 Fault-Tolerance Pattern (Yeni)

KFinans dış API kaynaklarını **kritik** ve **best-effort** olarak ayırır.

| Kaynak | Sınıflandırma | Davranış |
|--------|---------------|----------|
| TCMB USD/TRY | Kritik | Snapshot iptal (503), kıymetli maden sayfası açılmaz |
| TCMB GBP/USD | Best-effort | UK hisseleri 0 değerle devam eder, log warning |
| Yahoo Finance hisse kotasyonu | Per-ticker | Bir ticker fail olursa sadece o pozisyon eksik |
| Yahoo Finance XAU=X / XAG=X (altın/gümüş) | Best-effort + fallback | Önce primary (XAU=X / XAG=X), sonra futures (GC=F / SI=F); ikisi de fail ise 0 dön + UI uyarı banner |
| Binance / iCrypex / blockchain | Per-source | Her kaynak izole, biri fail diğerleri devam |

**Cache stratejisi:** Yahoo Finance metal sembolleri başarısız olursa cache TTL 5 dakikadan 30 saniyeye düşer — geçici 404 hızla telafi olur, sürekli sayfa açıldığında 5 dakika boyunca aynı 0 değer takılı kalmaz.

### 8.3.1 Multi-RPC Fallback Pattern (EVM)

`EthereumService` ve `AvalancheCChainService` upstream RPC patladığında self-heal sağlar:

| Servis | RPC Sırası |
|--------|-----------|
| Ethereum | `settings.ethereum_rpc_url` → publicnode → merkle → 1rpc → ankr |
| Avalanche C | `settings.avalanche_c_rpc_url` → public-rpc → drpc → 1rpc |

İlk başarılı RPC seçilir; tümü fail olursa servis hata döner ve snapshot bu kaynak için 0 değerle devam eder.

### 8.3.2 Bitcoin Cache + Single-Flight Pattern

`bitcoin.py` modül seviyesinde iki paylaşılan yapı tutar:

| Yapı | Amaç |
|------|------|
| `_BALANCE_CACHE` (dict, 10 dk TTL) | Dashboard yenileme rate limit'e takılmasın |
| `_INFLIGHT` (dict[address, asyncio.Future]) | Paralel cache miss'lerde tek tarama paylaşılır (single-flight) |

xpub HD tarama maliyetli olduğu için cache hit oranını yüksek tutar. **Düşürülmüş TTL:** Bakiye 0 dönerse (geçici upstream 404/timeout) cache TTL 30 saniyeye düşer — kısa süre sonra otomatik yeniden denenir, 10 dk boyunca yanlış 0 değer takılı kalmaz. Avalanche P-Chain ve Litecoin de aynı cache + single-flight pattern'ini kullanır.

### 8.3.3 ERC-20 Token Discovery (Ethplorer + Spam Filter)

| Zincir | Yöntem |
|--------|--------|
| Ethereum | `fetch_ethereum_tokens_via_ethplorer()` — Ethplorer free API (`api.ethplorer.io`, key='freekey'); dinamik discovery |
| Avalanche C | Curated `AVALANCHE_C_TOKENS` listesi (sAVAX, USDT.e, USDC.e); sequential `balanceOf` + 3 retry + 0.5 sn backoff (Infura/RPC rate limit) |

**Spam filter (`_looks_like_spam()`):** ad/sembolde domain TLD'leri (.io/.com/.finance), Cherokee veya Math Alphanumeric Unicode spoofing, "Visit/claim rewards" pattern'leri ve >1e12 miktar token'lar atılır. Saldırgan ERC-20 airdrop'larının dashboard'a kirletmesini engeller.

### 8.3.4 422 Validation Log Handler

`main.py` `RequestValidationError` exception handler 422 hata detayını (`exc.errors()`) log'a yazar — frontend'e mevcut formatta dönüş; geliştirme sırasında schema validation hatasının hangi alanda kaynaklandığı log'dan görülür.

## 8.4 MKK e-Yatırımcı Excel Import Pattern (Yeni)

MKK "Tüm Kıymetler" raporu eski .xls binary formatındadır. KFinans `xlrd==1.2.0` (xlsx desteği kaldırılmadan önceki son sürüm) ile parse eder.

**Pattern:**
1. `xlrd.open_workbook(file_contents=content)` ile workbook aç
2. Header satırını "Üye" sütunundan tespit et (ilk 20 satırı tara)
3. Sınıfa göre filtrele:
   - `POST /portfolio/tefas/import-mkk` → `Kıymet Sınıfı = 'Fon'`
   - `POST /portfolio/stocks/import-mkk` → `Kıymet Sınıfı = 'HS'` AND `Ek Tanım = 'A'` (aktif tradeable)
4. Her satır için: kod + ad + adet + fiyat (TL) + üye → `TefasHolding` veya `StockHolding`
   - Hisse için BIST kodları otomatik `.IS` suffix ile Yahoo Finance ticker formatına çevrilir
   - `Üye` sütunu `distributor` alanına yazılır (max 50 karakter)
   - Fiyat 0 ise `avg_cost_tl` `None` olur
5. Mevcut kullanıcı kayıtları **silinir** (replace-all), yeni kayıtlar eklenir
6. **Best-effort snapshot:** `compute_and_save_snapshot()` `try/except` ile çağrılır — fail olsa bile import korunur (history/finansal hedef güncel kalsın diye dener)

> Frontend: paylaşılan `_components/MkkHint.tsx` bileşeni info kart + opsiyonel `onUpload` prop ile MKK xls upload butonu (Stocks + TEFAS sayfalarında).

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
