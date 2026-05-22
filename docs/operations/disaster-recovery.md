# KFinans Disaster Recovery Plan

> **Amaç:** Veri kaybı, infrastructure failure, security incident sonrası recovery prosedürü.
> **İlgili:** [`infrastructure-runbook.md`](infrastructure-runbook.md), [`operations-playbook.md`](operations-playbook.md), [`../legal/incident-response-plan.md`](../legal/incident-response-plan.md) (KVKK m.12/5 bildirim)

**Durum:** Taslak — Sprint 2'de ilk DR drill ile 1.0 hedefli. **DR drill production'da hiç test edilmedi** (master audit §1.5 P0).

## 1. Hedefler

| Metrik | Şu an | Hedef |
|--------|-------|-------|
| **RTO** (Recovery Time Objective) | Bilinmiyor (drill yok) | <4 saat |
| **RPO** (Recovery Point Objective) | 24 saat (logical backup günlük) | <15 dakika (WAL-G PITR — Sprint 4) |
| **MTTR** (Mean Time To Restore) | Bilinmiyor | <2 saat |

## 2. Backup Inventory

| Bileşen | Yöntem | Lokasyon | Encryption | Retention |
|---------|--------|----------|------------|-----------|
| **Postgres logical** | `pg_dump | gzip | age` | PVC `postgres-backups` (Oracle K3s local-path) | age asymmetric (private key offline) | 30 gün |
| **K8s manifest** | Git (`k8s/`) | GitHub + GitLab | — | sınırsız |
| **SealedSecret master key** | kubectl get secret | Lokal Temp + Bitwarden + USB | TLS keypair | sınırsız (offline) |
| **Off-site backup sync** | **YOK** (master audit P0) | — | — | — |

⚠ **3-2-1 kuralı ihlal:** Tüm backup'lar tek lokasyonda (Oracle VM disk). Node failure → total data loss.

## 3. Senaryolar

### 3.1 Pod Restart (Routine — RTO ~30 sn)

K8s auto-restart. NetworkPolicy + ROFS uyumlu. Manuel müdahale yok.

### 3.2 Single Pod Persistent Failure

```bash
# Backend
ssh oracle-portfoy "sudo kubectl -n kfinans rollout restart deployment/backend"
ssh oracle-portfoy "sudo kubectl -n kfinans rollout status deployment/backend"
```

Eğer hâlâ fail: `kubectl logs --previous` ile sebep belirle, rollback'e dön (`kubectl rollout undo`).

### 3.3 DB Corruption / Pod Lost

**Adım 1: Onaylanmış backup seç**

```bash
ssh oracle-portfoy "sudo kubectl -n kfinans exec postgres-0 -- ls -la /backups/ | tail -10"
```

**Adım 2: Backup'ı lokal'e indir + decrypt**

Master key Bitwarden'dan veya `C:\Users\celik\AppData\Local\Temp\kfinans-backup-age-key.txt`'den.

```bash
ssh oracle-portfoy "sudo kubectl -n kfinans cp postgres-0:/backups/kfinans-<TIMESTAMP>.sql.gz.age /tmp/backup.age"
scp oracle-portfoy:/tmp/backup.age ./backup.age
age -d -i /path/to/age-key.txt backup.age | gunzip > restore.sql
```

**Adım 3: DB sil + yeniden yarat**

```bash
ssh oracle-portfoy "sudo kubectl -n kfinans exec postgres-0 -- dropdb -U kfinans kfinans"
ssh oracle-portfoy "sudo kubectl -n kfinans exec postgres-0 -- createdb -U kfinans kfinans"
```

**Adım 4: Restore**

```bash
ssh oracle-portfoy "sudo kubectl cp ./restore.sql kfinans/postgres-0:/tmp/restore.sql"
ssh oracle-portfoy "sudo kubectl -n kfinans exec postgres-0 -- psql -U kfinans -d kfinans -f /tmp/restore.sql"
```

**Adım 5: Verify**

```bash
ssh oracle-portfoy "sudo kubectl -n kfinans exec postgres-0 -- psql -U kfinans -d kfinans -c 'SELECT COUNT(*) FROM users; SELECT MAX(created_at) FROM portfolio_snapshots;'"
curl -sk https://kfinans.app/health
```

### 3.4 Oracle VM / Cluster Loss (DAHA YOK — off-site backup eksik)

Şu an mümkün DEĞİL. Sprint 1'de rclone + Oracle Object Storage tamamlanınca:

1. Yeni Oracle VM provision
2. K3s + Traefik + cert-manager kurulum (infrastructure-runbook §3)
3. Object Storage'dan backup indir + age decrypt + restore
4. DNS A kaydı yeni VM IP'sine güncelle
5. Verify

### 3.5 SealedSecret Master Key Loss

Recovery imkansız. `.credentials.local.md` §8 talimat:
- Bitwarden/USB'den master key restore et
- Yeni K3s cluster'a apply
- Controller restart
- Mevcut SealedSecret'lar decrypt olur

Eğer master key TAMAMEN kayboldu:
- Yeni controller kur → yeni master key üretir
- Tüm gerçek secret değerlerini Bitwarden / `.credentials.local.md`'den çek
- `kubeseal` ile yeniden seal et + commit

## 4. DR Drill Protokolü (Sprint 2 başlangıç)

**Çeyreklik tatbikat:**

1. Staging cluster (yeni Oracle VM veya minikube)
2. Production backup'tan restore (age decrypt + psql)
3. Smoke test: HEALTH 200 + login + MFA + DB query
4. RTO ölçümü
5. Tutanak (`docs/audits/dr-drill-YYYY-QQ.md`)

**İlk drill production cutover'dan ÖNCE ZORUNLU.**

## 5. Incident Response → KVKK m.12/5 / GDPR Art.33

72 saat içinde KVKK Kurul + 30 gün içinde etkilenen kullanıcılara bildirim.

Detay: [`../legal/incident-response-plan.md`](../legal/incident-response-plan.md)

## 6. Bekleyen İyileştirmeler

- **P0:** Off-site backup (rclone + Oracle Object Storage)
- **P0:** İlk DR drill
- **P1:** WAL-G PITR (RPO 24 saat → 15 dk)
- **P1:** CloudNativePG HA (multi-node)
- **P2:** Quarterly drill protokol otomasyon
