# KFinans Kubernetes Deploy

Modüler monolit mimari için minimum production deploy seti.

## Klasör İçeriği

| Dosya | Amaç |
|-------|------|
| `namespace.yaml` | `kfinans` namespace |
| `configmap.yaml` | Non-secret env (CORS, EMAIL_FROM, RPC URL'leri) |
| `secrets.example.yaml` | Secret şablonu — `secrets.yaml` olarak kopyalayıp doldurun (gitignore) |
| `postgres.yaml` | PostgreSQL 16 StatefulSet + 50Gi PVC + headless Service |
| `backend.yaml` | FastAPI Deployment (replicas: 2) + initContainer (alembic upgrade) + Service |
| `frontend.yaml` | Next.js Deployment (replicas: 2, standalone build) + Service |
| `ingress.yaml` | nginx-ingress + cert-manager TLS, `api.kfinans.app` + `app.kfinans.app` |
| `kustomization.yaml` | Kustomize index — tek komutla deploy |

---

## Ön Koşullar

Cluster'da yüklü olmalı:
- **kubectl** (1.28+) — local'den `kubeconfig` ile erişim
- **ingress-nginx-controller** — `helm install ingress-nginx ingress-nginx/ingress-nginx`
- **cert-manager** + bir `ClusterIssuer` (örn. `letsencrypt-prod`) — TLS sertifikası için
- **DNS:** `api.kfinans.app` ve `app.kfinans.app` ingress-controller LoadBalancer IP'sine yönlendirilmiş olmalı
- **Container registry** — `kfinans-backend:latest` ve `kfinans-frontend:latest` image'leri pushlanmış olmalı (ya da değiştirin)

---

## İlk Kurulum (Production)

### 1. Namespace + ConfigMap

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
```

> ConfigMap'teki `EMAIL_FROM`, `FRONTEND_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL` değerlerini kendi domain'inize göre güncellemeyi unutmayın.

### 2. Secret'ları oluştur (kubectl ile, YAML dışı — daha güvenli)

```bash
kubectl create secret generic kfinans-secrets \
  --namespace=kfinans \
  --from-literal=DATABASE_URL='postgresql+asyncpg://kfinans:<STRONG_PWD>@postgres:5432/kfinans' \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=FERNET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  --from-literal=RESEND_API_KEY='re_xxx' \
  --from-literal=ANTHROPIC_API_KEY='sk-ant-xxx' \
  --from-literal=POSTGRES_PASSWORD='<STRONG_PWD>'
```

> `DATABASE_URL`'deki `<STRONG_PWD>` ile `POSTGRES_PASSWORD` aynı olmalı.

### 3. Image'leri pushla

```bash
# Backend (production target)
docker build --target production -t <registry>/kfinans-backend:<tag> backend/
docker push <registry>/kfinans-backend:<tag>

# Frontend (standalone production)
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.kfinans.app \
  -t <registry>/kfinans-frontend:<tag> frontend/
docker push <registry>/kfinans-frontend:<tag>
```

`backend.yaml` ve `frontend.yaml`'da `image:` alanlarını gerçek registry/tag'e güncelleyin.

### 4. Postgres + Backend + Frontend + Ingress

```bash
kubectl apply -k k8s/
```

(Veya manuel: `kubectl apply -f k8s/postgres.yaml -f k8s/backend.yaml -f k8s/frontend.yaml -f k8s/ingress.yaml`)

### 5. Doğrulama

```bash
kubectl get pods -n kfinans
kubectl logs -n kfinans -l app=backend --tail=50
kubectl get ingress -n kfinans
curl -k https://api.kfinans.app/health  # {"status":"ok",...}
```

---

## Migration (Yeni sürüm deploy)

`backend.yaml` initContainer'ı her pod start'ında `alembic upgrade head` çalıştırır. Yeni image push'ladığınızda:

```bash
kubectl set image deployment/backend backend=<registry>/kfinans-backend:<new-tag> -n kfinans
kubectl set image deployment/backend alembic-upgrade=<registry>/kfinans-backend:<new-tag> -n kfinans
kubectl rollout status deployment/backend -n kfinans
```

Rolling update sırasında zero-downtime hedeflenir; `maxUnavailable: 0`.

---

## Ölçeklendirme

```bash
kubectl scale deployment backend --replicas=4 -n kfinans
kubectl scale deployment frontend --replicas=4 -n kfinans
```

Daha sonra HPA (HorizontalPodAutoscaler) eklenebilir; bu klasöre `hpa.yaml` ekleyip `kustomization.yaml`'a register edin.

---

## Yedekleme

Postgres PVC manuel snapshot için:

```bash
# Cluster'da volume snapshot driver kuruluysa:
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-$(date +%Y%m%d)
  namespace: kfinans
spec:
  source:
    persistentVolumeClaimName: postgres-data-postgres-0
EOF
```

Faz 3'te managed PostgreSQL hizmetlerine (RDS, Cloud SQL) geçiş düşünülebilir.

---

## Bilinen Eksikler / TODO (Faz 3)

- [ ] HPA (HorizontalPodAutoscaler) — CPU/RAM bazlı autoscale
- [ ] NetworkPolicy — frontend yalnız backend'e, backend yalnız postgres'e
- [ ] PodDisruptionBudget — node maintenance sırasında min replica koruması
- [ ] Prometheus + Grafana — metric scraping
- [ ] PgBouncer — connection pool
- [ ] CronJob — `revoked_tokens` cleanup (expires_at < now())
- [ ] External-secrets / SealedSecrets — secret rotation
- [ ] Backup CronJob — pg_dump → S3
