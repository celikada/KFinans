# KFinans Operations Playbook

> **Amaç:** Günlük operasyon, on-call, alerting ve troubleshooting referansı.
> **İlgili:** [`infrastructure-runbook.md`](infrastructure-runbook.md) (kurulum), [`disaster-recovery.md`](disaster-recovery.md) (DR), [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) (bekleyen iyileştirmeler)

**Durum:** Aktif — Hetzner Cloud k3s'e (CX23, `91.99.123.163`) taşındı (2026-06-23). Alerting (§3) hâlâ TODO.
**Son güncelleme:** 2026-06-23 (Oracle → Hetzner taşıma)

> **Erişim modeli (Hetzner):** Cluster lokal kubectl ile yönetilir — `export KUBECONFIG=~/.kube/hetzner-kfinans.yaml` sonrası `kubectl ...`. Bu playbook'taki komutlar bu KUBECONFIG ile çalışır. Sunucuya doğrudan kabuk gerekirse `ssh root@91.99.123.163`.

## 1. Üretim Mimarisi Hızlı Bakış

- **Domain:** `kfinans.app` (Namecheap, `.app` TLD HSTS preload)
- **Cluster:** Hetzner Cloud CX23 k3s v1.35 `91.99.123.163` (single-node, Falkenstein fsn1/DE)
- **CI/CD:** GitLab self-hosted `gitlab.192.168.3.191.nip.io` — 7 stage (lint→test→quality→build→scan→deploy→smoke). Kaniko build → Docker Hub `celikada/kfinans-{backend,frontend}`. Trivy image gate (HIGH/CRITICAL) + curl smoke gate (semver tag). **TODO: deploy job hâlâ Oracle K3s'i hedefliyor → Hetzner'e retarget edilecek.** Hetzner'de deploy şimdilik lokal kubectl ile manuel: `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/hetzner | kubectl apply -f -`.
- **Quality gate:** self-hosted SonarQube `sonar.192.168.3.191.nip.io` (BLOCKING — `qualitygate.wait=true`)
- **GitHub:** salt-mirror (develop/main/tags); Actions flag #4360519 nedeniyle 0 run
- **Monitoring:** Sentry + OTel opt-in (DSN/endpoint env)

## 2. Günlük Kontroller (5 dakika)

```bash
# Health
curl -sk -w "HEALTH: %{http_code}\n" https://kfinans.app/health

# Pod durumu (KUBECONFIG=~/.kube/hetzner-kfinans.yaml)
kubectl -n kfinans get pods

# Son backup durumu (⚠ Hetzner'de backup-cronjob henüz uygulanmadı — hardening TODO)
kubectl -n kfinans get job -l app=postgres-backup --sort-by=.metadata.creationTimestamp | tail -3
```

**Beklenen:** HEALTH 200, tüm pod'lar Running. (Backup CronJob Hetzner'de henüz yok — kurulunca son backup `Complete` beklenir.)

## 3. Alerting (TODO — Sprint 2)

Şu an alerting yok. Planlanan:
- Sentry exception spike → Slack
- Postgres backup fail → e-mail
- SSL cert expiry < 30 gün → Slack
- Disk usage > %80 → Slack

## 4. Yaygın Troubleshooting

### 4.1 Backend pod CrashLoopBackOff

```bash
kubectl -n kfinans logs deployment/backend --previous --tail=50
```

Olası nedenler:
- Alembic migration fail → migration zincirini kontrol
- DB connection refused → postgres pod durumu
- Fernet key yanlış → Secret değeri kontrolü (Hetzner'de düz k8s Secret; sealed-secrets henüz yok)

### 4.2 Yavaş response (>500ms)

```bash
curl -sH "X-Metrics-Token: $METRICS_TOKEN" https://kfinans.app/api/v1/metrics/performance
```

P99 > 1s ise: external API timeout, DB query slow, pool tükendi.

### 4.3 Login 401 (kullanıcı geri bildirimi)

1. `/auth/resend-verification` denenmiş mi? (login sayfasındaki amber banner)
2. Hesap kilitli mi? (SEC-002: 10 başarısız → 15 dk lockout, 423 status)
3. MFA aktif mi? (mfa_required: true → totp doğrulama gerek)

### 4.4 Deploy sonrası özellik bozuk — secret değeri yanlış (RESEND vb.)

> Belirti: deploy yeşil ama bir entegrasyon çalışmıyor (örn. email gitmiyor — `403 verified addresses` / Resend log boş). Tipik kök neden: canlı secret değeri hatalı **ve** `deploy-production` job'u `set image` yapar, **secret apply etmez** → eski/yanlış değer canlıda kalır.

**İki aşamalı düzeltme (RESEND_API_KEY örneği — yeniden kullanılabilir):**

```bash
# (KUBECONFIG=~/.kube/hetzner-kfinans.yaml)
# A) Canlı patch — SADECE ilgili key (kubectl create|apply tüm secret'ı ezer!)
kubectl patch secret kfinans-secrets -n kfinans --type=merge \
  -p '{"stringData":{"RESEND_API_KEY":"re_DOGRU_KEY"}}'
kubectl rollout restart deploy/backend -n kfinans

# B) Kalıcılık — canlı patch'i k8s/overlays/hetzner Secret manifest'ine de yansıt
#    (aksi halde sonraki apply -k eski değeri geri getirir).
#    Sealed-secrets Hetzner'de henüz kurulmadı (hardening TODO); kurulunca
#    kubeseal --raw --scope strict ile mühürle, sealed-secrets.yaml'a yaz, MR aç.
```

Tam prosedür + neden açıklaması: [`infrastructure-runbook.md`](infrastructure-runbook.md) §2.4.

**Genel kural:** `deploy-production` yalnızca image değiştirir. ConfigMap/Secret/NetworkPolicy/Ingress değişiklikleri **ayrıca** `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/hetzner | kubectl apply -f -` (veya hedefli patch) ile uygulanmalı; Secret manifest'i repo ile senkron tutulmalı.

## 5. Periyodik Bakım

| Periyod | Görev | Yöntem |
|---------|-------|--------|
| Günlük 02:00 | Postgres backup (age encrypted) | CronJob otomatik (⚠ Hetzner'de henüz uygulanmadı — hardening TODO) |
| Günlük 03:00 | revoked_tokens cleanup | Scheduler `_cleanup_revoked_tokens_job` |
| Günlük 04:00 | Hard-delete (30g geçmiş soft-delete'ler) | Scheduler |
| Günlük 04:30 | audit_logs 365g purge | Scheduler |
| Pazar 23:00 | Haftalık portföy snapshot | Scheduler `_weekly_snapshot_job` |
| Aylık | Secret değer/rotation kontrol (Hetzner düz Secret; sealed-secrets kurulunca master key) | Manuel |
| Çeyrek | DR drill (restore test) | Manuel — bkz disaster-recovery.md |

## 6. Acil Durum Kontağı

- **Sürdürücü:** `celikada@gmail.com` (Mayotek)
- **Yedek:** TODO (single-IC risk — compliance audit P3)

## 7. Bekleyen İyileştirmeler

Bu playbook'un eksikleri [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) §1.3 Bakım bölümünde detaylı:
- Sentry DSN production aktivasyonu
- Operations alerting kanalları
- Single-IC yedek
- Quarterly DR drill protokolü
