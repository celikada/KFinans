# KFinans Portability Matrix

> **Amaç:** Vendor lock-in noktalarını ve multi-cloud/multi-tenant migration plan'ını tek dokümanda tutmak.
> **İlgili:** [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) §3 Taşınabilirlik

**Durum:** Taslak — Sprint 3'te P1 düşürme hedefli.

## 1. Vendor Lock-in Heat Map

| Servis | Şu an | Lock-in Risk | Alternatif/abstraction | Effort |
|--------|-------|--------------|------------------------|--------|
| **LLM** | Anthropic Claude API | YÜKSEK (SPOF) | `BaseLLMProvider` Protocol → OpenAI/Gemini fallback | 2-3 gün |
| **E-mail** | Resend (Tokyo) | ORTA | `BaseEmailProvider` → SendGrid/Mailgun | 1-2 gün |
| **K8s Distro** | K3s Oracle (`svclb-traefik`, `local-path`) | ORTA | Vanilla K8s + Traefik chart + Longhorn/oci-bv | 1 hafta |
| **Registry** | Docker Hub (`celikada/kfinans-*`) | ORTA | Kaniko `--destination` multi-mirror (DH + GHCR + Quay) | 1 gün |
| **Object Storage** | YOK (planlanan) | DÜŞÜK | S3-compatible adapter (Oracle/AWS/B2/R2 hepsi aynı API) | 2-3 gün |
| **CI/CD** | GitLab iosrv (LAN) | ORTA (single nokta arıza) | Yedek runner Oracle VM veya GitHub Actions mirror | 2-3 gün |
| **DB** | PostgreSQL spesifik (`pg_try_advisory_lock`, JSONB) | DÜŞÜK | JSONB SQLAlchemy `sa.JSON` driver-transparent; advisory lock için `services/db_lock.py` abstraction | 1 gün |
| **Domain** | `kfinans.app` hard-coded 7+ dosyada | YÜKSEK (white-label engeli) | `lib/branding.ts` + env-driven config | 2-3 gün |
| **Node IP** | `141.144.243.54` 8 yerde | YÜKSEK (multi-node migration blocker) | NetworkPolicy: namespace label selector; CI: ENV variable | 1 gün |

## 2. Hard-coded Değerler Listesi

### 2.1 Oracle VM IP (`141.144.243.54`)

| Dosya | Satır | Bağlam |
|-------|-------|--------|
| `k8s/networkpolicies/02-backend-ingress.yaml` | ipBlock | Probe traffic source |
| `k8s/networkpolicies/04-frontend-ingress.yaml` | ipBlock | Probe traffic source |
| `.gitlab-ci.yml` | satır 26 `ORACLE_VM_HOST: "141.144.243.54"` | Deploy job — CI variable (default hard-code) |
| `.github/workflows/release.yml` | SİLİNDİ | Dosya artık yok (workflows: ci-backend, ci-frontend, e2e, security, sonar) |
| ~8 doc dosyası | — | Referans (operations-playbook, infrastructure-runbook, production-deploy-checklist, 01-tasarim, audit'ler) |

**Önerilen fix:** `ORACLE_VM_HOST` zaten GitLab CI variable; default hard-code'u CI/CD project variable'a taşı. NetworkPolicy node IP yerine namespace label selector (multi-node K8s'de auto-discovery).

### 2.2 Domain (`kfinans.app`)

| Dosya | Satır | Bağlam |
|-------|-------|--------|
| `frontend/next.config.ts` | CSP connect-src | Production domain |
| `frontend/proxy.ts` | — | Domain hard-code YOK (env/relative path; kontrol edildi 2026-06) |
| `frontend/app/legal/cookies/page.tsx` | mailto + body | iletisim@ + privacy@ |
| `frontend/app/legal/kvkk/page.tsx` | mailto + body | Aynı |
| `frontend/playwright/*.spec.ts` | BASE_URL | E2E test |
| `k8s/configmap.yaml` | ALLOWED_HOSTS + CORS_ORIGINS + FRONTEND_URL | Backend env |
| `k8s/ingress.yaml` | host: kfinans.app | TLS + routing |

**Önerilen fix:** `lib/branding.ts` central config (frontend) + ConfigMap env var (backend) + Helm `values.yaml` (k8s).

### 2.3 GitLab Runner IP (`gitlab.192.168.3.191.nip.io`)

LAN-spesifik. Lokal dev'den remote'a taşımak için runner Oracle VM'e migrate veya GitLab.com hosted alternative.

### 2.4 Registry (`docker.io/celikada`)

Tek registry; rate limit + supply chain risk. Multi-mirror Kaniko `--destination` ile (Docker Hub + GHCR + Quay).

## 3. Migration Roadmap

### Phase 1 (Q3 2026) — Multi-cloud foundation
- `k8s/base/` + `k8s/overlays/{oracle-k3s, aws-eks, gcp-gke, onprem-rke2}/` split
- Image multi-mirror (Kaniko `--destination` triplet)
- Hard-coded IP/domain → env-driven config

### Phase 2 (Q4 2026) — Storage abstraction
- Off-site backup S3-compatible adapter (Oracle Object Storage default)
- WAL-G PITR

### Phase 3 (Q1 2027) — GitOps + multi-cluster
- ArgoCD self-hosted
- Yedek runner Oracle VM
- Multi-registry image mirror

### Phase 4 (Q2 2027+) — Cloud-managed services opt-in
- Managed Postgres (RDS / Cloud SQL)
- External Secrets Operator + Vault
- CloudNativePG HA streaming replica

## 4. White-label / Multi-tenant SaaS Geçişi

`audit-2026-05-22/compliance-notes.md`'nin önerisi: `frontend/app/legal/_data/legal-config.ts` central config refactor (~2 saat) ile white-label hazır.

- `users.tenant_id` kolonu (multi-tenant data isolation)
- `audit_logs.tenant_id` (multi-tenant audit ayrımı)
- `lib/branding.ts` (frontend logo/color/domain)
- `SealedSecret` name/namespace pattern tenant-aware

Effort: 1-2 sprint (yapısal yapı + KVKK metinleri template).

## 5. Build-time vs Runtime Config

**Sorun:** `NEXT_PUBLIC_API_URL` build-time bake — staging + prod aynı image kullanamaz.

**Önerilen:** `/__env.json` endpoint veya `process.env` runtime-bridge. Next.js 16'da `headers()` ile request-time inject mümkün.

## 6. Test Edilen Geçiş Senaryoları

| Senaryo | Durum |
|---------|-------|
| Oracle K3s → vanilla K8s | TEST EDİLMEDİ |
| Docker Hub → GHCR fallback | TEST EDİLMEDİ |
| Anthropic → OpenAI fallback | TEST EDİLMEDİ (adapter pattern yok) |
| `kfinans.app` → başka domain | TEST EDİLMEDİ |

**Sprint 3 hedefi:** Her satır için bir migration drill.

## 7. Referans

- [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) §3
- [`../audit-2026-05-22/devops-notes.md`](../audit-2026-05-22/devops-notes.md) §Portability Roadmap
- [`../audit-2026-05-22/backend-notes.md`](../audit-2026-05-22/backend-notes.md) §Portability
