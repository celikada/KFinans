# Altyapı, Deployment ve Test Stratejisi

**Sahip ajanlar:** `devops`, `test-expert`
**İlgili:** [mimari.md](./mimari.md), [guvenlik.md](./guvenlik.md)

---

## 1. Mevcut Fonksiyonel Gereksinimler

### 1.1 Geliştirme Ortamı (Çalışıyor)
- ✅ Docker Compose: `postgres`, `backend` (FastAPI + uvicorn --reload), `frontend` (Next.js + Turbopack)
- ✅ Backend hot-reload: `./backend:/app` volume mount
- ✅ Frontend hot-reload: `./frontend:/app` volume mount
- ✅ Auto-migration: container start'ta `alembic upgrade head`
- ✅ Healthcheck: PostgreSQL `pg_isready` → backend depends_on healthy

### 1.2 CI Pipeline (Çalışıyor — 6 workflow)
- ✅ `.github/workflows/ci-backend.yml`: lint (ruff) + unit + integration + coverage gate (%50)
- ✅ `.github/workflows/ci-frontend.yml`: ESLint + Vitest + Next.js build
- ✅ `.github/workflows/e2e.yml`: backend + frontend up + Playwright (Chromium) — 5 senaryo
- ✅ `.github/workflows/security.yml` (FAZ B4): gitleaks (.gitleaks.toml allowlist) + Trivy fs (HIGH/CRITICAL fail) + pip-audit (osv strict) + npm-audit (high) + CodeQL (Python + JS/TS) — haftalık cron + her PR
- ✅ `.github/workflows/sonar.yml` (FAZ B2): backend pytest cov XML + frontend vitest LCOV → SonarCloud quality gate (`vars.ENABLE_SONAR='true'` iken aktif; bekleme döneminde skip)
- ✅ `.github/workflows/release.yml` (FAZ B3): semver tag (`v*.*.*`) → 5 job (Sonar QG → matrix Docker buildx & GHCR push → Trivy image scan HIGH/CRITICAL → Oracle SSH `kubectl set image` + rollout → Playwright @smoke → GitHub Release notes)

### 1.3 Yayın Pipeline ✅ TAMAMLANDI (FAZ B3)
- ✅ Semver tag push (`v*.*.*`) → otomatik Oracle Cloud K3s deploy
- ✅ GHCR `ghcr.io/celikada/kfinans-backend:tag` + `kfinans-frontend:tag`
- ✅ Trivy image vulnerability scan deploy öncesi
- ✅ kubectl set image + rollout status (360s timeout)
- ✅ Production smoke test (Playwright @smoke etiketi)
- ✅ GitHub Release notes otomatik

### 1.4 GitHub Actions Limit Durumu
- Repo: **PUBLIC** (FAZ B5) → **Sınırsız** GitHub Actions dakikası
- Workflow path filtresi aktif (sadece ilgili dizin değişince tetiklenir)

### 1.5 Eksik (Production'a Kadar)
- ✅ Kubernetes manifestleri (`k8s/` klasörü — kustomize, tek komutla deploy) — bkz. §3
- ✅ Production deployment otomatik (FAZ B3 — release.yml semver tag tetiklemesi)
- ✅ Branch protection rule'ları (`main` + `develop`) — FAZ B6
- ✅ Container image vulnerability scan (Trivy) — FAZ B3 + B4
- ✅ Dependency scan (pip-audit + npm-audit + Dependabot) — FAZ A4 + B4
- ❌ Tilt/Skaffold dev loop (Docker Compose'tan geçiş — bilinçli teknik borç)
- ❌ Monitoring (Prometheus + Grafana) — Faz 3
- ❌ Centralized logging (Loki veya ELK) — Faz 3
- ⏳ SonarCloud entegrasyonu — GitHub flag (Ticket #4360519) çözülmesi bekleniyor; workflow opsiyonel

---

## 2. Geliştirme Ortamı

### 2.1 Docker Compose Servisleri

```yaml
# docker-compose.yml — özet
services:
  postgres:
    image: postgres:16-alpine
    healthcheck: pg_isready
    volume: postgres_data
    port: 5432

  backend:
    build: ./backend (target: development)
    command: alembic upgrade head && uvicorn app.main:app --reload
    depends_on: postgres (healthy)
    port: 8000
    volume: ./backend:/app

  frontend:
    image: node:20-alpine
    command: npm install && npm run dev
    port: 3000
    volume: ./frontend:/app
```

### 2.2 Hızlı Başlangıç
```bash
# Tüm stack'i başlat
docker compose up -d

# Sadece DB
docker compose up postgres -d

# Logları izle
docker compose logs -f backend

# Container içine gir
docker compose exec backend bash

# Yeni Python paketi yükle (geçici)
docker compose exec backend pip install slowapi

# Kalıcı: pyproject.toml + image rebuild
docker compose up -d --build backend
```

### 2.3 Bilinen Sorunlar (Cosmetic)
- Turbopack `/app/src` watch error'ı — proje `app/` directory yapısı kullanıyor, `src/` yok. İşlevselliği etkilemez.

---

## 3. Production: Kubernetes (Manifest'ler Hazır)

### 3.1 Namespace ve Mevcut Durum
```
namespace: kfinans
mevcut (k8s/ klasöründe):
  ✅ namespace.yaml            — kfinans namespace
  ✅ configmap.yaml            — non-secret env (CORS, EMAIL_FROM, FRONTEND_URL,
                                  RPC URL'leri, CLAUDE_MODEL, NEXT_PUBLIC_API_URL)
  ✅ secrets.example.yaml      — şablon (gerçek secrets.yaml gitignore'da)
  ✅ postgres.yaml             — PostgreSQL 16 StatefulSet (replicas: 1, 50Gi PVC,
                                  headless Service, pg_isready probes)
  ✅ backend.yaml              — FastAPI Deployment (replicas: 2,
                                  RollingUpdate maxUnavailable: 0,
                                  initContainer alembic upgrade head,
                                  /health liveness + readiness + startup probes,
                                  envFrom configmap+secret, ClusterIP)
  ✅ frontend.yaml             — Next.js standalone Deployment (replicas: 2, ClusterIP)
  ✅ ingress.yaml              — nginx-ingress + cert-manager TLS
                                  (api.kfinans.app → backend, app.kfinans.app → frontend)
  ✅ kustomization.yaml        — kustomize index (tek komutla deploy)
  ✅ README.md                 — kapsamlı deploy rehberi

Frontend Dockerfile zaten production-ready (multi-stage standalone, next.config.ts'de
output: "standalone"). Backend Dockerfile production target da mevcut.
```

### 3.2 Önkoşullar
- Kubernetes cluster (1.27+) + `kubectl` yapılandırılmış
- nginx-ingress controller kurulu
- cert-manager kurulu + ClusterIssuer (`letsencrypt-prod`) tanımlı
- DNS: `api.kfinans.app` ve `app.kfinans.app` cluster ingress IP'sine bağlı
- GHCR'ya push edilmiş image'lar: `ghcr.io/celikada/kfinans-backend:{sha}`, `ghcr.io/celikada/kfinans-frontend:{sha}`

### 3.3 Tek Komut Deploy
```bash
# 1) Secret hazırlığı (sadece ilk seferinde):
cp k8s/secrets.example.yaml k8s/secrets.yaml
# secrets.yaml'i base64 değerlerle doldur (DATABASE_URL, SECRET_KEY, FERNET_KEY,
# ANTHROPIC_API_KEY, RESEND_API_KEY, POSTGRES_PASSWORD vb.)
# Alternatif: kubectl create secret generic kfinans-secrets --from-literal=... -n kfinans

# 2) Image tag güncelle (kustomization.yaml içindeki images: bloğu)

# 3) Deploy
kubectl apply -k k8s/

# 4) Migration init container otomatik çalışır; durumu izle
kubectl -n kfinans rollout status deploy/backend
kubectl -n kfinans rollout status deploy/frontend
```

> Ayrıntılı rehber (önkoşullar, secret oluşturma, image push, migration akışı, ölçeklendirme, yedekleme, Faz 3 TODO'ları): [`k8s/README.md`](../k8s/README.md)

### 3.4 Faz 3 TODO'ları (manifest seti dışında)
HPA (HorizontalPodAutoscaler), NetworkPolicy, PodDisruptionBudget, Prometheus + Grafana, PgBouncer, `revoked_tokens` cleanup CronJob, external-secrets/SealedSecrets, `pg_dump` CronJob.

### 3.5 Image Tagging Stratejisi
```
ghcr.io/celikada/kfinans-backend:{git-sha}    # immutable, deployment için
ghcr.io/celikada/kfinans-backend:develop      # son develop build
ghcr.io/celikada/kfinans-backend:v1.0.0       # release tag
ghcr.io/celikada/kfinans-backend:latest       # KULLANILMAYACAK — kafa karıştırıcı
```

---

## 4. CI/CD Pipeline (FAZ B sonrası — 6 workflow)

```
                          ┌──────────────────────────┐
                          │  develop branch (push)   │
                          └─────────────┬────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌──────────────┐               ┌──────────────┐                ┌──────────────┐
│ ci-backend   │               │ ci-frontend  │                │ e2e          │
│ ruff+pytest  │               │ eslint+vitest│                │ Playwright   │
│ +cov gate %50│               │ +next build  │                │              │
└──────────────┘               └──────────────┘                └──────────────┘
        │                               │                               │
        ▼                               ▼                               ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  security.yml                                                 │
        │  gitleaks (allowlist) | Trivy fs (HIGH/CRITICAL) | pip-audit  │
        │  npm-audit (high)     | CodeQL (Python + JS/TS)               │
        └───────────────────────────────────────────────────────────────┘
        │
        ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  sonar.yml (vars.ENABLE_SONAR='true' iken)                    │
        │  backend pytest cov XML + frontend vitest LCOV → SonarCloud   │
        │  quality gate (wait=true)                                     │
        └───────────────────────────────────────────────────────────────┘


                          ┌──────────────────────────┐
                          │  main: tag push v*.*.*   │
                          └─────────────┬────────────┘
                                        │
                                        ▼  release.yml
        ┌───────────────────────────────────────────────────────────────┐
        │  Job 0: SonarCloud Quality Gate (opsiyonel)                   │
        ├───────────────────────────────────────────────────────────────┤
        │  Job 1: Build & Push (matrix backend + frontend)              │
        │         docker buildx → ghcr.io/celikada/kfinans-{svc}:tag    │
        ├───────────────────────────────────────────────────────────────┤
        │  Job 2: Trivy Image Scan (HIGH/CRITICAL → fail)               │
        ├───────────────────────────────────────────────────────────────┤
        │  Job 3: Oracle K3s Deploy                                     │
        │         SSH → kubectl apply -k k8s/ → set image → rollout     │
        ├───────────────────────────────────────────────────────────────┤
        │  Job 4: Production Smoke Test (Playwright @smoke)             │
        ├───────────────────────────────────────────────────────────────┤
        │  Job 5: GitHub Release (changelog otomatik)                   │
        └───────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │ https://kfinans.app      │
                          │ (Oracle Cloud K3s)       │
                          └──────────────────────────┘
```

### 4.1 Workflow listesi
| Workflow | Tetikleyici | Süre | Status check name'leri (branch protection için) |
|----------|-------------|------|------------------------------------------------|
| `ci-backend.yml` | develop+main push, PR | ~5 dk | `Lint (ruff)`, `Unit testler`, `Integration testler (real PostgreSQL)`, `Coverage gate` |
| `ci-frontend.yml` | develop+main push, PR | ~3 dk | `Lint`, `Unit (vitest)`, `Build` |
| `e2e.yml` | develop+main push, PR | ~8 dk | `E2E (Playwright)` |
| `security.yml` | develop+main push, PR, weekly cron | ~10 dk | `Gitleaks — secret tarama`, `Trivy — filesystem (deps + IaC)`, `pip-audit — Python deps`, `npm-audit — Node deps`, `CodeQL — python`, `CodeQL — javascript-typescript` |
| `sonar.yml` | develop+main push, PR | ~6 dk | `Backend coverage (pytest + cobertura XML)`, `Frontend coverage (vitest + LCOV)`, `SonarCloud analiz + quality gate` |
| `release.yml` | Tag `v*.*.*` push | ~15 dk | (release-only, branch protection check değil) |

### 4.2 Branch Protection (FAZ B6)
**`main`:**
- PR şart, lineer history, force-push kapalı, branch silme kapalı
- Conversation resolution zorunlu
- Review opsiyonel (count=0 — tek dev için; ekip büyüyünce 1)
- Status check'ler **manuel UI'dan eklenir** (workflow'lar ilk başarılı run sonrası görünür olur)

**`develop`:**
- Doğrudan push'a izin (lokal akış için)
- Force-push kapalı, branch silme kapalı

### 4.3 GitHub Repo Ayarları
- Default branch: `develop`
- Sadece **squash merge** (lineer history)
- Merge sonrası branch otomatik silme
- Public repo (Apache-2.0 LICENSE otomatik tanındı)

### 4.4 Eklenecek (Faz 3)
- [ ] Slack/Discord deploy bildirimi (release sonrası)
- [ ] Image signing (cosign) + sigstore attestations
- [ ] Coverage trend (Codecov SaaS — Sonar zaten gösteriyor, opsiyonel)

---

## 5. Test Stratejisi

### 5.1 Test Piramidi

```
          ┌──────────┐
          │   E2E    │  Az sayıda — kritik akışlar (Playwright)
          ├──────────┤
          │Integration│ API endpoint'leri (gerçek DB, mock dış API)
          ├──────────┤
          │   Unit   │  Service helper'lar, formüller
          └──────────┘
            (en geniş taban)
```

### 5.2 Backend Test Yapısı (Mevcut — 159 test geçiyor)
```
backend/tests/
├── conftest.py                  # ✅ NullPool + per-request session + slowapi disable
├── unit/                        # 72 test
│   ├── test_security.py         # ✅ JWT, Fernet, bcrypt — 22 test
│   ├── test_aggregator.py       # ✅ WoW/MoM/breakdown/weight/staking — 22 test
│   ├── test_exchange_rates.py   # ✅ TCMB XML parse + fallback chain + cache — 9 test
│   ├── test_stocks_currency.py  # ✅ GBp/USD/TRY dönüşüm zinciri — 7 test
│   ├── test_tefas.py            # ✅ TefasService fiyat hesaplama (respx) — 6 test
│   └── test_advisor.py          # ✅ Anthropic SDK AsyncMock + token sayımı + prompt caching — 6 test
├── integration/                 # 88 test
│   ├── test_auth.py             # ✅ Register/login/refresh + verify-email + resend + 403 hard block — 21 test
│   ├── test_portfolio.py        # ✅ TEFAS holdings CRUD — 8 test
│   ├── test_idor.py             # ✅ Cross-user erişim koruma (BES dahil) — 8 test
│   ├── test_snapshot.py         # ✅ POST /portfolio/snapshot + idempotency + hata izolasyonu + USD/TL 503 + GBP/USD 201 devam + BES pension asset — 7 test
│   ├── test_bes_api.py          # ✅ BES holdings CRUD + Excel + validation — 8 test
│   ├── test_integrations_api.py # ✅ Exchange key encrypt/decrypt + leak — 5 test
│   ├── test_wallets_api.py      # ✅ Blockchain wallet CRUD — 5 test
│   ├── test_logout.py           # ✅ JWT blacklist + /auth/logout + idempotency + user izolasyonu — 8 test
│   ├── test_expenses_api.py     # ✅ Harcama CRUD + summary + filter + IDOR + auth — 18 test (Faz 3 MVP)
│   ├── test_stocks_api.py       # ⚠️ Henüz yazılmadı (preview/import/export)
│   ├── test_crypto_api.py       # ❌ Binance/iCrypex mock (Faz 2)
│   └── test_advice.py           # ❌ AI çağrı mock + kredi kontrolü (Faz 3)
└── e2e/
    └── (kullanılmıyor — E2E frontend Playwright'ta)
```

**Yeni test grupları (son sprint):**
- `test_expenses_api.py` (yeni dosya — Faz 3 MVP): 18 integration test — boş liste, create, geçersiz kategori 422, negatif/sıfır tutar 422; partial update + olmayan kayıt 404; delete; list filter year/month + category + geçersiz kategori 422 + tarih azalan sıralama; summary boş ay (total=0, count=0, by_category=[]) + dolu ay (kategori kırılımı + count); IDOR (User A → User B'nin expense'ini göremez/güncelleyemez/silemez); auth (token'sız 3 endpoint 401)
- `test_advisor.py` (yeni dosya): 6 unit test — `ANTHROPIC_API_KEY` boşsa `RuntimeError`; key set'liyse client oluşur; `generate()` `settings.claude_model` ve `settings.claude_max_tokens` kullanır; token usage `prompt_tokens`/`completion_tokens` olarak kaydedilir; horizon etiketi (orta vade / uzun vade) prompt'ta geçer; system prompt `cache_control: ephemeral` ile gönderilir (prompt caching). Anthropic SDK AsyncMock ile patch'lendi
- `test_logout.py` (yeni dosya): 8 integration test — `/auth/logout` 200 OK; logout sonrası access blacklist'te (auth endpoint 401); body refresh logout'tan sonra `/auth/refresh` 401; sadece access logout → refresh hala çalışır; logout auth gerektirir (token'sız 401); idempotent (ikinci logout 401 — token zaten blacklist'te); bozuk refresh body'de yutulur ama access yine blacklist'e alınır; User A logout User B'yi etkilemez
- `test_bes_api.py` (yeni dosya): 8 integration test — boş kullanıcı listesi, save & retrieve, idempotent PUT (replace-all), boş PUT, negatif değer reddi (`total_value_tl >= 0`), boş `plan_name` reddi (min_length=1), Excel export, Excel import
- `test_idor.py`: yeni `test_user_a_cannot_see_user_b_bes` + `test_no_token_returns_401`'e `/portfolio/bes/holdings` eklendi
- `test_snapshot.py`: yeni `test_snapshot_includes_bes_holdings` — BES manual değer snapshot'a `pension` asset_type ile geliyor
- `test_exchange_rates.py`: 9 unit test — TCMB XML parse (ForexBuying + Unit=100 normalize), USD/TL fallback chain (TCMB → exchangerate-api → RuntimeError), GBP/USD derive ve fallback, 5 dk in-memory TCMB cache davranışı
- `test_auth.py`: 14 test — kayıt akışı (risk profili, mail tetikleme), `verify-email` token doğrulama, expired token, `resend-verification` 202 davranışı, login 403 hard block

### 5.3 Test Araçları

| Araç | Kullanım |
|------|---------|
| pytest + pytest-asyncio | Ana koşucu (`asyncio_mode = "auto"`) |
| httpx AsyncClient | FastAPI endpoint testleri |
| respx | Dış HTTP mock (TEFAS, Yahoo, blockchain RPC) |
| pytest-cov | Coverage ölçüm |
| testcontainers (önerilen) | İzole PostgreSQL — mevcut conftest yerine |

### 5.4 Test Yazım Kuralları

#### Integration Test Kalıbı
```python
@pytest.mark.asyncio
async def test_get_crypto_no_integrations(client, auth_headers):
    resp = await client.get("/api/v1/portfolio/crypto", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"positions": [], "errors": {}}
```

#### Dış Servis Mock'lama
```python
@respx.mock
async def test_tefas_fetch():
    respx.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo").mock(
        return_value=httpx.Response(200, json={"data": [{"FONKODU": "GO3", ...}]})
    )
    svc = TefasService([{"code": "GO3", "quantity": 100, "name": ""}])
    assets = await svc.fetch()
    assert len(assets) == 1
```

#### Hata Senaryoları (Her Endpoint İçin)
- 401 — Auth header yok
- 404 — Olmayan kaynak
- 422 — Geçersiz input (Pydantic validation)
- 200/201 — Mutlu yol
- (Where applicable) 409, 429, 402

### 5.5 Coverage Hedefleri
| Katman | Hedef | Mevcut |
|--------|-------|--------|
| `core/security.py` (JWT, Fernet) | **%100** | ~%95 ✅ |
| `services/aggregator.py` (formüller) | **%100** | ~%85 ✅ |
| `api/v1/auth.py` | %95 | ~%80 ✅ |
| `services/advisor.py` (Anthropic SDK) | %80 | ~%85 ✅ |
| `services/exchange/*` | %70 | ~%5 (sadece logger import) |
| `services/blockchain/*` | %70 | ~%5 |
| Genel CI gate (faz bazlı) | Faz 1: %30 ✅ → Faz 2.5: %50 ✅ → Faz 3: %70 | ~%52.21 |

CI'da coverage threshold `ci-backend.yml::coverage-gate` ile uygulanır — düşüşte merge bloke.

### 5.6 Frontend Testleri (Kuruldu)
```
frontend/
├── vitest.config.ts            # ✅ jsdom + V8 coverage + %30 threshold
├── vitest.setup.ts             # ✅ @testing-library/jest-dom + cleanup
├── playwright.config.ts        # ✅ Chromium + retry x2 (CI)
├── __tests__/
│   └── api.test.ts             # ✅ setAuth/clearAuth — 3 test
├── playwright/
│   ├── login.spec.ts           # ✅ Token redirect senaryoları — 3 test
│   └── dashboard.spec.ts       # ✅ Register + login akışı — 2 test
└── (eksik) __tests__/components/CryptoPositionTable.test.tsx (Faz 2)
```

**Araçlar (kurulu):**
- Vitest 2.1 + jsdom + V8 coverage
- @testing-library/react, jest-dom, user-event
- @playwright/test (Chromium)
- MSW 2.6 (mock service worker — kurulu, henüz kullanılmadı)

**Frontend runtime bağımlılıkları (son eklenenler):**
- `recharts ^3.8.1` — `/dashboard/history`, `/dashboard/expenses`, `/dashboard/income` chart'ları için

**Backend runtime bağımlılıkları (son eklenenler):**
- `xlrd==1.2.0` — MKK e-Yatırımcı eski .xls binary parse için. **Sürüm pin'lendi:** xlrd 2.0+ xlsx desteğini kaldırdı; MKK dosyaları için 1.2.0 (xls binary destekli son sürüm) zorunlu. Yeni endpoint'ler: `POST /portfolio/tefas/import-mkk` + `POST /portfolio/stocks/import-mkk`.

**Yeni dış bağımlılıklar (10 zincir + ERC-20 discovery):**

| Servis | URL | Kullanım | Limit / Not |
|--------|-----|----------|-------------|
| mempool.space | `https://mempool.space/api` | Bitcoin UTXO `chain_stats` (xpub HD tarama) | Public, key yok; 10 dk in-memory cache + single-flight |
| Solana JSON-RPC | `https://api.mainnet-beta.solana.com` | `getBalance` + `getProgramAccounts` (Stake program filter) | Public RPC, key yok |
| Ethplorer | `https://api.ethplorer.io` (key='freekey') | Ethereum mainnet ERC-20 token discovery (dinamik) | Free tier ~50 istek/gün |
| Cardano / Algorand / Polkadot / Litecoin | Public REST API'ler | Adres bakiyesi (Faz A) | Single query / adres |

**Multi-RPC fallback listesi:**

| Zincir | RPC Sırası |
|--------|-----------|
| Ethereum | `settings.ethereum_rpc_url` → publicnode → merkle → 1rpc → ankr |
| Avalanche C | `settings.avalanche_c_rpc_url` → public-rpc → drpc → 1rpc |

İlk başarılı RPC seçilir; tümü fail olursa servis 0 döner ve snapshot bu kaynak için 0 değerle devam eder (best-effort).

**npm scripts:**
```
npm test           # Vitest run
npm run test:watch # Watch mode
npm run test:coverage
npm run e2e        # Playwright
npm run e2e:ui     # Playwright UI mode
```

---

## 6. Git Flow

### 6.1 Branch Yapısı
```
main          ← production (korumalı)
develop       ← aktif geliştirme birleştirme noktası (✅ mevcut)
│
├── feature/{ad}      → develop'a PR
├── hotfix/{ad}       → main'den dallanır, main + develop'a merge
└── release/{ver}     → develop'tan dallanır, main + develop'a merge
```

### 6.2 PR Kuralları (✅ Aktif)
- `main` korumalı: doğrudan push yasak
- Tüm merge'ler PR ile (en az 1 approval)
- CI yeşil olmadan merge yok
- Commit mesajları Türkçe, imperative: "Kredi sistemi ekle"
- Feature branch ömrü: merge sonrası silinir

### 6.3 Tipik Akış
```bash
git checkout develop && git pull
git checkout -b feature/yeni-ozellik
# kodla, test et
git commit -m "Açıklama: ne ve neden"
git push origin feature/yeni-ozellik
# GitHub'da PR aç
```

### 6.4 Release Akışı
```bash
git checkout -b release/1.0.0 develop
# version bump, changelog
git checkout main && git merge --no-ff release/1.0.0
git tag -a v1.0.0 -m "İlk public sürüm"
git checkout develop && git merge --no-ff release/1.0.0
git branch -d release/1.0.0
git push --tags
```

---

## 7. Monitoring ve Observability (Eklenecek)

### 7.1 Loglama (Mevcut)
- Python `logging` modülü; `INFO` level default
- Format: `%(asctime)s %(levelname)s %(name)s %(message)s`
- Önemli olaylar: login (success/fail), API entegrasyon hataları, scheduler events

### 7.2 Plan
- **Structured logging:** `structlog` (JSON log) — production'da Loki/ELK için zorunlu
- **Metrics:** Prometheus + Grafana (request latency, error rate, DB pool)
- **Tracing:** OpenTelemetry (Faz 4)
- **Error tracking:** Sentry (Python SDK + Next.js integration)

### 7.3 Alerting (Faz 3)
- Backend 5xx > %1 → Slack
- Anthropic API timeout > 5/dk → e-posta
- DB connection pool dolu → PagerDuty
- iyzico webhook fail → manuel inceleme

---

## 8. Backup ve Disaster Recovery (Faz 3)

### 8.1 Veritabanı
- **PITR (Point-in-Time Recovery):** WAL archiving + S3 (AWS Backup veya Restic)
- **Snapshot:** Günlük (gece 03:00), 30 gün retention
- **Test:** Aylık restore drill (staging'de)

### 8.2 Secrets
- Kubernetes Secrets → External Secrets Operator → AWS Secrets Manager / HashiCorp Vault
- Fernet master key (`FERNET_KEY`) **DEĞİŞTİRİLEMEZ** — değişirse tüm encrypted_key'ler okunamaz

---

## 9. Eksik / Eklenecek (TODO)

### Acil
- [x] Kubernetes manifest'lerini yaz (`k8s/` klasörü — kustomize, tek komutla deploy)
- [ ] Test coverage'ı %20'den %70'e çıkar
- [ ] Frontend test altyapısı (Vitest + RTL + Playwright)

### Orta Vade
- [ ] Tilt/Skaffold ile dev loop kur (Docker Compose'tan geçiş)
- [ ] Sentry entegrasyonu (backend + frontend)
- [ ] Prometheus + Grafana stack
- [ ] Vulnerability scan (Trivy) CI'da

### Uzun Vade
- [ ] OpenTelemetry distributed tracing
- [ ] Multi-region deployment (Faz 4 — uluslararası kullanıcılar)
- [ ] DR drill otomasyonu
