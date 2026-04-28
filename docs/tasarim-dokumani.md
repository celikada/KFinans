# KFinans — Sistem Tasarım Dokümanı

**Versiyon:** 2.0  
**Tarih:** 2026-04-28  
**Durum:** Aktif geliştirme

---

## 1. Platform Vizyonu

KFinans, kişisel finansı tek ekranda yöneten çok kiracılı (multi-tenant) bir SaaS platformudur. Android (Play Store) ve web üzerinden erişilebilir; temel özellikler ücretsiz, gelişmiş özellikler kredi sistemiyle ücretlendirilir.

| Faz | Kapsam | Durum |
|-----|--------|-------|
| Faz 1 | Yatırım takibi, TEFAS, Excel import/export | ✅ Aktif |
| Faz 2 | Harcama takibi, bütçe, banka ekstresi | Planlı |
| Faz 3 | Android app (Flutter), Play Store | Planlı |
| Faz 4 | Kredi/token sistemi, ödeme entegrasyonu | Planlı |

---

## 2. Hedef Kitle & İş Modeli

### 2.1 Kullanıcı Tipleri

| Tip | Özellikler | Fiyat |
|-----|-----------|-------|
| Ücretsiz | TEFAS takip, manuel varlık, temel portföy, Excel import/export | — |
| Kredi Paketi | AI tavsiye, kripto entegrasyonu, blockchain sorgu, gelişmiş analiz | Kredi başına |

### 2.2 Kredi Gerektiren İşlemler

| İşlem | Kredi Maliyeti |
|-------|---------------|
| AI portföy tavsiyesi (orta vade) | 5 kredi |
| AI portföy tavsiyesi (uzun vade) | 10 kredi |
| Kripto senkronizasyonu (Binance/iCrypex) | 1 kredi / çekim |
| Blockchain bakiye sorgusu | 1 kredi / sorgu |
| Gelişmiş harcama analizi (Claude) | 3 kredi |

### 2.3 Kredi Paketleri (iyzico / Stripe)

| Paket | Kredi | Fiyat |
|-------|-------|-------|
| Başlangıç | 50 | 29 ₺ |
| Standart | 150 | 69 ₺ |
| Profesyonel | 500 | 199 ₺ |

---

## 3. Veri Kaynakları

### 3.1 Fon & Yatırım

| Kaynak | Yöntem | Durum |
|--------|--------|-------|
| TEFAS | `POST /api/fund-returns/export` (JSON) | ✅ Tamamlandı |
| Manuel varlık (GO3 vb.) | Kullanıcı girişi | ✅ Tamamlandı |
| BES | Manuel giriş (Faz 2) | Planlı |

### 3.2 Kripto Exchange

| Kaynak | Yöntem | Kütüphane |
|--------|--------|-----------|
| Binance | REST API (API key + secret) | CCXT |
| iCrypex Global | REST API (`Bearer` token) | httpx (özel) |

### 3.3 Blockchain (Ledger / DeFi)

| Kaynak | Zincir | Yöntem | Kütüphane |
|--------|--------|--------|-----------|
| Sonic Labs | Sonic (EVM) | RPC + SFC staking contract | web3.py |
| Core.app | Avalanche P-Chain | Avalanche REST API | httpx |
| Core.app | Avalanche C-Chain | EVM RPC | web3.py |
| Ledger | Ethereum | EVM RPC + Etherscan | web3.py |

> Blockchain entegrasyonlarında özel anahtar **asla** sisteme girmez; yalnızca public adres kullanılır.

---

## 4. Sistem Mimarisi

### 4.1 Genel Bakış

```
┌──────────────────────────────────────────────────────────┐
│              İstemci Katmanı                             │
│                                                          │
│   ┌─────────────────┐        ┌──────────────────────┐   │
│   │  Next.js Web    │        │  Flutter Android App │   │
│   │  (localhost/    │        │  (Play Store)        │   │
│   │   nginx)        │        │                      │   │
│   └────────┬────────┘        └──────────┬───────────┘   │
└────────────┼──────────────────────────── ┼───────────────┘
             │ HTTPS / REST                │
┌────────────▼─────────────────────────────▼───────────────┐
│                Kubernetes Cluster                        │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │           Ingress (nginx-ingress)               │    │
│  │   api.kfinans.app → backend-svc                 │    │
│  │   app.kfinans.app → frontend-svc                │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  backend Deployment (FastAPI + uvicorn)          │    │
│  │  replicas: 2                                     │    │
│  │  image: kfinans/backend:latest                   │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  PostgreSQL StatefulSet (bitnami/postgresql)     │    │
│  │  namespace: kfinans                              │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  frontend Deployment (Next.js)                   │    │
│  │  replicas: 2                                     │    │
│  └─────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 4.2 Backend İç Yapısı (Modüler Monolit)

```
FastAPI Backend
│
├── api/v1/
│   ├── auth.py          (login, register, refresh, verify-email)
│   ├── portfolio.py     (TEFAS holdings, export, import, preview)
│   ├── integrations.py  (Binance, iCrypex API key yönetimi)
│   ├── wallets.py       (blockchain adres yönetimi)
│   ├── advice.py        (AI tavsiye — kredi gerektiren)
│   ├── credits.py       (bakiye, satın alma, kullanım geçmişi)
│   └── expenses.py      (Faz 2)
│
├── services/
│   ├── exchange/
│   │   ├── base.py
│   │   ├── binance.py
│   │   └── icrypex.py
│   ├── blockchain/
│   │   ├── sonic.py
│   │   ├── avalanche.py
│   │   └── ethereum.py
│   ├── tefas.py
│   ├── aggregator.py
│   └── advisor.py       (Claude API — kredi kontrolü ile)
│
├── models/
│   ├── user.py          (+ credit_balance, email_verified)
│   ├── tefas.py         (tefas_holdings)
│   ├── integration.py
│   ├── portfolio.py
│   ├── credit.py        (credit_transactions)
│   └── advice.py
│
└── scheduler.py         (APScheduler — Pazar 23:00)
```

### 4.3 Neden Modüler Monolit?

Mevcut ölçekte mikroservis karmaşıklığı (service mesh, distributed tracing, inter-service auth) gereksizdir. Modüler yapı ileride servis ayırımını kolaylaştırır. Kubernetes üzerinde 3 Deployment (frontend, backend, postgres) ile tüm cloud avantajları (scaling, health check, rolling update, secret management) elde edilir.

---

## 5. Veritabanı Şeması

### 5.1 Kullanıcı

```sql
users
  id                UUID PK
  email             TEXT UNIQUE
  password_hash     TEXT
  risk_profile      ENUM('conservative','balanced','aggressive')
  credit_balance    INT DEFAULT 0
  email_verified    BOOLEAN DEFAULT FALSE
  verify_token      TEXT
  created_at        TIMESTAMPTZ
```

### 5.2 Kredi İşlemleri

```sql
credit_transactions
  id           UUID PK
  user_id      UUID FK → users
  amount       INT              -- pozitif: yükleme, negatif: kullanım
  reason       TEXT             -- 'purchase', 'ai_advice_medium', 'crypto_sync' vb.
  reference_id TEXT             -- ödeme sağlayıcı işlem ID (iyzico/Stripe)
  created_at   TIMESTAMPTZ
```

### 5.3 TEFAS Holdingleri

```sql
tefas_holdings
  id       SERIAL PK
  user_id  UUID FK → users (CASCADE DELETE)
  code     VARCHAR(10)      -- 'GO3', 'TI2' vb.
  quantity NUMERIC(18,6)
  name     TEXT
```

### 5.4 Entegrasyon Kimlik Bilgileri

```sql
integrations
  id               UUID PK
  user_id          UUID FK → users
  provider         ENUM('binance','icrypex')
  encrypted_key    TEXT        -- Fernet şifreli
  encrypted_secret TEXT        -- Fernet şifreli
  is_active        BOOLEAN
  last_synced_at   TIMESTAMPTZ
  created_at       TIMESTAMPTZ
```

### 5.5 Blockchain Cüzdan Adresleri

```sql
wallet_addresses
  id         UUID PK
  user_id    UUID FK → users
  chain      ENUM('ethereum','sonic','avalanche_c','avalanche_p')
  address    TEXT
  label      TEXT
  is_active  BOOLEAN
  created_at TIMESTAMPTZ
  UNIQUE(user_id, chain, address)
```

### 5.6 Portföy Snapshot

```sql
portfolio_snapshots
  id              UUID PK
  user_id         UUID FK → users
  snapshot_date   DATE
  total_value_tl  NUMERIC(18,2)
  created_at      TIMESTAMPTZ
  UNIQUE(user_id, snapshot_date)

asset_positions
  id                UUID PK
  snapshot_id       UUID FK → portfolio_snapshots
  source_type       ENUM('exchange','blockchain','fund','manual')
  provider          TEXT
  asset_type        ENUM('crypto','staked_crypto','fund','pension','cash','manual')
  symbol            TEXT
  name              TEXT
  liquid_quantity   NUMERIC(28,8)
  staked_quantity   NUMERIC(28,8)
  pending_rewards   NUMERIC(28,8)
  unit_price_tl     NUMERIC(18,4)
  total_value_tl    NUMERIC(18,2)
  weight_pct        NUMERIC(5,2)
  wallet_address_id UUID FK → wallet_addresses
```

### 5.7 Yatırım Tavsiyeleri

```sql
investment_advice
  id                UUID PK
  user_id           UUID FK → users
  snapshot_id       UUID FK → portfolio_snapshots
  horizon           ENUM('medium','long')
  content           TEXT
  credits_used      INT
  prompt_tokens     INT
  completion_tokens INT
  generated_at      TIMESTAMPTZ
```

### 5.8 Harcamalar (Faz 2)

```sql
expense_categories
  id         UUID PK
  user_id    UUID FK → users
  name       TEXT
  color      TEXT
  budget_tl  NUMERIC(12,2)
  is_default BOOLEAN

expenses
  id           UUID PK
  user_id      UUID FK → users
  category_id  UUID FK → expense_categories
  amount_tl    NUMERIC(12,2)
  description  TEXT
  expense_date DATE
  source       ENUM('manual','bank_import')
  is_recurring BOOLEAN DEFAULT FALSE
  created_at   TIMESTAMPTZ
```

---

## 6. API Tasarımı

### 6.1 Auth
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/verify-email?token=...
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
```

### 6.2 Krediler
```
GET    /api/v1/credits                  -- bakiye + işlem geçmişi
POST   /api/v1/credits/checkout         -- iyzico/Stripe ödeme başlat
POST   /api/v1/credits/webhook          -- ödeme sağlayıcı callback
```

### 6.3 TEFAS Portföy
```
GET    /api/v1/portfolio/tefas/holdings
PUT    /api/v1/portfolio/tefas/holdings
GET    /api/v1/portfolio/tefas/export   -- xlsx indir
POST   /api/v1/portfolio/tefas/import   -- xlsx yükle
POST   /api/v1/portfolio/tefas/preview  -- canlı fiyat
```

### 6.4 Exchange Entegrasyonları (kredi gerekli)
```
GET    /api/v1/integrations
POST   /api/v1/integrations/{provider}
DELETE /api/v1/integrations/{provider}
POST   /api/v1/integrations/sync        -- 1 kredi / çekim
```

### 6.5 Blockchain Cüzdanlar (kredi gerekli)
```
GET    /api/v1/wallets
POST   /api/v1/wallets
DELETE /api/v1/wallets/{id}
POST   /api/v1/wallets/sync             -- 1 kredi / sorgu
```

### 6.6 Portföy & Tavsiye
```
GET    /api/v1/portfolio
GET    /api/v1/portfolio/history
GET    /api/v1/portfolio/changes
GET    /api/v1/portfolio/breakdown
POST   /api/v1/advice/generate          -- 5-10 kredi
GET    /api/v1/advice
```

### 6.7 Harcamalar (Faz 2)
```
GET/POST        /api/v1/expenses
PUT/DELETE      /api/v1/expenses/{id}
POST            /api/v1/expenses/import
GET/POST        /api/v1/expenses/categories
GET             /api/v1/expenses/analysis
POST            /api/v1/expenses/analysis/generate   -- 3 kredi
```

---

## 7. Kubernetes Deployment

### 7.1 Namespace & Mevcut Durum

```
namespace: kfinans
mevcut:    postgres StatefulSet (bitnami/postgresql) ✅
eklenecek: backend Deployment + Service
           frontend Deployment + Service
           nginx Ingress
           Secrets (DATABASE_URL, SECRET_KEY, FERNET_KEY vb.)
```

### 7.2 Manifest Yapısı

```
k8s/
├── namespace.yaml
├── secrets.yaml           (kubectl create secret — git'e girmez)
├── postgres/
│   └── values.yaml        (Helm override — mevcut)
├── backend/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── frontend/
│   ├── deployment.yaml
│   └── service.yaml
└── ingress.yaml
```

### 7.3 Backend Deployment Özeti

```yaml
replicas: 2
image: kfinans/backend:{{ git-sha }}
resources:
  requests: { cpu: 250m, memory: 256Mi }
  limits:   { cpu: 500m, memory: 512Mi }
livenessProbe:  GET /health
readinessProbe: GET /health
envFrom: secretRef kfinans-secrets
```

### 7.4 CI/CD Akışı (GitHub Actions)

```
push → main
  ├── test (pytest)
  ├── docker build & push (ghcr.io)
  └── kubectl rollout (image tag = git sha)
```

---

## 8. Test Stratejisi

### 8.1 Test Piramidi

```
          ┌──────────┐
          │   E2E    │  az sayıda, kritik akışlar
          ├──────────┤
          │Integration│ API endpoint testleri (gerçek DB)
          ├──────────┤
          │   Unit   │  service & helper fonksiyonları
          └──────────┘
```

### 8.2 Backend Test Yapısı

```
backend/tests/
├── conftest.py            (async engine, test DB, client fixture)
├── unit/
│   ├── test_tefas.py      (fiyat hesaplama, export/import)
│   ├── test_aggregator.py (TL normalize, staking ayrımı)
│   └── test_credits.py    (bakiye kontrol, deduction)
├── integration/
│   ├── test_auth.py       (register, login, refresh)
│   ├── test_portfolio.py  (holdings CRUD, export, import)
│   └── test_advice.py     (kredi kontrolü, AI çağrısı mock)
└── e2e/
    └── test_tefas_flow.py (login → holding kaydet → fiyat çek → export)
```

### 8.3 Test Araçları & Kurallar

| Araç | Kullanım |
|------|---------|
| pytest + pytest-asyncio | Ana test koşucusu |
| httpx AsyncClient | FastAPI endpoint testleri |
| pytest-postgresql / testcontainers | Gerçek PostgreSQL (mock yok) |
| respx | Dış HTTP çağrılarını mock'la (TEFAS, iyzico) |
| pytest-cov | Kod kapsama — hedef %80+ |

**Kurallar:**
- DB asla mock'lanmaz — her test gerçek PostgreSQL'e karşı çalışır
- Dış HTTP (TEFAS, blockchain RPC, ödeme API) `respx` ile mock'lanır
- Her PR'da testler geçmeden merge yapılamaz (CI zorunlu)

### 8.4 Frontend Test Yapısı

```
frontend/
├── __tests__/
│   ├── api.test.ts        (api.ts fonksiyonları)
│   └── components/
│       └── tefas-page.test.tsx
```

| Araç | Kullanım |
|------|---------|
| Jest + React Testing Library | Bileşen testleri |
| msw (Mock Service Worker) | API mock |

---

## 9. Git Flow

### 9.1 Branch Yapısı

```
main          ← production (korumalı, doğrudan push yasak)
develop       ← aktif geliştirme birleştirme noktası
│
├── feature/tefas-holdings      (tamamlandı → develop'a merge)
├── feature/excel-import-export (tamamlandı → develop'a merge)
├── feature/kubernetes-deploy   (aktif)
├── feature/user-register       (planlanıyor)
├── feature/credit-system       (planlanıyor)
│
├── release/1.0.0               (develop → main hazırlık)
└── hotfix/kritik-bug-adi       (main'den dallanır, main + develop'a merge)
```

### 9.2 Kurallar

| Kural | Detay |
|-------|-------|
| `main` korumalı | Doğrudan push yasak; yalnızca PR ile merge |
| PR zorunluluğu | Tüm mergelar PR üzerinden, en az 1 approval |
| CI zorunlu | Testler geçmeden merge yapılamaz |
| Commit mesajları | Türkçe, imperative: "Kredi sistemi ekle" |
| Feature branch ömrü | Merge sonrası silinir |
| Release tag | `v{major}.{minor}.{patch}` semantic versioning |

### 9.3 Tipik Geliştirme Akışı

```bash
git checkout develop
git pull origin develop
git checkout -b feature/yeni-ozellik

# geliştir, test et
git add ...
git commit -m "Özellik: açıklama"
git push origin feature/yeni-ozellik

# GitHub'da PR aç: feature → develop
# CI geçer → review → merge → branch silinir
```

### 9.4 Release Akışı

```bash
git checkout -b release/1.0.0 develop
# son düzeltmeler, versiyon bump
git checkout main && git merge release/1.0.0
git tag -a v1.0.0 -m "İlk public sürüm"
git checkout develop && git merge release/1.0.0
git branch -d release/1.0.0
```

---

## 10. Güvenlik

| Konu | Çözüm |
|------|-------|
| Exchange API key | Fernet şifreleme, master key Kubernetes Secret'ta |
| Blockchain adres | Public key — şifrelemeye gerek yok |
| Özel anahtar | **Asla sisteme girmez** |
| Kullanıcı şifresi | bcrypt hash |
| JWT | access 8sa (geliştirme) / 15dk (prod), refresh 7 gün |
| HTTPS | Kubernetes Ingress + cert-manager (Let's Encrypt) |
| Secrets | Kubernetes Secrets (git'e asla girmez) |
| Kredi işlemi | İdempotency key ile çift ödeme koruması |
| Rate limiting | Nginx Ingress rate limit annotation |

---

## 11. AI Tavsiye Motoru

### 11.1 Claude API Ayarları

- Model: `claude-sonnet-4-6`
- Prompt caching: sistem prompt cache'lenir (maliyet optimizasyonu)
- Max tokens: 1024
- Yanıt formatı: Yapılandırılmış Markdown

### 11.2 Kredi Kontrolü Akışı

```
POST /api/v1/advice/generate
  1. Kullanıcı kredi bakiyesini kontrol et
  2. Yetersizse 402 Payment Required dön
  3. Claude API çağrısını yap
  4. Başarılıysa credit_transactions'a negatif kayıt ekle
  5. users.credit_balance güncelle
  6. Tavsiyeyi kaydet ve dön
```

---

## 12. Mobile (Flutter — Faz 3)

### 12.1 Mimari

- **Flutter** (Android öncelikli, iOS hazır)
- Mevcut FastAPI backend'i değişmez — aynı REST API
- JWT token'ı `flutter_secure_storage` ile güvenli saklanır
- Offline-first değil — internet bağlantısı gerekli

### 12.2 Ekranlar

| Ekran | Açıklama |
|-------|---------|
| Giriş / Kayıt | JWT auth |
| Dashboard | Portföy toplam değeri, varlık kartları |
| TEFAS | Holding listesi, canlı fiyatlar |
| Tavsiye | AI önerileri (kredi ile) |
| Kredi | Bakiye, paket satın alma (iyzico in-app) |
| Ayarlar | Profil, risk profili, API key yönetimi |

---

## 13. Teknoloji Bağımlılıkları

### 13.1 Backend

```toml
fastapi, uvicorn, sqlalchemy[asyncio], alembic, asyncpg
pydantic-settings, pydantic[email]
python-jose[cryptography], bcrypt, cryptography
ccxt, web3, httpx, beautifulsoup4
apscheduler, anthropic
python-multipart, openpyxl
```

### 13.2 Frontend (Web)

```json
next.js, react, tailwindcss, typescript
```

### 13.3 Mobile

```yaml
flutter, http, flutter_secure_storage, provider/riverpod
```

### 13.4 Altyapı

```
Kubernetes (Docker Desktop / cloud)
Helm (bitnami/postgresql)
nginx-ingress, cert-manager
GitHub Actions (CI/CD)
ghcr.io (container registry)
```

---

## 14. Geliştirme Fazları & Durum

### ✅ Tamamlanan

- FastAPI iskeleti, PostgreSQL + Alembic, JWT auth
- TEFAS fiyat çekme (export API)
- TEFAS holding kaydet/yükle (DB)
- Excel import/export (openpyxl)
- Next.js dashboard, login, TEFAS sayfası

### 🔄 Sıradaki (Öncelik Sırası)

#### Kubernetes Deploy
- [ ] Backend Dockerfile
- [ ] Frontend Dockerfile
- [ ] k8s/backend manifests (Deployment, Service)
- [ ] k8s/frontend manifests
- [ ] k8s/ingress.yaml
- [ ] GitHub Actions CI pipeline

#### Test Altyapısı
- [ ] pytest conftest (async DB, test client)
- [ ] Unit testler (TEFAS, aggregator)
- [ ] Integration testler (auth, portfolio endpoints)
- [ ] Frontend Jest setup

#### Git Flow Kurulumu
- [ ] `develop` branch oluştur
- [ ] `main` branch koruması (GitHub branch protection)
- [ ] PR template ekle

#### Kullanıcı Yönetimi (SaaS hazırlığı)
- [ ] `POST /auth/register` endpoint
- [ ] E-posta doğrulama (SMTP / Resend)
- [ ] Şifre sıfırlama akışı
- [ ] `credit_balance` users tablosuna ekle (migration)

#### Kredi Sistemi
- [ ] `credit_transactions` tablosu (migration)
- [ ] `GET/POST /credits` endpointleri
- [ ] iyzico ödeme entegrasyonu (sandbox)
- [ ] Kredi kontrolü middleware (advisor.py)

#### Faz 2 — Harcama Takibi
- [ ] Harcama modelleri + migration
- [ ] CRUD endpointler
- [ ] Frontend harcama ekranları

#### Faz 3 — Flutter Mobile
- [ ] Proje kurulumu
- [ ] Auth akışı
- [ ] TEFAS ekranı
- [ ] Play Store yayını
