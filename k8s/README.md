# KFinans Kubernetes Deploy

Modüler monolit mimari için minimum production deploy seti.

## Klasör İçeriği

| Dosya | Amaç |
|-------|------|
| `namespace.yaml` | `kfinans` namespace + PodSecurity restricted label |
| `configmap.yaml` | Non-secret env (CORS, ALLOWED_HOSTS, EMAIL_FROM, RPC URL'leri, scheduler ayarları) |
| `secrets.example.yaml` | Secret şablonu — `secrets.yaml` olarak kopyalayıp doldurun (gitignore) |
| `postgres.yaml` | PostgreSQL 16 StatefulSet + 50Gi PVC + headless Service |
| `backend.yaml` | FastAPI Deployment (replicas: 1) + initContainer (alembic upgrade) + Service |
| `frontend.yaml` | Next.js Deployment (replicas: 2, standalone build) + Service |
| `ingress.yaml` | Traefik Ingress + cert-manager TLS + Middleware'ler (redirect-https + body-size-limit) |
| `backup-cronjob.yaml` | Günlük 02:00 (Europe/Istanbul) Postgres logical backup |
| `kustomization.yaml` | Kustomize index — tek komutla deploy |

---

## Ön Koşullar

Cluster'da yüklü olmalı:
- **kubectl** (1.28+) — local'den `kubeconfig` ile erişim
- **Traefik** — K3s default ingress controller (Oracle prod cluster K3s; Traefik CRD'leri Middleware için gerekli)
- **cert-manager** v1.14+ + `ClusterIssuer` `letsencrypt-prod` (gerçek email ile)
- **DNS:** `kfinans.app` ve `www.kfinans.app` ingress LoadBalancer IP'sine (Oracle VM public IP) yönlendirilmiş olmalı
- **Container registry erişimi:** image'ler `docker.io/celikada/kfinans-{backend,frontend}` (Docker Hub) — public pull, secret gerektirmez

> Mimari notu: tek host modeli (`kfinans.app`) + path-based routing (`/api/*` → backend, `/*` → frontend). `.app` TLD HSTS preload listesinde olduğu için tarayıcı HTTPS'i zorlar; ek olarak `redirect-https` Middleware HTTP isteğini 308 ile HTTPS'e yönlendirir.

---

## İlk Kurulum (Production)

### 1. Namespace + ConfigMap

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
```

> ConfigMap'teki `ALLOWED_HOSTS`, `CORS_ORIGINS`, `EMAIL_FROM`, `FRONTEND_URL` değerlerini kendi domain'inize göre güncellemeyi unutmayın. `NEXT_PUBLIC_API_URL` boş bırakılır (göreceli `/api/v1` → ingress).

### 2. Secret'ları oluştur

**Yeni kurulum (önerilen — SealedSecrets):**

```bash
# Önce sealed-secrets controller kur (kube-system'da)
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  -n kube-system --version 2.17.0 \
  --set fullnameOverride=sealed-secrets-controller
kubectl -n kube-system rollout status deployment/sealed-secrets-controller

# k8s/sealed-secrets.yaml repo'dan apply (encryptedData controller private key
# ile decrypt eder; lokal repo'ya commit edilebilir — encrypted)
kubectl apply -f k8s/sealed-secrets.yaml
```

**Master key BACKUP (KRİTİK — kayıp durumunda decrypt yapılamaz):**

```bash
# K8s cluster yeniden kurulursa veya controller kaybolursa bu key gerekli
kubectl -n kube-system get secret \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > /backup/sealed-secrets-master.key

# Bu dosya `.credentials.local.md` §7'de + offline yedek (Bitwarden/USB) saklanmalı
```

**Manuel Secret (ilk kurulum / DR fallback):**

```bash
kubectl create secret generic kfinans-secrets \
  --namespace=kfinans \
  --from-literal=DATABASE_URL='postgresql+asyncpg://kfinans:<STRONG_PWD>@postgres:5432/kfinans' \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=FERNET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  --from-literal=RESEND_API_KEY='re_xxx' \
  --from-literal=ANTHROPIC_API_KEY='sk-ant-xxx' \
  --from-literal=POSTGRES_PASSWORD='<STRONG_PWD>' \
  --from-literal=POSTGRES_USER='kfinans' \
  --from-literal=POSTGRES_DB='kfinans'
```

**Mevcut Secret'i SealedSecret'e dönüştürme:**

```bash
# Public cert çek
kubeseal --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system --fetch-cert > pub-cert.pem

# Mevcut Secret'i seal et
kubectl -n kfinans get secret kfinans-secrets -o yaml | \
  grep -v '^\s*creationTimestamp\|^\s*resourceVersion\|^\s*uid' | \
  kubeseal --cert pub-cert.pem --format yaml > k8s/sealed-secrets.yaml
```

> **NOT:** SealedSecrets yalnızca GitOps commit'i için secret'ları korur (asymmetric encrypted). etcd at-rest encryption ayrı: K3s start flag `--secrets-encryption=true` veya `EncryptionConfiguration` apply gerekli.
>
> **NOT 2:** `DATABASE_URL`'deki `<STRONG_PWD>` ile `POSTGRES_PASSWORD` aynı olmalı.

### 3. Image'leri pushla (Docker Hub)

Lokal build + push (manuel; CI/CD bunu otomatik yapar):

```bash
TAG=v0.1.0-rc3
docker login -u celikada  # PAT ile

docker build --target production -t docker.io/celikada/kfinans-backend:$TAG backend/
docker push docker.io/celikada/kfinans-backend:$TAG

docker build \
  --build-arg NEXT_PUBLIC_API_URL="" \
  -t docker.io/celikada/kfinans-frontend:$TAG frontend/
docker push docker.io/celikada/kfinans-frontend:$TAG
```

> CI/CD: GitLab self-hosted (`gitlab.192.168.3.191.nip.io`) Kaniko ile build edip Docker Hub'a pushlar (`.gitlab-ci.yml::build` job). GitHub Actions `release.yml` paralel olarak GHCR'a push edebilir (atıl durumda — flag #4360519 sonrası deploy yolu GitLab CI üzerinden).

### 4. Manifest tag override + apply

```bash
# kustomize transformer ile tag set et (manifest'lerdeki :v0.0.0 placeholder)
cd k8s/
kustomize edit set image docker.io/celikada/kfinans-backend=docker.io/celikada/kfinans-backend:$TAG
kustomize edit set image docker.io/celikada/kfinans-frontend=docker.io/celikada/kfinans-frontend:$TAG

# Apply (postgres + backend + frontend + ingress + backup-cronjob)
kubectl apply -k .
```

(Veya manuel: `kubectl apply -f namespace.yaml -f configmap.yaml -f postgres.yaml -f backend.yaml -f frontend.yaml -f ingress.yaml -f backup-cronjob.yaml`)

### 5. Doğrulama

```bash
kubectl get pods -n kfinans
kubectl logs -n kfinans -l app=backend --tail=50
kubectl get ingress -n kfinans

# Ingress TLS hazır olunca (Let's Encrypt challenge ~30sn):
curl -sI https://kfinans.app/health
# HTTP/2 200
# content-type: application/json
curl -s https://kfinans.app/health
# {"status":"ok","version":"0.1.0"}
```

---

## Migration (Yeni sürüm deploy)

`backend.yaml` initContainer'ı her pod start'ında `alembic upgrade head` çalıştırır. Manuel deploy:

```bash
TAG=v0.1.0-rc4
kubectl -n kfinans set image deployment/backend \
  backend=docker.io/celikada/kfinans-backend:$TAG \
  alembic-upgrade=docker.io/celikada/kfinans-backend:$TAG
kubectl -n kfinans set image deployment/frontend \
  frontend=docker.io/celikada/kfinans-frontend:$TAG
kubectl -n kfinans rollout status deployment/backend
kubectl -n kfinans rollout status deployment/frontend
```

Rolling update sırasında zero-downtime hedeflenir; `maxUnavailable: 0`.

GitLab CI `deploy-production` job bunu otomatik yapar (`v*.*.*` semver tag push edildiğinde manuel onayla).

---

## Probe Host Header (TrustedHostMiddleware uyumlu)

`ALLOWED_HOSTS=["kfinans.app","www.kfinans.app"]` (sıkı) olunca kubelet probe'ları default `Host: <pod-ip>` ile vurur ve `TrustedHostMiddleware` 400 döndürür. Çözüm: `livenessProbe`/`readinessProbe`/`startupProbe`'a `httpHeaders.Host: kfinans.app` ekledik (`backend.yaml`). Bu sayede `ALLOWED_HOSTS`'u `["*"]`'tan sıkıya çekebilirsiniz.

---

## Ölçeklendirme

```bash
kubectl scale deployment backend --replicas=4 -n kfinans
kubectl scale deployment frontend --replicas=4 -n kfinans
```

> Backend için `replicas=1` default (slowapi MemoryStorage; 2+ replica = 2x rate limit kotası). Redis backend eklenince (`REDIS_URL` ConfigMap'e set + slowapi storage_url) `replicas` 2+'a çıkarın.

HPA için bu klasöre `hpa.yaml` ekleyip `kustomization.yaml`'a register edebilirsiniz.

---

## Yedekleme

Otomatik: `backup-cronjob.yaml` her gün 02:00 Europe/Istanbul `pg_dump | gzip` → `postgres-backups` PVC (5Gi, 30 gün retention).

Manuel restore:

```bash
kubectl exec -n kfinans postgres-0 -- bash -c \
  "gunzip -c /backups/kfinans-2026-05-20_*.sql.gz | psql -U kfinans kfinans"
```

> Backup PVC'ye erişmek için bir job kullanın (postgres-backups read-only). Sonraki seviye: Oracle Object Storage (S3-compatible) sync, PITR için pgBackRest.

---

## Bilinen Eksikler / TODO

- [ ] HPA (HorizontalPodAutoscaler) — CPU/RAM bazlı autoscale
- [ ] NetworkPolicy — frontend yalnız backend'e, backend yalnız postgres'e
- [ ] PodDisruptionBudget — node maintenance sırasında min replica koruması
- [ ] Prometheus + Grafana — metric scraping (OBS-001 OTel hazır)
- [ ] PgBouncer — connection pool
- [ ] External-secrets / SealedSecrets — secret rotation
- [ ] Backup off-cluster sync (Oracle Object Storage / S3)
- [ ] ServiceAccount + RBAC (automountServiceAccountToken: false default)
