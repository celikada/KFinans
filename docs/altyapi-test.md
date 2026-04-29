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

### 1.2 CI Pipeline (Çalışıyor)
- ✅ GitHub Actions `ci.yml`: PostgreSQL test service, Ruff lint+format, pytest unit + integration, frontend `npm run build`

### 1.3 Yayın Pipeline (Çalışıyor)
- ✅ GitHub Actions `cd.yml`: develop → GHCR'a backend + frontend image push (commit SHA tag)

### 1.4 Eksik (Production'a Kadar)
- ❌ Kubernetes manifestleri (`k8s/` klasörü boş)
- ❌ Production deployment (kubectl rollout otomasyonu)
- ❌ Tilt/Skaffold dev loop (Docker Compose'tan geçiş — bilinçli teknik borç)
- ❌ Monitoring (Prometheus + Grafana)
- ❌ Centralized logging (Loki veya ELK)

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

## 3. Production: Kubernetes (Eklenecek)

### 3.1 Namespace ve Mevcut Durum
```
namespace: kfinans
mevcut:    postgres StatefulSet (bitnami/postgresql Helm) ✅
eklenecek: backend Deployment + Service
           frontend Deployment + Service
           nginx Ingress + cert-manager
           Secrets (DATABASE_URL, SECRET_KEY, FERNET_KEY, ANTHROPIC_API_KEY)
           ConfigMap (CORS_ORIGINS, NEXT_PUBLIC_API_URL)
```

### 3.2 Manifest Yapısı (Önerilen)
```
k8s/
├── namespace.yaml
├── secrets/
│   ├── kfinans-secrets.yaml         # External Secrets Operator veya sealed-secrets
│   └── README.md                     # `kubectl create secret` komutları
├── postgres/
│   ├── values.yaml                   # bitnami/postgresql Helm override
│   └── pvc.yaml                      # 50Gi PersistentVolumeClaim
├── backend/
│   ├── deployment.yaml               # replicas: 2, resources, probes
│   ├── service.yaml                  # ClusterIP :80 → :8000
│   ├── configmap.yaml                # CORS_ORIGINS vb.
│   └── hpa.yaml                      # HorizontalPodAutoscaler (CPU 70%)
├── frontend/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
└── ingress.yaml                       # nginx-ingress + cert-manager (Let's Encrypt)
```

### 3.3 Backend Deployment Özeti
```yaml
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: backend
        image: ghcr.io/celikada/kfinans-backend:{git-sha}
        ports: [{ containerPort: 8000 }]
        envFrom:
          - secretRef: { name: kfinans-secrets }
          - configMapRef: { name: kfinans-config }
        resources:
          requests: { cpu: 100m, memory: 256Mi }
          limits:   { cpu: 500m, memory: 512Mi }
        livenessProbe:
          httpGet: { path: /health, port: 8000 }
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet: { path: /health, port: 8000 }
          initialDelaySeconds: 10
          periodSeconds: 5
```

### 3.4 Image Tagging Stratejisi
```
ghcr.io/celikada/kfinans-backend:{git-sha}    # immutable, deployment için
ghcr.io/celikada/kfinans-backend:develop      # son develop build
ghcr.io/celikada/kfinans-backend:v1.0.0       # release tag
ghcr.io/celikada/kfinans-backend:latest       # KULLANILMAYACAK — kafa karıştırıcı
```

---

## 4. CI/CD Pipeline

### 4.1 CI Akışı (`.github/workflows/ci.yml`) — Çalışıyor
```yaml
on: [pull_request, push]
jobs:
  backend:
    services: postgres:16
    steps:
      - pip install -e ".[dev]"
      - ruff check . && ruff format --check .
      - pytest --cov=app --cov-report=xml
  frontend:
    steps:
      - npm ci
      - npm run lint
      - npm run build
```

### 4.2 CD Akışı (`.github/workflows/cd.yml`) — Çalışıyor
```yaml
on:
  push:
    branches: [develop, main]
jobs:
  build-and-push:
    steps:
      - docker build → ghcr.io/.../{git-sha}
      - docker push
  # production deploy: manuel veya `kubectl rollout` (Faz 3'te otomatize)
```

### 4.3 Eklenecek
- [ ] Test coverage `Codecov` veya `Coveralls`'a yüklensin
- [ ] `kubectl rollout` otomasyonu (main → production)
- [ ] Slack/Discord deploy bildirimi
- [ ] Vulnerability scan (Trivy) — image push öncesi

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

### 5.2 Backend Test Yapısı
```
backend/tests/
├── conftest.py                  # async engine, test DB, client, auth_headers
├── unit/
│   ├── test_tefas.py            # ✅ TefasService fiyat hesaplama (respx mock)
│   ├── test_aggregator.py       # ❌ TL normalize, calculate_changes
│   └── test_advisor.py          # ❌ Prompt formatting, token sayımı
├── integration/
│   ├── test_auth.py             # ✅ Login/refresh; eksik: register testi
│   ├── test_portfolio.py        # ⚠️ Sadece TEFAS holdings; eksik: crypto, wallets, stocks
│   ├── test_stocks.py           # ❌ Stocks CRUD + Yahoo mock
│   ├── test_wallets.py          # ❌ Blockchain wallet CRUD
│   ├── test_integrations.py     # ❌ Exchange key encrypt/decrypt
│   └── test_advice.py           # ❌ AI çağrı mock + kredi kontrolü (Faz 3)
└── e2e/
    └── test_tefas_flow.py       # ❌ login → holding kaydet → preview → export
```

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
| `services/` (iş mantığı) | %85+ | ~%30 |
| `api/v1/` (endpoint'ler) | %80+ | ~%20 |
| `core/` (auth, deps) | %90+ | ~%50 |
| Genel | %70+ | ~%20 |

CI'da coverage düşüşü merge'i bloklayacak (Faz 2'de aktif edilecek).

### 5.6 Frontend Testleri (Henüz Yok)
```
frontend/__tests__/
├── unit/
│   └── api.test.ts                  # lib/api.ts fonksiyonları (msw mock)
├── components/
│   ├── CryptoPositionTable.test.tsx
│   └── LoginForm.test.tsx
└── e2e/
    └── login-flow.spec.ts            # Playwright
```

Araçlar: **Vitest** + React Testing Library + **MSW** + **Playwright**

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
- [ ] Kubernetes manifest'lerini yaz (`k8s/` klasörü)
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
