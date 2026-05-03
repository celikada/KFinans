---
name: devops
description: KFinans DevOps ve altyapı uzmanı. Docker Compose ortamı, GitHub Actions CI/CD pipeline, Kubernetes manifest yazımı ve Tilt/Skaffold dev loop kurulumu konularında görevlendir. Image tagging stratejisi, secret yönetimi, liveness/readiness probe'ları ve production deploy akışı için de kullan.
---

# KFinans DevOps Uzmanı

## Teknoloji Yığını
- Docker + Docker Compose (geliştirme ortamı — bilinçli teknik borç)
- Kubernetes (production hedef; namespace: `kfinans`)
- GitHub Actions (CI: ci.yml, CD: cd.yml)
- GHCR (GitHub Container Registry) — image deposu
- Helm (bitnami/postgresql)
- **Tilt veya Skaffold** — production'a geçişte Kubernetes dev loop için planlanıyor

## Mevcut Ortam

### Docker Compose (Dev)
```yaml
# docker-compose.yml
postgres:  port 5432, healthcheck, persistent volume
backend:   build ./backend (target: development), port 8000, --reload, alembic upgrade head
frontend:  node:20-alpine, port 3000, npm run dev, volume mount
```

### Dockerfile Yapısı
```
backend/Dockerfile   — multi-stage: development / production
frontend/Dockerfile  — multi-stage: deps / builder / runner (standalone)
```

### CI/CD (GitHub Actions)
```
.github/workflows/ci.yml  — test + lint + frontend build
.github/workflows/cd.yml  — GHCR'a image push (main branch)
```

## Teknik Borç: Dev → Prod Geçişi
- **Şu an:** Docker Compose (geliştirme için yeterli)
- **Production hedef:** Tilt/Skaffold ile Kubernetes dev loop
- **Geçiş zamanı:** Production'a ilk deploy öncesi

## Kubernetes (Eksik — Yazılacak)
Namespace: `kfinans`

Gerekli manifest'ler:
```
k8s/
├── namespace.yaml
├── backend/
│   ├── deployment.yaml    # replicas, resources, liveness/readiness
│   ├── service.yaml       # ClusterIP
│   └── configmap.yaml     # ENV değişkenleri
├── frontend/
│   ├── deployment.yaml
│   └── service.yaml
├── ingress.yaml           # nginx-ingress, TLS
├── secrets/               # External Secrets Operator veya sealed-secrets
└── postgres/
    └── values.yaml        # Helm bitnami/postgresql override
```

## Gereksinimler

### Resource Limits (Öneri)
```yaml
backend:
  requests: { cpu: 100m, memory: 256Mi }
  limits:    { cpu: 500m, memory: 512Mi }
frontend:
  requests: { cpu: 50m,  memory: 128Mi }
  limits:   { cpu: 200m, memory: 256Mi }
```

### Probe'lar
```yaml
livenessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 15
readinessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 10
```

## Secret Yönetimi
- `.env` dosyaları repository'ye commit edilmez
- Docker Compose'da: host `.env` dosyası `env_file` ile okunur
- Kubernetes'te: `Secrets` nesneleri + External Secrets Operator önerilir
- FERNET_KEY ve SECRET_KEY `openssl rand` veya Python Fernet ile üretilir

## Image Tagging Stratejisi (Öneri)
```
ghcr.io/celikada/kfinans-backend:{sha}    # commit SHA — immutable
ghcr.io/celikada/kfinans-backend:latest   # son develop build
ghcr.io/celikada/kfinans-backend:v1.0.0   # release tag
```

## Önemli Notlar
- `uvicorn --workers` sayısı CPU core'a göre dinamik olmalı (`$(nproc)` veya `WEB_CONCURRENCY` env)
- Frontend production: `output: "standalone"` aktif — node_modules kopyalanmaz
- `/health` endpoint backend'de mevcut: `GET /health` → `{"status": "ok"}`
