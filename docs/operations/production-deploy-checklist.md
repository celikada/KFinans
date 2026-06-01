# Production Deploy Checklist (v0.1.0)

> Faz F çıkış kriterleri. Tüm satırlar ✓ olunca `git tag v0.1.0` ile ilk prod deploy.

## 1. Yasal / KVKK (kullanıcı aksiyonu)

| | Item | Durum |
|---|------|-------|
| [ ] | **#11 COMP-001** — KVKK Aydınlatma Metni'nde `[TİCARİ ÜNVAN]` placeholder | Mayotek tüzel kimlik (vergi no, MERSIS, KEP, tebligat adresi, mahkeme) doldurulacak |
| [ ] | **#12 COMP-002** — `kvkk@kfinans.app` + `privacy@kfinans.app` mailbox | Namecheap Private Email veya Google Workspace ($6/ay) |
| [ ] | **#13 COMP-005** — Anthropic + Resend + Oracle Cloud DPA imzaları | 3 sağlayıcıdan DPA isteyip Mayotek adına imza (KVKK m.9 zayıf zemin) |

**Why:** KVKK Aydınlatma Metni'nde placeholder yayında bırakmak idari para cezası riskidir. Mailbox olmadan kullanıcı veri erişim talebi yanıtsız kalır (KVKK m.13 30 gün şartı). DPA olmadan veri sorumlusu zinciri eksik.

## 2. SonarQube Quality Gate (self-hosted — kod kalitesi gate)

> **Not (2026-06-01):** GitHub flag #4360519 nedeniyle SonarCloud OAuth bloklu → **self-hosted SonarQube**'a geçildi (`http://sonar.192.168.3.191.nip.io`, `projectKey=KFinans`). Gate GitLab CI `quality` stage'inde BLOCKING.

| | Item | Durum |
|---|------|-------|
| [x] | Self-hosted SonarQube ayakta + `KFinans` projesi | ✅ `sonar.192.168.3.191.nip.io` |
| [x] | GitLab `SONAR_TOKEN` Protected variable eklendi | ✅ CI/CD → Variables (protected) |
| [x] | `sonarqube-scan` job `qualitygate.wait=true` + `allow_failure` kaldırıldı | ✅ 2026-06-01 (BLOCKING) |
| [x] | Coverage fix: `concurrency=["greenlet","thread"]` (async handler ölçümü) | ✅ new_coverage %48→%96 |
| [x] | Develop'a MR → GitLab pipeline `quality` stage yeşil | ✅ v0.1.0-rc10 |
| [x] | Gate koşulları: new_violations=0 + hotspots_reviewed=100% + new_coverage>=80% | ✅ tanımlı |

## 3. Repository Settings (GitLab primary + GitHub mirror)

> CI/CD GitLab'da; GitHub salt-mirror (develop/main/tags). GitHub Actions flag nedeniyle 0 run.

| | Item | Durum |
|---|------|-------|
| [x] | GitLab `develop`/`main` push = No one (MR-only) | ✅ |
| [x] | GitLab `release/*`+`hotfix/*` = maintainer push | ✅ |
| [x] | GitLab `remove_source_branch_after_merge` | ✅ |
| [x] | GitHub `develop`+`main` protected (force-push+delete engelli, enforce_admins=false) | ✅ mirror FF sync çalışır |
| [ ] | Orphan GitHub mirror branch periyodik temizliği | ⏳ manuel (bu oturumda 10 yetim temizlendi) |

## 4. GitLab CI/CD Variables (deploy için)

| Variable | Açıklama | Durum | Tip |
|----------|----------|-------|-----|
| `SONAR_TOKEN` | self-hosted SonarQube auth | ✅ | Protected |
| `DOCKERHUB_USER` / `DOCKERHUB_TOKEN` | Kaniko → Docker Hub push | ✅ | Masked |
| `ORACLE_SSH_KEY` | Oracle VM SSH private key (File variable; job `/tmp/oracle.key`'e kopyalar) | ✅ | File |
| `ORACLE_VM_HOST` / `ORACLE_VM_USER` / `ORACLE_K8S_NAMESPACE` | deploy SSH hedefi | ✅ | — |
| `GITLAB_PAT` | manuel deploy job `POST /jobs/:id/play` tetiklemek için | ✅ | — |

## 5. DNS — kfinans.app (Namecheap)

> **Tüm kayıtların güncel durumu için bkz. [`infrastructure-runbook.md`](infrastructure-runbook.md) §1.1**

| | Item | Durum |
|---|------|-------|
| [x] | A record `@` → `141.144.243.54` (Oracle VM) | ✅ 2026-05-14 |
| [x] | CNAME record `www` → `kfinans.app.` (apex CNAME, IP değişirse otomatik takip) | ✅ 2026-05-14 |
| [ ] | A record `api` → `141.144.243.54` (opsiyonel, path-based ingress var, şu an gereksiz) | — |
| [x] | TXT `resend._domainkey` (Resend DKIM) | ✅ 2026-05-14 |
| [x] | MX `send` → `feedback-smtp.ap-northeast-1.amazonses.com` priority 10 (Resend SPF return-path) | ✅ 2026-05-14 |
| [x] | TXT `send` → `v=spf1 include:amazonses.com ~all` (Resend SPF) | ✅ 2026-05-14 |
| [x] | TXT `_dmarc` → `v=DMARC1; p=none;` (DMARC monitoring) | ✅ 2026-05-14 |
| [x] | DNS propagation kontrol: `nslookup kfinans.app 8.8.8.8` → 141.144.243.54 | ✅ 2026-05-14 |
| [ ] | MX record apex `@` → mailbox sağlayıcı (kvkk@/privacy@ inbound, yasal aksiyon ile birlikte) | ⏳ COMP-002 |

## 6. Oracle Cloud K3s

| | Item | Durum |
|---|------|-------|
| [ ] | Oracle VM `141.144.243.54` çalışıyor (Always Free Tier) | SSH login test |
| [ ] | K3s kurulu, `kubectl get nodes` yeşil | SSH'da kontrol |
| [ ] | `kfinans` namespace var | `kubectl get ns kfinans` |
| [ ] | nginx-ingress kurulu | `kubectl get pods -n ingress-nginx` |
| [ ] | cert-manager + Let's Encrypt ClusterIssuer | `kubectl get clusterissuer` |
| [ ] | Postgres StorageClass tanımlı (`local-path` veya `oci-bv`) | DEVOPS-027 #56 ile çözüldü |
| [ ] | K8s Secrets oluşturuldu (DATABASE_URL, SECRET_KEY, FERNET_KEY, vs.) | `kubectl get secret kfinans-secrets -n kfinans` |
| [ ] | etcd encryption-at-rest aktif | DEVOPS-017 #55 ile çözüldü |
| [ ] | NetworkPolicy aktif | DEVOPS-008 #54 ile çözüldü |
| [ ] | Pod Security Standards (restricted) | DEVOPS-003 #51 ile çözüldü |

## 7. İlk deploy senaryosu (GitLab — son: v0.1.0-rc10)

```bash
# 1. Develop'taki her şey hazır + main'e merge (GitLab MR ile)
#    GitLab MR: develop → main, CI yeşil + SonarQube gate yeşil olmalı

# 2. Semver tag (her iki remote'a)
git tag -a v0.1.0 -m "First production release"
git push gitlab main --tags
git push origin main --tags   # GitHub mirror

# 3. GitLab pipeline otomatik tetiklenir (tag):
#    - lint → test → quality (SonarQube BLOCKING gate, geçmeli)
#    - build (backend + frontend) → Kaniko → Docker Hub :{tag}+:latest
#    - deploy-production: when: manual — OTOMATIK BAŞLAMAZ

# 4. Deploy job'unu manuel tetikle (GitLab UI "play" VEYA API):
curl -s --request POST --header "PRIVATE-TOKEN: $GITLAB_PAT" \
  "http://gitlab.192.168.3.191.nip.io/api/v4/projects/<PID>/jobs/<JOB_ID>/play"
#    → SSH Oracle K3s: kubectl set image + rollout status --timeout=5m

# 5. Smoke verify (manuel — pipeline'da otomatik smoke job henüz yok):
curl -fsS https://kfinans.app/health        # {"status":"ok"}
curl -I https://kfinans.app                  # HSTS + X-Frame + CSP
# veya: cd frontend && npm run smoke
```

> ⚠️ **deploy `set image` yapar, `apply -k k8s/` YAPMAZ** → ConfigMap/Secret değişiklikleri ayrı uygulanmalı (bkz. infrastructure-runbook §2.4). SealedSecret güncellenmeden yapılan canlı patch GitOps reconcile'da geri alınır.

## 8. Rollback senaryosu

```bash
# Smoke fail veya prod hata durumunda manuel rollback:
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl rollout undo deployment/backend -n kfinans"
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl rollout undo deployment/frontend -n kfinans"

# Yanlış tag'i geri çek (her iki remote):
git tag -d v0.1.0
git push gitlab :refs/tags/v0.1.0
git push origin :refs/tags/v0.1.0
```

## 9. Post-deploy monitoring (ilk 24 saat)

- [ ] `https://kfinans.app` erişilebilir + HTTPS cert valid
- [ ] Login + register akışı çalışıyor (manuel test)
- [ ] Snapshot al akışı çalışıyor
- [ ] Sentry (eğer SENTRY_DSN set ise) error rate normal
- [ ] X-Response-Time header (PERF-004) makul (<500ms p95)
- [ ] HSTS preload listede `kfinans.app` (.app TLD otomatik)

## Notlar

- **FAZ G/H bitirildi:** 80+ kod-tarafı issue kapatıldı, production blocker yok.
- **3 critical kullanıcı aksiyonu** prod öncesi zorunlu — kod ile çözülemez.
- **FAZ F (production rollout):** bu checklist'in tüm satırları ✓ olunca başlar.
- Public production → kullanıcı kaydı → KVKK m.5 ispat yükü doğar.
- **Operasyonel referans:** Periyodik bakım, acil durum komutları, key rotation prosedürleri için [`infrastructure-runbook.md`](infrastructure-runbook.md).
- **Secret değerleri:** `.credentials.local.md` (gitignore'da). Production deploy v0.1.0 secret üretim tarihi: 2026-05-14.

## Değişiklik Geçmişi

| Tarih | Değişiklik |
|-------|-----------|
| 2026-05-10 | İlk versiyon (8d751c0) |
| 2026-05-14 | DNS (A `@` + CNAME `www` + Resend DKIM/SPF/MX/DMARC) eklendi → ✅. Runbook'a referans eklendi. |
| 2026-06-01 | §2 SonarCloud→self-hosted SonarQube (blocking gate + coverage fix). §3 GitLab/GitHub branch hijyeni. §4 GitHub Secrets→GitLab CI/CD Variables. §7 deploy GitLab manuel tetikleme (v0.1.0-rc10). §8 rollback iki-remote tag silme. |
