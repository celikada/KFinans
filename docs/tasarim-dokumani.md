# KFinans — Sistem Tasarım Dokümanı

**Versiyon:** 3.5
**Tarih:** 2026-04-30
**Durum:** Aktif geliştirme — Faz 1 tamamlandı, Faz 2 yedi madde develop'ta
**Üretici:** Mayotek

---

## Doküman Yapısı

Bu doküman bir **kapı dokümanı**dır — projenin genel vizyonunu, fazlarını ve detaylı dokümanlara yönlendirmeleri içerir. Her teknik konunun derinlemesine açıklaması ilgili alt dokümandadır.

| Doküman | İçerik | Sahip Ajan |
|---------|--------|------------|
| [mimari.md](./mimari.md) | Sistem mimarisi, modüler monolit yapı, veritabanı şeması, indeks stratejisi | architect + dba |
| [api-referansi.md](./api-referansi.md) | Tüm REST endpoint'leri, request/response örnekleri, hata kodları | backend-expert |
| [frontend.md](./frontend.md) | Next.js App Router yapısı, component sınırları, state, API client | frontend-expert |
| [altyapi-test.md](./altyapi-test.md) | Docker Compose, Kubernetes, CI/CD, test stratejisi ve coverage hedefleri | devops + test-expert |
| [guvenlik.md](./guvenlik.md) | Auth akışı, JWT, Fernet şifreleme, rate limiting, OWASP kontrol listesi | security-expert |
| [uyumluluk-kvkk.md](./uyumluluk-kvkk.md) | KVKK, GDPR, SPK lisans sınırı, gizlilik politikası, kullanıcı hakları | compliance-expert |
| [ai-ve-finans.md](./ai-ve-finans.md) | Claude API entegrasyonu, prompt tasarımı, portföy hesaplama formülleri | ai-expert + finance-expert |
| [kredi-sistemi.md](./kredi-sistemi.md) | Kredi paketleri, iyzico ödeme akışı, kredi tüketim kuralları | architect + finance-expert |

---

## 1. Platform Vizyonu

KFinans, kişisel finansı tek ekranda yöneten **çok kiracılı (multi-tenant) SaaS platformudur**. Hedef pazar: Türkiye bireysel yatırımcısı. Erişim kanalları: web (Next.js) ve mobil (Flutter — Faz 3). Temel takip ücretsiz; AI tavsiye, kripto/blockchain otomatik senkronizasyon ve gelişmiş analiz **kredi sistemi** ile ücretlendirilir.

### 1.1 Üretici ve Marka
- **Üretici Firma:** Mayotek (kurucu: celikada@gmail.com)
- **Ürün:** KFinans
- **Logolar:** `frontend/public/images/kfinans-logo.png`, `mayotek-logo.png`

### 1.2 Faz Planı

| Faz | Kapsam | Durum |
|-----|--------|-------|
| **Faz 1** | Yatırım takibi (TEFAS, kripto, blockchain, hisse senedi), Excel import/export, dashboard | ✅ Tamamlandı |
| **Faz 2** | Kullanıcı kaydı + e-posta doğrulama ✅, scheduler + snapshot servisi ✅, TCMB fallback ✅, BES manuel giriş ✅, JWT blacklist + logout ✅, Kubernetes manifest'leri | 🔄 Devam ediyor |
| **Faz 3** | Kredi sistemi + iyzico, AI tavsiye motoru aktivasyonu, harcama takibi | Planlı |
| **Faz 4** | Flutter mobile app, Play Store yayın, Apple sertifikasyonu | Planlı |

---

## 2. İş Modeli

### 2.1 Kullanıcı Tipleri ve Fiyatlandırma

| Tip | Erişim | Fiyat |
|-----|--------|-------|
| **Ücretsiz** | TEFAS takibi, manuel varlık, temel portföy görünümü, Excel import/export | — |
| **Kredi Paketi** | AI tavsiye, kripto entegrasyonu, blockchain sorgu, gelişmiş analiz | Kredi başına |

### 2.2 Kredi Tüketim Kuralları

| İşlem | Maliyet |
|-------|---------|
| AI portföy tavsiyesi (orta vade) | 5 kredi |
| AI portföy tavsiyesi (uzun vade) | 10 kredi |
| Kripto senkronizasyonu (Binance/iCrypex/BinanceTR) | 1 kredi/çekim |
| Blockchain bakiye sorgusu | 1 kredi/sorgu |
| Gelişmiş harcama analizi (Faz 3) | 3 kredi |

> Detaylı tüketim mantığı, ödeme akışı ve idempotency: [kredi-sistemi.md](./kredi-sistemi.md)

### 2.3 Kredi Paketleri

| Paket | Kredi | Fiyat |
|-------|-------|-------|
| Başlangıç | 50 | 29 ₺ |
| Standart | 150 | 69 ₺ |
| Profesyonel | 500 | 199 ₺ |

Ödeme: **iyzico** (sandbox + production). Stripe çoklu para birimi için Faz 4'te değerlendirilecek.

---

## 3. Teknoloji Yığını

### 3.1 Backend
- Python 3.12 + FastAPI (async-first)
- PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg driver) + Alembic
- APScheduler (Pazar 23:00 haftalık snapshot)
- Anthropic Python SDK (Claude API tavsiye motoru)
- CCXT (Binance, iCrypex), web3.py (Sonic, Avalanche, Ethereum), httpx (TEFAS, Yahoo Finance)
- slowapi (rate limiting), Fernet (API key encryption), bcrypt (şifre hash), python-jose (JWT)

### 3.2 Frontend
- Next.js 16.2.4 (App Router, Turbopack), React 19, TypeScript (strict mode), Tailwind CSS v4
- `proxy.ts` (Next.js 16 yeni adlandırma — `middleware.ts` deprecated)

### 3.3 Mobile (Faz 4)
- Flutter, http, flutter_secure_storage, riverpod

### 3.4 Altyapı
- Docker + Docker Compose (geliştirme — bilinçli teknik borç)
- Kubernetes (production hedef; namespace: `kfinans`)
- Tilt veya Skaffold (production'a geçişte dev loop için)
- GitHub Actions (CI/CD), GHCR (container registry)
- Helm (bitnami/postgresql), nginx-ingress, cert-manager

---

## 4. Veri Kaynakları

| Tür | Kaynak | Yöntem |
|-----|--------|--------|
| TEFAS fonu | TEFAS API | httpx + JSON (`fonkod/sonPortfoyDegeri/sonPayAdedi`) |
| Hisse (BIST/ABD/UK) | Yahoo Finance | httpx (`v8/finance/chart/{ticker}`) — auth gerekmez |
| Kripto Spot | Binance, iCrypex | CCXT |
| Kripto TR Earn | Binance TR | session token (cid cookie) — geçici çözüm |
| Sonic | EVM (RPC) | web3.py + SFC staking contract (Semaphore(20)) |
| Avalanche P-Chain | platform.getStake | httpx (REST API) |
| Avalanche C-Chain | EVM (RPC) | web3.py |
| Ethereum | EVM (RPC) | web3.py + Etherscan |
| BES | Manuel giriş ✅ (Faz 2) | Kullanıcı plan adı + toplam ₺ girer; idempotent PUT + Excel import/export |

> Blockchain entegrasyonlarında **özel anahtar asla sisteme girmez** — yalnızca public adres saklanır.
> Detaylı entegrasyon mantığı: [mimari.md](./mimari.md#7-veri-kaynaklari-ve-servisler)

---

## 5. Mimari Özeti

KFinans **modüler monolit** mimarisi kullanır:
- Tek FastAPI uygulaması (3 Kubernetes Deployment: backend, frontend, postgres)
- Servis ayrımı kod içinde (`api/v1/*`, `services/*`)
- Mikroservise geçişe gerek yok — mevcut ölçek ve trafik için aşırı karmaşıklık

```
İstemci (Web / Mobile)
    │
    ▼ HTTPS / REST
Kubernetes Ingress (nginx)
    │
    ├──► backend Deployment (FastAPI + uvicorn, replicas: 2)
    │         │
    │         ▼
    │    PostgreSQL StatefulSet (bitnami/postgresql)
    │
    └──► frontend Deployment (Next.js standalone, replicas: 2)
```

> Tam mimari, modül sınırları ve veri akışı: [mimari.md](./mimari.md)

---

## 6. Geliştirme Kuralları

- **Doküman dili:** Türkçe (commit mesajları dahil)
- **Kod dili:** İngilizce (identifier, comment, log)
- **Secrets:** Asla koda yazılmaz; `.env` üzerinden `pydantic-settings` ile okunur
- **Migration:** Tüm DB değişiklikleri Alembic üzerinden
- **PR akışı:** `feature/*` → `develop` → `release/*` → `main` (korumalı)
- **CI:** Test + lint geçmeden merge yapılamaz

> Git Flow detayları: [altyapi-test.md](./altyapi-test.md#git-flow)

---

## 7. Güncel Durum (2026-04-30)

### ✅ Faz 1 Tamamlandı
- Backend iskeleti, JWT auth, slowapi rate limiting (login 10/dk, register 5/dk, refresh 30/dk), `/health` endpoint
- TEFAS, kripto (Binance/BinanceTR/iCrypex), blockchain (Sonic/Avalanche/Ethereum), hisse (Yahoo Finance)
- Excel import/export tüm varlık türleri için
- Frontend dashboard, login, kripto/wallets/stocks sayfaları
- Docker Compose dev ortamı (Kubernetes port-forward watchdog kaldırıldı)
- CI/CD: 4 ayrı workflow — `ci-backend`, `ci-frontend`, `e2e`, `security`
- 11 domain expert ajanı (`.claude/agents/`) — backend, frontend, dba, devops, security, test, architect, finance, doc, ai, compliance
- 9 odaklı doküman (`docs/`)
- Migration durumu güncel: `users` lifecycle kolonları (email_verified, verify_token, deleted_at, credit_balance), `investment_advice.credits_used`, performans index'leri

### ✅ Faz 2 — Tamamlanan Maddeler (develop'ta)

**1. Stocks (hisse senedi) modülü**
- Backend: `models/stock.py` (StockHolding), migration `c3d4e5f6a7b8`. Mevcut `services/stocks.py` ve `api/v1/stocks.py` artık çalışır durumda (model olmadığı için broken'dı)
- Frontend: `/dashboard/stocks` — Yahoo Finance fiyat preview, Excel import/export
- Endpoint'ler: `GET/PUT /portfolio/stocks/holdings`, `POST /portfolio/stocks/preview`, `GET /portfolio/stocks/export`, `POST /portfolio/stocks/import`

**2. Wallets UI sayfası**
- Frontend: `/dashboard/wallets` — cüzdan ekle/sil/listele, pozisyon tablosu, Excel import/export
- Backend zaten mevcuttu (`api/v1/wallets.py`)

**3. Kullanıcı kayıt + e-posta doğrulama akışı**
- Backend: `RegisterRequest(email, password, risk_profile)`, `verify_token` üretimi (24 saat TTL), Resend SDK ile mail
- Yeni endpoint'ler: `GET /auth/verify-email`, `POST /auth/resend-verification` (her zaman 202 — account enumeration koruması), `POST /auth/login` 403 hard block (email_verified=False)
- Yeni servis: `services/email.py` (Resend SDK + HTML şablon)
- Yeni env: `RESEND_API_KEY`, `EMAIL_FROM`, `FRONTEND_URL`, `VERIFY_TOKEN_EXPIRE_HOURS=24`
- Migration `9a8b7c6d5e4f`: `users.verify_token_expires_at` + `ix_users_verify_token`
- Frontend: `/register`, `/verify-email` (Suspense + useSearchParams), `/login`'e "Kayıt ol" linki
- 14 yeni backend test (`test_auth.py`)

**4. Scheduler + snapshot servisi**
- Yeni servis: `services/snapshot.py::compute_and_save_snapshot()` — tüm kaynakları (Binance, BinanceTR, iCrypex, Sonic, Avalanche P/C, Ethereum, TEFAS, hisse) paralel toplar, TL'ye normalize eder, `portfolio_snapshots` + `asset_positions` yazar
- İdempotent (aynı gün eskiyi siler, yenisi yazılır), hata izolasyonu (bir kaynak fail diğerleri devam)
- USD/TL kritik kur — başarısız olursa snapshot iptal (raise); GBP/USD opsiyonel — başarısız olursa 0 ile devam (UK hisseleri 0 değer + log warning)
- `app/scheduler.py`: `AsyncIOScheduler` (Europe/Istanbul, Pazar 23:00, misfire_grace_time=3600s)
- Yeni endpoint: `POST /portfolio/snapshot` (manuel tetikleme — test/UI için), kur servisleri erişilemezse 503
- Frontend dashboard'da "Snapshot al" butonu
- 4 yeni snapshot integration test

**5. TCMB API USD/TRY (ve GBP/USD) fallback**
- `services/aggregator.py` baştan yazıldı: `TCMB_URL = https://www.tcmb.gov.tr/kurlar/today.xml` (primary)
- Fallback: `https://api.exchangerate-api.com/v4/latest/{USD,GBP}`
- `_fetch_tcmb_rates()` — TCMB XML'i parse eder (`ForexBuying`); `Unit=100` (JPY vb.) tek birime normalize edilir
- `fetch_usd_to_tl()`: TCMB → exchangerate-api → fail ise `RuntimeError`
- `fetch_gbp_to_usd()`: TCMB'den derive (`GBP/TRY ÷ USD/TRY`) → exchangerate-api → fail ise `RuntimeError`
- 5 dakikalık in-memory TCMB cache (aynı snapshot içinde tek HTTP çağrısı)
- `services/snapshot.py`: `asyncio.gather(..., return_exceptions=True)` ile USD/TL kritik (raise), GBP/USD opsiyonel (0 ile devam)
- `POST /portfolio/snapshot` `RuntimeError` → 503
- 9 yeni unit test (`test_exchange_rates.py`) + 2 yeni integration test (kur fail senaryoları)

**6. BES (Bireysel Emeklilik Sistemi) manuel giriş modülü**
- Backend: `models/bes.py` (`BesHolding(id, user_id, plan_name, total_value_tl)`), migration `1f2e3d4c5b6a` — `bes_holdings` tablosu + `ix_bes_holdings_user_id`
- `User.bes_holdings` ilişkisi (cascade all, delete-orphan)
- `schemas/bes.py`: `BesHolding(plan_name min_length=1 max_length=200, total_value_tl Decimal ge=0)`
- Yeni router: `api/v1/bes.py` (prefix `/portfolio/bes`, tag `bes`)
  - `GET /holdings` → liste
  - `PUT /holdings` → idempotent (replace-all)
  - `GET /export` → `bes-holdingleri.xlsx`
  - `POST /import` → Excel'den yükle (mevcut kayıtları değiştirir)
- `services/snapshot.py`: yeni `_gather_bes_assets()` — BES holding'leri `asset_type="pension"`, `provider="bes"`, `source_type="bes"`, `liquid_quantity=1`, `unit_price_tl=total_value_tl` ile `AssetData`'ya çevrilir; ana paralel toplama dalına `bes_holdings` DB çekimi eklendi
- Frontend: `/dashboard/bes` sayfası (plan adı + toplam ₺ tek satırda iki input, "Plan ekle" + "Kaldır" + "Kaydet" + Excel İndir/Yükle), dashboard kartı pasif "yakında"dan aktif `besTotal`/`besPlanCount` özetli butona dönüştü
- `lib/api.ts`: `getBesHoldings`, `saveBesHoldings`, `exportBesHoldings`, `importBesHoldings` + `BesHoldingDTO`
- 8 yeni API test (`test_bes_api.py`) + 1 IDOR test + 1 snapshot integration test

**7. JWT blacklist + logout endpoint'i**
- Backend: `models/revoked_token.py` — `RevokedToken(jti TEXT PK, user_id, token_type, expires_at, created_at)`. Migration `2a3b4c5d6e7f` — `revoked_tokens` tablosu + `ix_revoked_tokens_expires_at` (cleanup için)
- `core/security.py` — `create_access_token` ve `create_refresh_token` artık her token'a `jti=uuid.uuid4().hex` claim ekler
- `core/deps.py::get_current_user` — decode sonrası jti blacklist kontrolü; eski jti'siz tokenlar geriye dönük uyumlu (jti yoksa atlanır)
- Yeni endpoint: `POST /auth/logout` — `LogoutRequest(refresh_token: str | None)`. Header'daki access ve body'deki refresh (varsa, sub eşleşiyorsa) blacklist'e alınır. PK çakışmasında rollback (idempotent), bozuk refresh sessizce yutulur
- `POST /auth/refresh` güncellendi — refresh token blacklist'teyse 401 "Token iptal edilmiş"
- Schema: `LogoutRequest` `schemas/auth.py`'a eklendi
- Frontend: `lib/api.ts::logout(refreshToken?)` ve `/dashboard/page.tsx` logout butonu (`clearAuth()` öncesi `api.logout()` çağırır)
- Bilinen limitasyon: frontend `localStorage`'da yalnızca access tutuyor; refresh akışı eklendiğinde refresh token da blacklist'e alınmalı
- 8 yeni integration test (`test_logout.py`)

**Test paketi (güncel):**
- **135 backend** + 3 frontend Vitest + 5 Playwright E2E senaryosu
  - Unit: security (22), aggregator (22), exchange_rates (9), GBp dönüşümü (7), TEFAS (6) — toplam 66
  - Integration: auth (21), portfolio (8), IDOR (8), integrations (5), wallets (5), snapshot (7), bes (8), logout (8) — toplam 70
  - E2E: login redirect, register + login akışı (Playwright)

### 🐛 Son Sprint'te Düzeltilen Bug'lar
- **`AssetPositionOut.id` ve `SnapshotOut.id` Pydantic v2 strict UUID rejection** — `str → uuid.UUID` düzeltildi
- **Binance `_sign` paralel istek recvWindow aşımı** — `recvWindow=60000` eklendi
- **Migration cycle düzeltmesi** — `c3d4e5f6a7b8.down_revision = a1b2c3d4e5f6`, `9a8b7c6d5e4f.down_revision = f6a7b8c9d0e1`

### 🐛 Faz 1'de Düzeltilen Bug'lar
- **GBp dönüşüm hatası** — UK hisseleri için GBP/USD kuru zinciri (`api/v1/stocks.py::convert_to_tl`)
- **Duplicate wallet 500 → 409** — `IntegrityError` doğru HTTP koduyla yakalanıyor
- **Pydantic v2 uyumsuzluk** — `class Config` → `model_config` (kısmi)
- **Service katmanı logger eksikliği** — 9 servise module-level `logger` eklendi

### 🔄 Faz 2 — Kalan Öncelikler
- [x] Kullanıcı kayıt frontend sayfası + e-posta doğrulama akışı (Resend)
- [x] Haftalık snapshot servisi + scheduler implementasyonu
- [x] Stocks ve Wallets UI sayfaları
- [x] TCMB API USD/TRY fallback (TCMB primary + exchangerate-api fallback, 5 dk in-memory cache)
- [x] BES manuel giriş ekranı (model + endpoint'ler + Excel + snapshot entegrasyonu + frontend)
- [x] JWT blacklist + `/auth/logout` endpoint'i (revoked_tokens tablosu + jti claim + refresh blacklist kontrolü)
- [ ] Kubernetes manifest'leri (`k8s/` klasörü hâlâ boş)
- [ ] KVKK metinleri (gizlilik politikası, aydınlatma, açık rıza)
- [ ] Şifre sıfırlama akışı (`/auth/forgot-password`, `/auth/reset-password`)
- [ ] Binance TR Earn endpoint'i için Resmi API yanıtı bekleniyor — geçici çözüm `encrypted_extra` ile cookie token `feature/binancetr-session-token` branch'inde
- [ ] Test coverage %30 → %50 hedefi

### 📋 Faz 3 Planlananlar
- Kredi sistemi tam implementasyonu + iyzico sandbox
- KVKK endpoint'leri (`/me/data-export`, `/me/account` soft delete)
- `audit_logs` tablosu
- Cache katmanı (Redis) — USD/TRY, TEFAS, Yahoo
- Background job kuyruğu (Celery/RQ)

> Detaylı yol haritası ve TODO'lar her alt dokümanın sonundadır.
