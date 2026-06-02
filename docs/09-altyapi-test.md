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

### 1.2 CI/CD Platformu — GitLab Primary, GitHub Salt-Mirror

> **Önemli:** Birincil (ve fiilen tek çalışan) CI/CD **self-hosted GitLab**'tedir (`gitlab.192.168.3.191.nip.io`). GitHub `.github/workflows/*` dosyaları repoda durur ve "active/enabled" görünür ama **0 run üretir** — `celikada` hesabı flag'li (Ticket #4360519). GitHub yalnızca **salt-mirror** (develop/main/tags) olarak kullanılır. Aşağıdaki tüm pipeline gerçeği `.gitlab-ci.yml`'dir.

### 1.2.1 GitLab CI Pipeline (Çalışıyor — 7 stage)
`.gitlab-ci.yml` — 7 stage: `lint → test → quality → build → scan → deploy → smoke`.

- ✅ **lint** — `backend-lint` (ruff format --check + ruff check, `allow_failure` kaldırıldı 2026-05-21) + `frontend-lint` (ESLint, `allow_failure` kaldırıldı)
- ✅ **test** — `backend-test` (Docker python:3.12 + postgres service; pytest --cov coverage.xml + junit; cobertura report artifact) + `frontend-test` (`npm run test:coverage` → lcov.info; vitest threshold %15)
- ✅ **quality** — `sonarqube-scan`: **self-hosted SonarQube** (`http://sonar.192.168.3.191.nip.io`, `projectKey=KFinans`). **Gate BLOCKING (2026-06-01):** `-Dsonar.qualitygate.wait=true` + `allow_failure` kaldırıldı → gate kırmızıysa pipeline durur. Gate koşulları: `new_violations=0` + `new_security_hotspots_reviewed=100%` + `new_coverage>=80%`. Sadece protected branch (develop/main) + MR + tag'lerde çalışır (`SONAR_TOKEN` Protected variable).
- ✅ **build** — `backend-build` + `frontend-build`: **Kaniko** (`gcr.io/kaniko-project/executor:v1.23.2-debug`) → **Docker Hub** (`celikada/kfinans-{backend,frontend}`). Sadece `main`, `develop` ve tag'lerde (feature/hotfix branch'lerinde build yok). Tag → ek olarak `:latest` + `:<tag>` push'lar.
- ✅ **scan** — `trivy-image-scan` (2026-06-01): **Trivy** (`aquasec/trivy:0.58.0`) Docker Hub'a push edilen tag image'larını tarar. `--severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed` → açık varsa **deploy ÖNCESİ** pipeline durur. `build → scan → deploy` sırası deploy'u gate'ler. Sadece semver tag'lerde. Trivy DB cache'li; Docker Hub auth `TRIVY_USERNAME/PASSWORD`.
- ✅ **deploy** — `deploy-production`: `when: manual` + **sadece semver tag** (`/^v\d+\.\d+\.\d+/`). SSH → Oracle K3s `kubectl set image deployment/{backend,frontend}` + `rollout status --timeout=5m`. `environment: production` (https://kfinans.app).
- ✅ **smoke** — `smoke-test` (2026-06-01): deploy SONRASI (`needs: deploy-production`). DEPLOY-001 4-adımlı curl gate: frontend HTTPS+cert, `/health` `{status:ok}`, bogus login→401, HSTS header. Deploy bozuksa pipeline kırmızı (alarm). Sadece semver tag'lerde.

### 1.2.2 Manuel Deploy Tetikleme
`deploy-production` `when: manual` olduğu için GitLab UI'dan "play" butonuyla **veya** GitLab API ile tetiklenir:

```bash
# 1) Tag'in pipeline'ındaki deploy job ID'sini bul
curl -s --header "PRIVATE-TOKEN: $GITLAB_PAT" \
  "http://gitlab.192.168.3.191.nip.io/api/v4/projects/<PROJECT_ID>/pipelines/<PIPELINE_ID>/jobs" \
  | jq '.[] | select(.name=="deploy-production") | {id, status}'

# 2) Manuel job'u oynat (play)
curl -s --request POST --header "PRIVATE-TOKEN: $GITLAB_PAT" \
  "http://gitlab.192.168.3.191.nip.io/api/v4/projects/<PROJECT_ID>/jobs/<JOB_ID>/play"
```

### 1.3 Yayın Pipeline ✅ ÇALIŞIYOR (GitLab)
- ✅ Semver tag push (`v*.*.*`) → build (Kaniko → Docker Hub) → **manuel onaylı** deploy-production
- ✅ Docker Hub `celikada/kfinans-backend:{tag}` + `kfinans-frontend:{tag}` (+ `:{short-sha}` + `:{ref-slug}` + tag'de `:latest`)
- ✅ kubectl set image + rollout status (5 dk timeout)
- ✅ Son production deploy: **`v0.1.0-rc16`** — rollout + smoke yeşil (backend `/health` ok, frontend up, security header'lar mevcut)
- ✅ Container image Trivy scan (`trivy-image-scan`, scan stage, HIGH/CRITICAL `--ignore-unfixed`, deploy ÖNCESİ gate) + curl smoke gate (`smoke-test`, smoke stage, deploy SONRASI) GitLab pipeline'ına eklendi (2026-06-01). Playwright @smoke şu an GitLab pipeline'ında otomatik değil; lokal `frontend/scripts/smoke.sh` ile doğrulanabilir.

### 1.4 GitHub Hesap Flag Durumu (#4360519)
- `celikada` hesabı **hâlâ flag'li** (2026-06-01). Workflow'lar "active" + Actions "enabled" görünür ama **0 run** üretir.
- SonarCloud OAuth bloklu → bu nedenle **self-hosted SonarQube**'a geçildi.
- CI/CD **tamamen GitLab'da**; GitHub sadece develop/main/tags salt-mirror.

### 1.5 Eksik (Production'a Kadar)
- ✅ Kubernetes manifestleri (`k8s/` klasörü — kustomize, tek komutla deploy) — bkz. §3
- ✅ Production deployment (GitLab semver tag → manuel deploy-production)
- ✅ Branch hijyeni (GitLab MR-only develop/main + GitHub mirror protected) — bkz. §6
- ✅ Container image vulnerability scan (Trivy) — GitLab `scan` stage `trivy-image-scan` (HIGH/CRITICAL `--ignore-unfixed`, deploy öncesi gate, sadece semver tag)
- ⚠️ Dependency scan (pip-audit + npm-audit + Dependabot) — GitHub workflow'da var ama çalışmıyor; GitLab'a taşınacak
- ❌ Tilt/Skaffold dev loop (Docker Compose'tan geçiş — bilinçli teknik borç)
- ❌ Monitoring (Prometheus + Grafana) — Faz 3
- ❌ Centralized logging (Loki veya ELK) — Faz 3

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

### 2.3 Lokal Test Ortamı (Windows)

> CI'ın birebir kopyası lokalde Docker üzerinden koşturulur. **Native Windows ile koşturmayın** — Windows Python 3.14 üzerinde `coincurve` (bip-utils bağımlılığı) C build'i patlar.

```bash
# Backend: Docker python:3.12 + postgres (CI ile aynı imaj)
# Modül bazlı (~30 sn):
docker compose run --rm backend pytest tests/unit/test_security.py -q
# Full suite (mount + coverage, ~28-30 dk):
docker compose run --rm backend pytest --cov=app --cov-report=term

# Frontend vitest — npx Windows'ta bozuk, node ile doğrudan çağır:
node node_modules/vitest/vitest.mjs run --pool=forks
```

**Ders (kayıtlı):** Backend commit öncesi `py -m ruff format --check .` + `py -m ruff check .` zorunlu (lint job `allow_failure` olmadan blocking — kırmızı pipeline = merge yok).

### 2.4 Bilinen Sorunlar (Cosmetic)
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
  ✅ secrets.example.yaml      — şablon
  ✅ sealed-secrets.yaml       — Bitnami SealedSecret (encryptedData; gerçek değerler
                                  master key ile cluster-içi decrypt; repoya commit edilir)
  ✅ postgres.yaml             — PostgreSQL 16 StatefulSet (replicas: 1, 50Gi PVC,
                                  headless Service, pg_isready probes)
  ✅ postgres-cert.yaml        — cert-manager SelfSigned Certificate (DB TLS, asyncpg
                                  ssl require — audit 2026-05-22 P0 #6)
  ✅ backend.yaml              — FastAPI Deployment (replicas: 1 — SEC-003 slowapi
                                  MemoryStorage tek-replica; Redis sonrası 2+'ya çıkar,
                                  RollingUpdate maxUnavailable: 0,
                                  initContainer wait-for-dns + alembic upgrade head,
                                  /health liveness + readiness + startup probes,
                                  PSS restricted securityContext, readOnlyRootFilesystem,
                                  resources limits cpu 500m / memory 1Gi (256→512→1Gi OOM fix),
                                  envFrom configmap+secret, ClusterIP)
  ✅ frontend.yaml             — Next.js standalone Deployment (ClusterIP)
  ✅ ingress.yaml              — Traefik (K3s default) + cert-manager TLS, TEK host
                                  kfinans.app path-based: /api + /health → backend,
                                  / → frontend; www.kfinans.app → frontend.
                                  HTTP→HTTPS redirect + 10MB body-size Traefik Middleware.
  ✅ networkpolicies/          — 7 policy: default-deny, allow-dns (CoreDNS + pod/service
                                  CIDR 53 fallback, a8496ca DNS egress fix),
                                  backend ingress/egress, frontend-ingress,
                                  postgres-ingress, backup-egress (zero-trust)
  ✅ backup-cronjob.yaml       — günlük 02:00 (Europe/Istanbul) pg_dump | gzip | age
                                  asimetrik encrypt → postgres-backups PVC, 30 gün retention
  ✅ kustomization.yaml        — kustomize index (tek komutla deploy)
  ✅ README.md                 — kapsamlı deploy rehberi

Frontend Dockerfile zaten production-ready (multi-stage standalone, next.config.ts'de
output: "standalone"). Backend Dockerfile production target da mevcut.
```

### 3.2 Önkoşullar
- Kubernetes cluster (K3s, 1.27+) + `kubectl` yapılandırılmış
- Traefik ingress controller (K3s default — ayrıca kurulum gerekmez)
- cert-manager kurulu + ClusterIssuer (`letsencrypt-prod`) tanımlı
- sealed-secrets controller kurulu (master key restore edilmiş)
- DNS: `kfinans.app` (apex A) + `www.kfinans.app` (CNAME) cluster ingress IP'sine bağlı (tek host path-based; subdomain split YOK)
- Docker Hub'a push edilmiş image'lar: `celikada/kfinans-backend:{tag}`, `celikada/kfinans-frontend:{tag}` (GitLab Kaniko build üretir)

### 3.3 Tek Komut Deploy
```bash
# 1) Secret: k8s/sealed-secrets.yaml repoda (encryptedData). sealed-secrets
#    controller master key cluster'da yüklü olmalı (DR durumunda Bitwarden/USB'den
#    restore — bkz. disaster-recovery.md §3.5). Yeni key eklemek için:
#      echo -n '<deger>' | kubeseal --raw --scope strict \
#        --namespace kfinans --name kfinans-secrets --cert <controller-pub.pem>
#    → çıktıyı sealed-secrets.yaml spec.encryptedData.<KEY>'e yaz.

# 2) Image tag güncelle (kustomization.yaml içindeki images: bloğu)

# 3) Deploy (namespace, configmap, sealed-secrets, postgres, ingress,
#    networkpolicies, backup-cronjob — hepsi kustomize ile)
kubectl apply -k k8s/

# 4) init container (wait-for-dns + alembic upgrade head) otomatik çalışır; izle
kubectl -n kfinans rollout status deploy/backend
kubectl -n kfinans rollout status deploy/frontend
```

> Ayrıntılı rehber (önkoşullar, secret oluşturma, image push, migration akışı, ölçeklendirme, yedekleme, Faz 3 TODO'ları): [`k8s/README.md`](../k8s/README.md)

### 3.4 Faz 3 TODO'ları (manifest seti dışında)
Eklendi (FAZ H / audit 2026-05-22): NetworkPolicy (7 policy zero-trust), SealedSecrets, `pg_dump` CronJob (age encrypted), DB TLS (postgres-cert), Pod Security Standards restricted. `revoked_tokens` cleanup APScheduler içinde (CronJob değil).
Kalan TODO: HPA (HorizontalPodAutoscaler), PodDisruptionBudget, Prometheus + Grafana, PgBouncer, Redis (slowapi multi-replica için), off-site backup (rclone + Object Storage — DR P0, bkz. disaster-recovery.md).

### 3.5 Image Tagging Stratejisi (Docker Hub — GitLab Kaniko)
```
celikada/kfinans-backend:{short-sha}    # immutable, her build (CI_COMMIT_SHORT_SHA)
celikada/kfinans-backend:{ref-slug}     # branch adı (develop / main)
celikada/kfinans-backend:v1.0.0         # semver tag → deploy bunu kullanır (set image)
celikada/kfinans-backend:latest         # SADECE tag build'lerde push edilir
```
> Deploy job `set image ...:$CI_COMMIT_TAG` ile **semver tag** image'ını çeker — `latest` deploy için kullanılmaz.

---

## 4. CI/CD Pipeline (GitLab — 7 stage)

```
                          ┌──────────────────────────┐
                          │  GitLab push / MR / tag  │
                          │  (gitlab.192.168.3.191)  │
                          └─────────────┬────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 1: lint                                                │
        │  backend-lint (ruff fmt+check)  |  frontend-lint (eslint)     │
        │  allow_failure KALDIRILDI (2026-05-21) — kırmızı = durur      │
        └───────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 2: test                                                │
        │  backend-test  (python:3.12 + postgres service, pytest --cov  │
        │                 → coverage.xml cobertura + junit)             │
        │  frontend-test (npm run test:coverage → lcov.info)            │
        └───────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 3: quality  →  self-hosted SonarQube                   │
        │  sonar.host=sonar.192.168.3.191  projectKey=KFinans           │
        │  qualitygate.wait=true + allow_failure KALDIRILDI (BLOCKING)  │
        │  Gate: new_violations=0 + hotspots_reviewed=100%              │
        │        + new_coverage>=80%   ← kırmızıysa pipeline DURUR       │
        │  Tetik: protected branch (develop/main) + MR + tag            │
        └───────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 4: build  →  Kaniko → Docker Hub                       │
        │  backend-build + frontend-build                               │
        │  celikada/kfinans-{svc}:{short-sha,ref-slug}                  │
        │  tag'de ek: :{tag} + :latest                                  │
        │  Sadece main / develop / tag (feature branch'te build yok)    │
        └───────────────────────────────────────────────────────────────┘
                                        │
                          ┌─────────────┴────────────┐
                          │  semver tag (v*.*.*)?    │
                          └─────────────┬────────────┘
                                        │ evet (scan/deploy/smoke sadece tag)
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 5: scan  →  Trivy image (trivy-image-scan)             │
        │  trivy image --severity HIGH,CRITICAL --exit-code 1           │
        │              --ignore-unfixed  (backend + frontend tag image) │
        │  Açık varsa pipeline DURUR — deploy ÖNCESİ gate               │
        └───────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 6: deploy-production   (when: manual — onay gerekir)    │
        │  SSH → Oracle K3s                                             │
        │    kubectl set image deployment/{backend,frontend}=:{tag}     │
        │    rollout status --timeout=5m (her ikisi)                    │
        │  ⚠ set image YALNIZCA — configmap/secret APPLY ETMEZ          │
        └───────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  STAGE 7: smoke  →  smoke-test (needs: deploy-production)      │
        │  curl gate: frontend HTTPS + /health {status:ok}              │
        │             + bogus login 401 + HSTS header                   │
        │  Deploy bozuksa pipeline KIRMIZI (alarm)                      │
        └───────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │ https://kfinans.app      │
                          │ (Oracle Cloud K3s)       │
                          │ son deploy: v0.1.0-rc16  │
                          └──────────────────────────┘
```

> **Kritik ders (DevOps):** `deploy-production` yalnızca `kubectl set image` yapar — ConfigMap/Secret/manifest **apply ETMEZ**. Secret veya configmap değişiklikleri ayrıca uygulanmalı + SealedSecret güncellenmeli; aksi halde GitOps reconcile eski değeri geri getirir. Bkz. operations-playbook.md §4.4 (RESEND secret fix runbook'u).

### 4.1 GitLab CI Job Listesi
| Job | Stage | Tetikleyici | Not |
|-----|-------|-------------|-----|
| `backend-lint` | lint | push, MR, tag | ruff format --check + ruff check; blocking |
| `frontend-lint` | lint | push, MR, tag | ESLint; blocking |
| `backend-test` | test | push, MR, tag | Docker python:3.12 + postgres; coverage.xml + junit artifact |
| `frontend-test` | test | push, MR, tag | vitest coverage → lcov.info; threshold %15 |
| `sonarqube-scan` | quality | develop/main + MR + tag | **BLOCKING** quality gate (wait=true) |
| `backend-build` / `frontend-build` | build | main, develop, tag | Kaniko → Docker Hub |
| `trivy-image-scan` | scan | semver tag (`/^v\d+\.\d+\.\d+/`) | Trivy HIGH/CRITICAL `--ignore-unfixed`; deploy öncesi gate |
| `deploy-production` | deploy | semver tag (`/^v\d+\.\d+\.\d+/`) | **`when: manual`** — UI play veya API |
| `smoke-test` | smoke | semver tag (`/^v\d+\.\d+\.\d+/`) | `needs: deploy-production`; 4-adım curl gate |

### 4.2 Coverage Ölçüm Fix (2026-06-01)
`backend/pyproject.toml [tool.coverage.run]`'a `concurrency = ["greenlet", "thread"]` eklendi. Async FastAPI handler'ları greenlet/thread içinde çalıştığı için coverage.py varsayılan ölçümde bunları **saymıyordu** → `new_coverage` yapay düşüktü. Fix sonrası CI `coverage.xml` doğru, SonarQube `new_coverage` **%48 → %96**. Frontend vitest LCOV de gate'e dahil (iki dilin coverage'ı birleşik değerlendiriliyor).

### 4.3 Branch Hijyeni (GitLab Primary + GitHub Mirror)
**GitLab (primary):**
- `develop` / `main` push = **No one** → sadece MR ile merge
- `release/*` + `hotfix/*` = maintainer push
- `remove_source_branch_after_merge = true` (merge'te source branch auto-delete)
- Feature branch'ler **SADECE GitLab**'a push edilir

**GitHub (salt-mirror — develop/main/tags):**
- `develop` + `main` **protected** (force-push + delete engelli)
- `enforce_admins = false` → mirror FF sync çalışabilir (mirror push admin yetkisiyle FF yapar)
- ⚠️ **Orphan branch riski:** GitLab merge'te source branch'i siler ama bu silme **GitHub mirror'a yansımaz** → yetim feature branch birikir. Periyodik temizlik gerekir (bu oturumda 10 yetim branch temizlendi).

### 4.4 Repo Ayarları
- Default branch: `develop` (her iki platformda)
- Squash merge (lineer history)
- GitHub Actions workflow'ları repoda durur ama **flag nedeniyle 0 run** — CI tamamen GitLab'da

### 4.5 Eklenecek (Faz 3)
- [x] GitLab pipeline'ına container image Trivy scan job (build sonrası, deploy öncesi gate) — `trivy-image-scan` (2026-06-01)
- [x] GitLab pipeline'ına curl smoke gate (deploy sonrası) — `smoke-test` (2026-06-01). Playwright @smoke hâlâ lokal/manuel.
- [ ] gitleaks + pip-audit + npm-audit GitLab'a taşı (GitHub workflow'da var ama çalışmıyor)
- [ ] Slack/Discord deploy bildirimi
- [ ] Image signing (cosign)
- [ ] Orphan GitHub mirror branch otomatik temizlik (cron)

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

### 5.2 Backend Test Yapısı (Mevcut — ~1196 test geçiyor: ~519 unit + ~677 integration)

> **Not:** Aşağıdaki dosya ağacı erken (Faz 1) durumunun illüstratif bir kesitidir; gerçek suite çok daha geniş (SonarQube gate sertleştirme oturumunda ~800 test eklendi — blockchain/exchange/servisler/API endpoint'leri). Güncel toplam ve coverage için §5.5 + CI `junit.xml`/`coverage.xml` esas alınır. Backend coverage **%95.83** (greenlet concurrency fix sonrası).

```
backend/tests/   (Faz 1 kesiti — illüstratif)
├── conftest.py                  # ✅ NullPool + per-request session + slowapi disable
├── unit/                        # (Faz 1: 72 test → güncel ~519)
│   ├── test_security.py         # ✅ JWT, Fernet, bcrypt — 22 test
│   ├── test_aggregator.py       # ✅ WoW/MoM/breakdown/weight/staking — 22 test
│   ├── test_exchange_rates.py   # ✅ TCMB XML parse + fallback chain + cache — 9 test
│   ├── test_stocks_currency.py  # ✅ GBp/USD/TRY dönüşüm zinciri — 7 test
│   ├── test_tefas.py            # ✅ TefasService fiyat hesaplama (respx) — 6 test
│   └── test_advisor.py          # ✅ Anthropic SDK AsyncMock + token sayımı + prompt caching — 6 test
├── integration/                 # (Faz 1: 88 test → güncel ~677)
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
| `services/exchange/*` | %70 | ✅ (SonarQube turunda kapsandı) |
| `services/blockchain/*` | %70 | ✅ (SonarQube turunda kapsandı) |
| Genel backend coverage | %70 | **%95.83** ✅ (greenlet concurrency fix sonrası) |

> **Coverage gate gerçeği:** Coverage düşüşü, GitLab `quality` stage'inde **self-hosted SonarQube** BLOCKING gate'i ile yakalanır (`new_coverage >= %80`, gerçekleşen ≈%96.3). GitHub `ci-backend.yml::coverage-gate` job'u dormant (Actions çalışmıyor). `pyproject.toml [tool.coverage.run] concurrency = ["greenlet","thread"]` async handler ölçümünü doğru sayar (yapay %48 → gerçek %96).

### 5.6 Frontend Testleri (Kuruldu — vitest ~396 test geçiyor + ~23 Playwright @smoke/e2e)

> CI vitest coverage threshold şu an **%15** (`frontend-test` job; test artırımı sonrası tekrar %30+'a çıkarılacak). Aşağıdaki ağaç erken kesittir.

```
frontend/   (erken kesit — illüstratif)
├── vitest.config.ts            # ✅ jsdom + V8 coverage (CI threshold %15)
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

### 6.2 MR Kuralları (✅ Aktif — GitLab primary)
- `develop` / `main` korumalı: GitLab'da push = No one → sadece **MR (Merge Request)** ile
- CI yeşil + **SonarQube gate yeşil** olmadan merge yok (blocking)
- Commit mesajları Türkçe, imperative: "Kredi sistemi ekle"
- Feature branch ömrü: merge sonrası GitLab otomatik siler (`remove_source_branch_after_merge`)
- Feature branch'ler sadece GitLab'a push edilir (GitHub'a değil)

### 6.3 Tipik Akış
```bash
git checkout develop && git pull gitlab develop
git checkout -b feature/yeni-ozellik
# kodla, test et — commit öncesi: py -m ruff format --check . && py -m ruff check .
git commit -m "Açıklama: ne ve neden"
git push gitlab feature/yeni-ozellik    # SADECE gitlab remote'a
# GitLab'da MR aç → develop'a
```
> `develop`/`main` GitHub mirror'ına push her zaman (her push'ta GitHub'a da gönderilir).

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

## 8. Backup ve Disaster Recovery

> Detaylı prosedür: [`operations/disaster-recovery.md`](operations/disaster-recovery.md).

### 8.1 Veritabanı
- **Logical backup (aktif):** `k8s/backup-cronjob.yaml` — günlük 02:00 Europe/Istanbul `pg_dump | gzip | age` (asimetrik encryption, private key cluster dışında), `postgres-backups` PVC, 30 gün retention.
- **Off-site sync (BEKLİYOR — DR P0):** rclone + Oracle Object Storage. Şu an tüm backup'lar tek lokasyonda (Oracle VM disk) → 3-2-1 ihlal. Backlog (master audit 2026-05-22).
- **PITR (planlı — Sprint 4):** WAL-G ile RPO 24 saat → 15 dk.
- **Restore drill (BEKLİYOR — DR P0):** production'da hiç test edilmedi; ilk drill cutover öncesi zorunlu.

### 8.2 Secrets
- **Mevcut:** Kubernetes Secrets + Bitnami **SealedSecrets** (`k8s/sealed-secrets.yaml`, encryptedData repoya commit edilir; master key cluster içinde decrypt eder, offline yedeklenir).
- **Planlı:** External Secrets Operator → cloud secret manager (Faz 3+).
- Fernet master key (`FERNET_KEY`) `MultiFernet` ile **rotate edilebilir** (primary + secondary key) — bkz. [`operations/infrastructure-runbook.md`](operations/infrastructure-runbook.md) §2.5.

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
