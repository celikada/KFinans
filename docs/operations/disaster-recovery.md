# KFinans Disaster Recovery Plan

> **Amaç:** Veri kaybı, infrastructure failure, security incident sonrası recovery prosedürü.
> **İlgili:** [`infrastructure-runbook.md`](infrastructure-runbook.md), [`operations-playbook.md`](operations-playbook.md), [`../legal/incident-response-plan.md`](../legal/incident-response-plan.md) (KVKK m.12/5 bildirim)

**Durum:** Taslak — Sprint 2'de ilk DR drill ile 1.0 hedefli. **DR drill production'da hiç test edilmedi** (master audit §1.5 P0).

> **Barındırma (2026-06-23):** Production artık Hetzner Cloud CX23 k3s v1.35 (`91.99.123.163`, Falkenstein/DE). Cluster lokal kubectl ile yönetilir — `export KUBECONFIG=~/.kube/hetzner-kfinans.yaml` sonrası `kubectl ...`; sunucuya doğrudan kabuk gerekirse `ssh root@91.99.123.163`. Aşağıdaki komutlar bu erişim modeline göre yazılmıştır.
>
> ⚠ **Hetzner ilk-deploy hardening TODO'ları (DR'ı doğrudan etkiler):** backup-cronjob henüz uygulanmadı (otomatik günlük backup YOK), off-site sync yok, sealed-secrets yerine düz k8s Secret, NetworkPolicy uygulanmadı, DB TLS kapalı. Bu eksikler giderilene kadar veri kaybı riski yüksek.

## 1. Hedefler

| Metrik | Şu an | Hedef |
|--------|-------|-------|
| **RTO** (Recovery Time Objective) | Bilinmiyor (drill yok) | <4 saat |
| **RPO** (Recovery Point Objective) | 24 saat (logical backup günlük) | <15 dakika (WAL-G PITR — Sprint 4) |
| **MTTR** (Mean Time To Restore) | Bilinmiyor | <2 saat |

## 2. Backup Inventory

| Bileşen | Yöntem | Lokasyon | Encryption | Retention |
|---------|--------|----------|------------|-----------|
| **Postgres logical** | `pg_dump \| gzip \| age` | PVC `postgres-backups` (Hetzner k3s local-path) | age asymmetric (private key offline) | 30 gün (⚠ Hetzner'de backup-cronjob henüz uygulanmadı) |
| **K8s manifest** | Git (`k8s/` + `k8s/overlays/hetzner/`) | GitLab (primary) + GitHub (mirror) | — (Hetzner'de düz Secret; sealed-secrets henüz yok) | sınırsız |
| **Secret değerleri** | `.credentials.local.md` + Bitwarden + USB | offline | — | sınırsız (offline) |
| **Off-site backup sync** | **YOK** (master audit P0) | — | — | — |

⚠ **3-2-1 kuralı ihlal:** Tüm backup'lar tek lokasyonda (Hetzner VM disk) + Hetzner'de henüz otomatik backup yok. Node failure → total data loss.

## 3. Senaryolar

### 3.1 Pod Restart (Routine — RTO ~30 sn)

K8s auto-restart. NetworkPolicy + ROFS uyumlu. Manuel müdahale yok.

### 3.2 Single Pod Persistent Failure

```bash
# Backend (KUBECONFIG=~/.kube/hetzner-kfinans.yaml)
kubectl -n kfinans rollout restart deployment/backend
kubectl -n kfinans rollout status deployment/backend
```

Eğer hâlâ fail: `kubectl logs --previous` ile sebep belirle, rollback'e dön (`kubectl rollout undo`).

### 3.3 DB Corruption / Pod Lost

**Adım 1: Onaylanmış backup seç**

```bash
# (KUBECONFIG=~/.kube/hetzner-kfinans.yaml)
kubectl -n kfinans exec postgres-0 -- ls -la /backups/ | tail -10
```

**Adım 2: Backup'ı lokal'e indir + decrypt**

Master key Bitwarden'dan veya `C:\Users\celik\AppData\Local\Temp\kfinans-backup-age-key.txt`'den.

```bash
kubectl -n kfinans cp postgres-0:/backups/kfinans-<TIMESTAMP>.sql.gz.age ./backup.age
age -d -i /path/to/age-key.txt backup.age | gunzip > restore.sql
```

**Adım 3: DB sil + yeniden yarat**

```bash
kubectl -n kfinans exec postgres-0 -- dropdb -U kfinans kfinans
kubectl -n kfinans exec postgres-0 -- createdb -U kfinans kfinans
```

**Adım 4: Restore**

```bash
kubectl cp ./restore.sql kfinans/postgres-0:/tmp/restore.sql
kubectl -n kfinans exec postgres-0 -- psql -U kfinans -d kfinans -f /tmp/restore.sql
```

**Adım 5: Verify**

```bash
kubectl -n kfinans exec postgres-0 -- psql -U kfinans -d kfinans -c 'SELECT COUNT(*) FROM users; SELECT MAX(created_at) FROM portfolio_snapshots;'
curl -sk https://kfinans.app/health
```

### 3.4 Hetzner VM / Cluster Loss (off-site backup eksik → veri kurtarma sınırlı)

Off-site sync + otomatik backup henüz yok (hardening TODO). Bunlar tamamlanınca tam DR mümkün olacak. Genel akış (Hetzner):

1. Yeni Hetzner Cloud CX23 VM provision (Falkenstein fsn1) + 2 GB swap + firewall (22/80/443 public, 6443 admin-IP)
2. k3s v1.35 + Traefik + cert-manager (ClusterIssuer `letsencrypt-prod`) kurulum (infrastructure-runbook §3)
3. **Cluster state'i Git'ten apply et:** `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/hetzner | kubectl apply -f -` — namespace, configmap, Secret, postgres, ingress vb. hepsi repodadır. (Not: GitLab `deploy-production` job'u hâlâ Oracle'ı hedefliyor [retarget TODO] ve sadece `set image` yapar — full cluster'ı **manuel kustomize apply** ile kur.)
4. Secret değerlerini `.credentials.local.md` / Bitwarden'dan al → `k8s/overlays/hetzner` Secret manifest'ine yaz (sealed-secrets Hetzner'de henüz kurulmadı; kurulduğunda controller master key'i Bitwarden/USB'den restore edilir → §3.5)
5. Backup indir + age decrypt + restore (§3.3 adımları) — off-site sync kurulunca uzak lokasyondan
6. Doğru image tag'ini canlıya al: `kubectl set image ...=:vX.Y.Z` (Docker Hub `celikada/kfinans-{backend,frontend}`)
7. DNS A kaydı yeni VM IP'sine güncelle (infrastructure-runbook §1.4)
8. Verify (HEALTH 200 + login + DB count)

### 3.5 Secret / SealedSecret Master Key Loss

> **Hetzner durumu:** Secret'lar şu an düz k8s Secret olarak tutuluyor (sealed-secrets henüz kurulmadı). Secret değerleri kaybolursa `.credentials.local.md` / Bitwarden'dan geri yazılır. Aşağıdaki sealed-secrets akışı, controller Hetzner'de devreye alındığında geçerli olur.

Sealed-secrets kurulu olduğunda master key kaybı recovery'si — `.credentials.local.md` §8 talimat:
- Bitwarden/USB'den master key restore et
- Yeni k3s cluster'a apply
- Controller restart
- Mevcut SealedSecret'lar decrypt olur

Eğer master key TAMAMEN kayboldu:
- Yeni controller kur → yeni master key üretir
- Tüm gerçek secret değerlerini Bitwarden / `.credentials.local.md`'den çek
- `kubeseal` ile yeniden seal et + commit

## 4. DR Drill Protokolü (Sprint 2 başlangıç)

**Çeyreklik tatbikat:**

1. Staging cluster (yeni Hetzner VM veya minikube)
2. Production backup'tan restore (age decrypt + psql)
3. Smoke test: HEALTH 200 + login + MFA + DB query
4. RTO ölçümü
5. Tutanak (`docs/audits/dr-drill-YYYY-QQ.md`)

**İlk drill production cutover'dan ÖNCE ZORUNLU.**

## 5. Incident Response → KVKK m.12/5 / GDPR Art.33

72 saat içinde KVKK Kurul + 30 gün içinde etkilenen kullanıcılara bildirim.

Detay: [`../legal/incident-response-plan.md`](../legal/incident-response-plan.md)

## 6. Bekleyen İyileştirmeler

- **P0:** Hetzner backup-cronjob uygula (otomatik günlük backup) + off-site backup (rclone + Hetzner Storage Box / S3-uyumlu object storage)
- **P0:** İlk DR drill
- **P1:** WAL-G PITR (RPO 24 saat → 15 dk)
- **P1:** CloudNativePG HA (multi-node)
- **P2:** Quarterly drill protokol otomasyon
