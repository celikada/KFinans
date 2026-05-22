# DevOps Audit Notları — 2026-05-22

> **Kapsam:** Oracle K3s production + GitLab self-hosted CI/CD + Docker Hub registry + SealedSecrets + cert-manager + 7 NetworkPolicy + age-encrypted backup. Vurgu: **taşınabilirlik** (vendor lock-in azaltma) ve **multi-cloud / cloud-agnostic** deploy hazırlığı.
>
> Audit tarihi: 2026-05-22 (post fix turu sonrası snapshot)
> Audit eden: DevOps audit pass
> İlgili dosyalar: `k8s/`, `.gitlab-ci.yml`, `docker-compose.prod.yml`, `docs/infrastructure-runbook.md`

---

## ✓ Mevcut Pozitif

1. **Pod Security Standards "restricted" tam uyum** — Backend, frontend, postgres ve backup pod'larında `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`. Audit-friendly (CIS, NSA Kubernetes Hardening), production grade.
2. **GitOps-safe secret yönetimi** — Bitnami SealedSecrets controller asimetrik şifreleme; `sealed-secrets.yaml` repo'ya commit edilebilir. Cluster compromise olmadan secret okunamaz. SealedSecret kontrolcüsü hem K3s'te hem standart Kubernetes'te aynı (taşınabilir).
3. **Backup encryption-at-rest (age)** — `pg_dump | gzip | age -r <pubkey>` asimetrik şifreleme; private key cluster dışında. Backup PVC çalınsa bile decrypt edilemez. Public key rotation + multi-recipient (`-r`) desteği mevcut.
4. **NetworkPolicy iterative redesign + default-deny zero-trust** — 7 policy (default-deny, allow-dns, backend-ingress/egress, frontend-ingress, postgres-ingress, backup-egress). Monolitik tek dosya yerine her adım smoke test ile doğrulandı; kustomization.yaml apply sırası dokümante.
5. **DB TLS in-transit (cert-manager selfsigned)** — Postgres `ssl=on`, `ssl_min_protocol_version=TLSv1.2`, cert init container chmod 0600 + chown 70 (postgres UID Alpine). `DATABASE_SSL_MODE=prefer` backward-compatible (mevcut bağlantılar kırılmaz).
6. **Refresh token rotation + revoked_tokens cleanup cron** — multi-replica güvenli `pg_try_advisory_lock` leader election (ARC-011); SCHEDULER_ENABLED env ile job override edilebilir.
7. **Self-hosted CI/CD bağımsızlığı** — GitLab iosrv + Kaniko (rootless build) + SonarQube self-hosted. GitHub flag #4360519'a bağımlılık koparıldı; CI/CD GitHub'sız çalışır.
8. **Image immutability (SHA + tag)** — Kaniko her image'ı `$CI_COMMIT_SHORT_SHA` + `$CI_COMMIT_REF_SLUG` + opsiyonel `$CI_COMMIT_TAG` ile pushlar; rollback için immutable referans her zaman mevcut.
9. **Resource requests/limits + 3-probe pattern** — Backend/frontend/postgres'in hepsinde CPU+memory request+limit. `startupProbe` cold-start window'a (150 sn'ye kadar) tolerans verir, `liveness` ve `readiness` ayrı yaşam döngüsü.
10. **Runbook + DR doc kaliteli** — `docs/infrastructure-runbook.md` DNS, email, K3s acil komutları, periyodik bakım takvimi, cert/DKIM rotation prosedürleri içeriyor.

---

## ⚠ Çelişti / Düzeltme Notları

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | **P0** | **Off-site backup yok** — `postgres-backups` PVC `local-path` ile node-local. Oracle VM kaybı / disk bozulması = backup da gider. `pg_dump | age` encrypted ama tek lokasyon. | Tam veri kaybı riski (RPO ∞). 3-2-1 backup kuralının "1 off-site" ayağı yok. | Faz I sprint zero: rclone sidecar container backup CronJob'ına eklenip Oracle Object Storage / Backblaze B2 / AWS S3 (provider-agnostic, S3-compatible) bucket'a sync. `S3_ENDPOINT` env override ile multi-cloud (Oracle, AWS, MinIO, R2) aynı manifest. |
| 2 | **P0** | **Restore drill (DR rehearsal) yok** — Backup alınıyor ama gerçek restore prosedürü production'da hiç test edilmedi. age private key kayıp/yanlış senaryosu için recovery prosedür belirsiz. | Gerçek incident'ta backup decryption fail edebilir; RTO ölçülmedi. | Çeyrek sonu DR drill: stage cluster'a son backup restore + uygulama bootstrap timing'i ölç. age private key sahibi rotation prosedürünü test etmeli (Bitwarden + USB + lokal AppData üçlüsü). |
| 3 | **P0** | **Hard-coded Oracle IP** (`.gitlab-ci.yml` L24: `141.144.243.54`) + **K3s spesifik kabul** (`storageClassName: local-path`, Traefik middleware, svclb LoadBalancer). | Multi-cloud / cloud-migrate impossible — bir provider'a kilitli. K3s'i kaldırıp standart EKS/GKE/AKS ya da on-prem RKE2'ye geçişte tüm manifest revize gerekir. | `kustomize` overlay yapısı: `k8s/base/` (cloud-agnostic) + `k8s/overlays/{oracle-k3s, aws-eks, gcp-gke, onprem-rke2}/`. Oracle'a özgü: IP, storageClass, ingressClassName. Base'de StorageClass referansı kaldırılır (overlay'de patch). |
| 4 | **P1** | **Single-node K3s + replicas: 1 backend** — DEVOPS-027 dokümante edilmiş ama PVC `local-path` migration blocker'ı sırasıyla çözülmedi. slowapi MemoryStorage (Redis yok) replicas=1'i zorunlu kılıyor. | HA yok; node yeniden başlatma = downtime. Single point of failure. | Faz I: (a) Redis sidecar veya StatefulSet (slowapi storage), (b) postgres için Longhorn veya Oracle Block Volume CSI, (c) frontend replicas zaten 2 — Pod Disruption Budget ekle. Backend replicas → 2-3. |
| 5 | **P1** | **`kubectl set image` deploy stratejisi** — `.gitlab-ci.yml::deploy-production` SSH + `sudo kubectl set image` ile çalışıyor; **GitOps değil**. Manifest desired-state cluster ile divergent (kustomize images: `v0.0.0` placeholder kalıyor). | Drift olabilir, audit trail eksik. CI fail → cluster gerçek state bilinmez. Manifest history Git'te ama runtime state ayrı. | ArgoCD veya Flux self-hosted (kümede çalışan operator) → Git push tag = ArgoCD sync. Aynı zamanda multi-cluster (oracle + aws + gcp staging) deploy aynı pipeline'la mümkün olur. |
| 6 | **P1** | **Docker Hub rate limit + tek registry** — `docker.io/celikada/kfinans-*` hard-coded `kustomization.yaml`'da. Docker Hub anonymous pull 100/6saat; auth'lu 200/6saat. Pod restart fırtınasında ImagePullBackOff riski. | Image pull throttling + Docker Hub down = deploy fail. Vendor lock-in (rotation zor). | (a) Manifest'lerde `image: REGISTRY/kfinans-backend:TAG` placeholder + kustomize overlay'de registry set. (b) Aynı image'ı paralel registry'lere push (GHCR + Docker Hub + Oracle OCIR) — Kaniko `--destination` çoklu. (c) `imagePullSecrets` ile auth'lu pull. |
| 7 | **P1** | **GitLab CI runner = iosrv (192.168.3.191) tek nokta** — Kaniko build, SonarQube scan, deploy SSH hepsi tek lokal sunucudan. iosrv ölü = tüm CI/CD donar. | CI/CD single point of failure. Lokal güç/network kesintisinde tag deploy edemezsiniz. | (a) Yedek runner Oracle VM'de kayıtlı tut (acil durum); (b) Pipeline kritik aşamaları GitHub Actions'a paralel mirror (build + push) — primary GitLab, fallback GHA. (c) Runner job timeout düşürülmüş + auto-retry tanımlanmış olmalı. |
| 8 | **P1** | **K3s `--secrets-encryption` (etcd at-rest encryption) durumu belirsiz** — SealedSecret application-level encryption sağlıyor, ama K8s API'ye decrypted hale gelince etcd'de plaintext yatabilir (K3s default sqlite/etcd). | Node disk dump = secret leak (Fernet master key, Anthropic API key dahil). | K3s install komutunda `--secrets-encryption` flag'ini doğrula; yoksa `EncryptionConfiguration` ekle (aescbc veya KMS provider). Cloud provider KMS (Oracle Vault, AWS KMS) → portability için interface (`pkcs11` veya KMS plugin). |
| 9 | **P2** | **NetworkPolicy `cidr: 0.0.0.0/0` egress backend için fazla geniş** — `03-backend-egress.yaml` HTTPS/HTTP için tüm internet açık. Cluster pod CIDR `10.42.0.0/16` hariç. | Backend compromise → lateral attack (mining pool, exfiltration). Egress allowlist (TEFAS, Yahoo, Anthropic, Resend, RPC endpoint'leri) yok. | (a) Hedef domain'leri DNS resolve → /32 CIDR allowlist; veya (b) Cilium NetworkPolicy ile FQDN allowlist (`toFQDNs`); veya (c) Forward proxy (Squid/Envoy) sidecar — sadece allow-list domain'lere proxy. Cloud-agnostic: Cilium veya Calico her yerde çalışır. |
| 10 | **P2** | **Secret rotation prosedürü yarı-otomatik** — Runbook §2.4 SSH + kubectl + manuel base64 kodlama. SealedSecret kullanılmıyor secret update'inde (sealed-secrets.yaml override edilmiyor). | Rotation hatası secret leak'e yol açabilir; rotation drift (lokal değer ≠ cluster). Audit log eksik. | (a) `kubeseal` CLI ile yeni sealed secret üret + commit + ArgoCD sync. (b) External Secrets Operator + bir vault (HashiCorp Vault self-hosted, AWS Secrets Manager, Oracle Vault) → rotation source-of-truth vault, cluster otomatik çeker. |
| 11 | **P2** | **CI/CD reusability — `.gitlab-ci.yml` proje-spesifik** — Lint/test/build job'ları KFinans-özel. Mayotek'in başka projeleri için (Flutter mobile, MCP server) copy-paste gerekir. | DRY violation; her proje için ayrı maintenance. | GitLab CI `include:` direktifi ile shared template: `mayotek/ci-templates` repo + `include: { project: 'mayotek/ci-templates', file: 'python-kaniko.yml' }`. Kaniko build pattern reuse edilebilir (sadece context + image name değişir). |
| 12 | **P2** | **`docker-compose.prod.yml` yetim/stale** — Production K3s ile deploy edilirken bu dosya repo'da duruyor (CI/CD tarafından kullanılmıyor). nginx self-managed cert directory başvurusu var ama production cert-manager kullanıyor. | Confusion: yeni developer hangisinin "gerçek prod" olduğunu bilemez. | Ya sil (cleanly) ya da `docker-compose.local-prod.yml` olarak rename + README'de "single-machine fallback deployment" şeklinde dokümante et. Production tek olmalı: K3s manifest. |
| 13 | **P2** | **Probe `Host: kfinans.app` header override hard-coded** — `backend.yaml` liveness/readiness `httpHeaders.Host: kfinans.app`. Cluster'ı `staging.kfinans.app` veya `test.example.org` ile reuse etmek için manifest patch gerekir. | Multi-environment (dev/staging/prod) için manifest fork olur. | Probe Host'ı configmap'ten al (`valueFrom` HTTP header'a doğrudan inject edilemez — kustomize overlay patch + envsubst CI step ya da `ALLOWED_HOSTS=["*"]` health-only override middleware'i). |
| 14 | **P2** | **Ingress Traefik-spesifik annotation'lar + Middleware CRD** — `traefik.ingress.kubernetes.io/router.middlewares`, `traefik.io/v1alpha1::Middleware`. EKS/GKE'de varsayılan nginx-ingress veya AWS ALB controller; Traefik kurulu değil. | Cloud-agnostic deploy zor — manifest fork gerekir. | Base manifest'i Gateway API (`gateway.networking.k8s.io`) standardına geçir — Traefik, nginx-ingress, Istio, Linkerd hepsi destekliyor. Veya overlay'de ingress class + annotation patch. |
| 15 | **P3** | **`.gitlab-ci.yml`'de hardcoded test SECRET_KEY/FERNET_KEY** (L86-87). CI-only ama "production-looking" pattern. | Static analysis tool false-positive; yanlışlıkla prod'da kullanılırsa zafiyet. | CI script içinde runtime'da `openssl rand` ile üret + env'e set. Ya da `ci-fake-key-${CI_PIPELINE_ID}` pattern (asla prod'da çalışmayacak şekilde). |
| 16 | **P3** | **Sonar `qualitygate.wait=false`** + `allow_failure: true` — quality gate fiilen pasif. | Code quality regression tespit edilmez (test coverage düşüşü, code smell artışı). | Custom quality gate tanımla (KFinans için makul threshold'lar): line coverage %50, new code %70, no new critical bug. `qualitygate.wait=true` + `allow_failure: false` tag releases için. |
| 17 | **P3** | **`successfulJobsHistoryLimit: 3`** backup-cronjob — son 3 başarılı job history. | Geçmiş backup job log'ları silinir; audit trail zayıflar. | Audit logs için `successfulJobsHistoryLimit: 7` (haftalık). Veya Sentry/OTel'e job result push. |
| 18 | **P3** | **Pod Disruption Budget (PDB) yok** — `kubectl drain` node maintenance'da uygulama tamamen down olabilir. | Plan node upgrade / kernel patch sırasında downtime. | `frontend` PDB `minAvailable: 1` (replicas: 2), `backend` PDB ek (replicas 2+'a çıkınca). PostgreSQL StatefulSet için PDB tek-replica olduğu sürece anlamsız (HA postgres ayrı epic). |

---

## Portability Roadmap

> Hedef: KFinans manifest'leri ve CI/CD pipeline'ı tek vendor'a bağımlı olmadan (Oracle / AWS / GCP / on-prem) deploy edilebilir hale getirmek.

- **Phase 1 — kustomize base + overlay separation (Q3 2026, ~2 sprint)**
  - `k8s/base/`: cloud-agnostic kısımlar (Deployment, Service, ConfigMap schema, PSS, network policies).
  - `k8s/overlays/oracle-k3s/`: hard-coded IP, `storageClassName: local-path`, Traefik annotation'ları, single-replica.
  - `k8s/overlays/aws-eks/`: `storageClassName: gp3`, nginx-ingress veya ALB, multi-AZ replicas, IRSA (IAM role for service account).
  - `k8s/overlays/gcp-gke/`: `storageClassName: standard-rwo`, Workload Identity, multi-region.
  - `k8s/overlays/onprem-rke2/`: Longhorn storage, MetalLB load balancer.
  - **Çıktı:** `kubectl apply -k k8s/overlays/aws-eks/` herhangi bir cluster'da çalışır.

- **Phase 2 — Storage abstraction (Q4 2026, ~1 sprint)**
  - Backup target'ı S3-compatible API'ye normalize et (Oracle Object Storage, AWS S3, MinIO, Cloudflare R2, Backblaze B2 hepsi destekliyor).
  - Backup CronJob `rclone` sidecar + `S3_ENDPOINT` + `S3_BUCKET` env. Default Oracle, overlay'de override.
  - PVC için CSI driver soyutlaması: base'de `storageClassName` belirtilmez, overlay'de patch.
  - DB için pgBackRest veya WAL-G ile sürekli WAL archiving → S3'e push (PITR / point-in-time recovery enable).

- **Phase 3 — GitOps + multi-cluster (Q1 2027, ~2 sprint)**
  - ArgoCD self-hosted (oracle K3s'te kurulu) → `argocd.kfinans.app`. Git repo source of truth.
  - Per-environment ApplicationSet (`prod-oracle`, `staging-aws`, `dev-local-kind`).
  - `kubectl set image` deploy yerine Git tag commit + ArgoCD auto-sync. Drift tespit otomatik.
  - Image pull: çoklu registry mirror (GHCR + Docker Hub + Oracle OCIR) + Kaniko `--destination` triplet.

- **Phase 4 — Cloud-managed services geçiş opsiyonu (Q2 2027+, opsiyonel)**
  - Postgres → RDS / Cloud SQL / Oracle Autonomous (managed); WAL backup cloud-native.
  - Secret store → External Secrets Operator + provider (AWS Secrets Manager, GCP Secret Manager, Oracle Vault).
  - DNS → Route53/Cloud DNS (Terraform-managed, Namecheap legacy).
  - **Trade-off:** managed servisler vendor lock-in artırır; sadece SaaS scale arttığında.

---

## CI/CD Reusability

### GitLab CI Multi-Project Template Extraction

`.gitlab-ci.yml` şu an monolitik (257 satır, KFinans-spesifik). Mayotek'in başka projeleri için (Flutter mobile, MCP server, future SaaS modules) reuse imkansız. Plan:

1. **Yeni repo:** `mayotek/gitlab-ci-templates` (private GitLab project).
2. **Template files:**
   - `templates/python-fastapi.yml` — backend-lint + backend-test (ruff + pytest pattern)
   - `templates/nextjs.yml` — frontend-lint + frontend-test (eslint + vitest pattern)
   - `templates/kaniko-build.yml` — generic Kaniko build with `$IMAGE_NAME` + `$REGISTRY` variables
   - `templates/sonar-scan.yml` — SonarQube self-hosted scan
   - `templates/k8s-deploy.yml` — generic `kubectl set image` SSH deploy (ya da ArgoCD sync)

3. **KFinans `.gitlab-ci.yml` shrinks to:**
   ```yaml
   include:
     - project: 'mayotek/gitlab-ci-templates'
       file: 'templates/python-fastapi.yml'
     - project: 'mayotek/gitlab-ci-templates'
       file: 'templates/nextjs.yml'
     - project: 'mayotek/gitlab-ci-templates'
       file: 'templates/kaniko-build.yml'
   variables:
     IMAGE_NAME_BACKEND: celikada/kfinans-backend
     IMAGE_NAME_FRONTEND: celikada/kfinans-frontend
   ```

4. **Versioning:** Template repo'da semver tag (`v1.0.0`), `include: { ref: 'v1.2.0' }` ile pin. Breaking change'lerde tüm projeler yavaş yavaş upgrade.

### Kaniko Build Pattern Reusability

`.kaniko-build:` anchor şu an iki kez kullanılıyor (backend + frontend, aynı `before_script`). YAML anchor → template'e çıkar:

```yaml
# templates/kaniko-build.yml
.kaniko-build:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.23.2-debug
    entrypoint: [""]
  before_script:
    - mkdir -p /kaniko/.docker
    - |
      cat > /kaniko/.docker/config.json <<EOF
      { "auths": { "$REGISTRY_URL": { "auth": "$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_TOKEN" | base64 -w0)" } } }
      EOF
  script:
    - >
      /kaniko/executor
      --context "$CI_PROJECT_DIR/$BUILD_CONTEXT"
      --dockerfile "$CI_PROJECT_DIR/$BUILD_CONTEXT/Dockerfile"
      --destination "$REGISTRY_URL/$IMAGE_NAME:$CI_COMMIT_SHORT_SHA"
      --destination "$REGISTRY_URL/$IMAGE_NAME:$CI_COMMIT_REF_SLUG"
      ${CI_COMMIT_TAG:+--destination "$REGISTRY_URL/$IMAGE_NAME:$CI_COMMIT_TAG"}
```

KFinans `.gitlab-ci.yml`:
```yaml
backend-build:
  extends: .kaniko-build
  variables:
    BUILD_CONTEXT: backend
    IMAGE_NAME: kfinans-backend
    REGISTRY_URL: docker.io
```

**Sonuç:** Yeni proje eklerken backend-build job'ı kopyalamadan, sadece `variables` ile override.

### Multi-Registry Mirror Pattern

Single-registry (Docker Hub) bağımlılığını kırmak için Kaniko aynı build'i çoklu registry'e push edebilir:

```yaml
--destination docker.io/celikada/kfinans-backend:$TAG
--destination ghcr.io/celikada/kfinans-backend:$TAG
--destination ocir.eu-frankfurt-1.oci.oraclecloud.com/.../kfinans-backend:$TAG
```

`imagePullSecrets` ile cluster da ImagePullPolicy fallback'ı yapar.

---

## Acil Aksiyon Önceliği (Önümüzdeki 4 Hafta)

1. **Hafta 1:** Off-site backup (rclone + S3-compatible) PR aç → P0 #1
2. **Hafta 2:** DR drill staging cluster → P0 #2 + age private key rotation test
3. **Hafta 3:** kustomize base/overlay split → P0 #3 + #4 + #14
4. **Hafta 4:** ArgoCD self-hosted kurulum + GitOps deploy → P1 #5 + #7
