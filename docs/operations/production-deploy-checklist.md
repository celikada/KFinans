# Production Deploy Checklist (v0.1.0 → v1.0.0 GA)

> **Durum (2026-06-23):** Production Hetzner Cloud k3s'e (CX23, `91.99.123.163`, Falkenstein/DE) taşındı. Bu checklist'in teknik/altyapı satırları (§2-§9) Oracle'da tamamlanmıştı; Hetzner ilk-deploy'da bir kısmı sadeleştirildi (bkz. §6 hardening TODO). Kalan ✗ satırları **v1.0.0 GA** için zorunlu **kullanıcı aksiyonları** (§1 KVKK) — kod ile çözülemez.

## 1. Yasal / KVKK (kullanıcı aksiyonu)

| | Item | Durum |
|---|------|-------|
| [ ] | **#11 COMP-001** — KVKK Aydınlatma Metni'nde `[TİCARİ ÜNVAN]` placeholder | Mayotek tüzel kimlik (vergi no, MERSIS, KEP, tebligat adresi, mahkeme) doldurulacak |
| [ ] | **#12 COMP-002** — `kvkk@kfinans.app` + `privacy@kfinans.app` mailbox | Namecheap Private Email veya Google Workspace ($6/ay) |
| [ ] | **#13 COMP-005** — Anthropic + Resend + Hetzner Cloud DPA imzaları | 3 sağlayıcıdan DPA isteyip Mayotek adına imza (KVKK m.9 zayıf zemin; Hetzner Almanya/AB — yurt dışı aktarım DPA'sı Hetzner'den alınır) |

**Why:** KVKK Aydınlatma Metni'nde placeholder yayında bırakmak idari para cezası riskidir. Mailbox olmadan kullanıcı veri erişim talebi yanıtsız kalır (KVKK m.13 30 gün şartı). DPA olmadan veri sorumlusu zinciri eksik.

## 2. SonarQube Quality Gate (self-hosted — kod kalitesi gate)

> **Not (2026-06-01):** GitHub flag #4360519 nedeniyle SonarCloud OAuth bloklu → **self-hosted SonarQube**'a geçildi (`http://sonar.192.168.3.191.nip.io`, `projectKey=KFinans`). Gate GitLab CI `quality` stage'inde BLOCKING.

| | Item | Durum |
|---|------|-------|
| [x] | Self-hosted SonarQube ayakta + `KFinans` projesi | ✅ `sonar.192.168.3.191.nip.io` |
| [x] | GitLab `SONAR_TOKEN` Protected variable eklendi | ✅ CI/CD → Variables (protected) |
| [x] | `sonarqube-scan` job `qualitygate.wait=true` + `allow_failure` kaldırıldı | ✅ 2026-06-01 (BLOCKING) |
| [x] | Coverage fix: `concurrency=["greenlet","thread"]` (async handler ölçümü) | ✅ new_coverage %48→%96 |
| [x] | Develop'a MR → GitLab pipeline `quality` stage yeşil | ✅ v0.1.0-rc16 |
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
| `ORACLE_SSH_KEY` | Oracle VM SSH private key (File variable; job `/tmp/oracle.key`'e kopyalar) — **(TODO: deploy job Hetzner'e retarget edilince güncellenecek)** | ✅ | File |
| `ORACLE_VM_HOST` / `ORACLE_VM_USER` / `ORACLE_K8S_NAMESPACE` | deploy SSH hedefi (Oracle — Hetzner retarget bekliyor) | ✅ | — |
| `GITLAB_PAT` | manuel deploy job `POST /jobs/:id/play` tetiklemek için | ✅ | — |

## 5. DNS — kfinans.app (Namecheap)

> **Tüm kayıtların güncel durumu için bkz. [`infrastructure-runbook.md`](infrastructure-runbook.md) §1.1**

| | Item | Durum |
|---|------|-------|
| [x] | A record `@` → `91.99.123.163` (Hetzner VM) | ✅ 2026-06-23 |
| [x] | CNAME record `www` → `kfinans.app.` (apex CNAME, IP değişirse otomatik takip) | ✅ 2026-05-14 |
| [ ] | A record `api` → `91.99.123.163` (opsiyonel, path-based ingress var, şu an gereksiz) | — |
| [x] | TXT `resend._domainkey` (Resend DKIM) | ✅ 2026-05-14 |
| [x] | MX `send` → `feedback-smtp.ap-northeast-1.amazonses.com` priority 10 (Resend SPF return-path) | ✅ 2026-05-14 |
| [x] | TXT `send` → `v=spf1 include:amazonses.com ~all` (Resend SPF) | ✅ 2026-05-14 |
| [x] | TXT `_dmarc` → `v=DMARC1; p=none;` (DMARC monitoring) | ✅ 2026-05-14 |
| [x] | DNS propagation kontrol: `nslookup kfinans.app 8.8.8.8` → 91.99.123.163 | ✅ 2026-06-23 |
| [ ] | MX record apex `@` → mailbox sağlayıcı (kvkk@/privacy@ inbound, yasal aksiyon ile birlikte) | ⏳ COMP-002 |

## 6. Hetzner Cloud k3s

> **Erişim:** lokal kubectl + `KUBECONFIG=~/.kube/hetzner-kfinans.yaml` (sunucuya doğrudan kabuk gerekirse `ssh root@91.99.123.163`).
>
> ⚠ **Hetzner ilk-deploy hardening TODO'ları:** DB TLS KAPALI (`DATABASE_SSL_MODE=disable`), NetworkPolicy'ler uygulanmadı, sealed-secrets yerine düz k8s Secret, backup-cronjob henüz yok, 2 GB swap eklendi, Hetzner firewall (22/80/443 public, 6443 admin-IP). Bunlar v1.0.0 GA öncesi sertleştirilecek.

| | Item | Durum |
|---|------|-------|
| [x] | Hetzner VM `91.99.123.163` çalışıyor (CX23) | `ssh root@91.99.123.163` / `kubectl get nodes` |
| [x] | k3s v1.35 kurulu, `kubectl get nodes` yeşil | lokal kubectl |
| [x] | `kfinans` namespace var | `kubectl get ns kfinans` |
| [x] | Traefik ingress kurulu (k3s default) | `kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik` |
| [x] | cert-manager + Let's Encrypt ClusterIssuer `letsencrypt-prod` | `kubectl get clusterissuer` |
| [x] | Postgres StorageClass tanımlı (`local-path`) | k3s default local-path |
| [x] | K8s Secrets oluşturuldu (DATABASE_URL, SECRET_KEY, FERNET_KEY, vs.) | `kubectl get secret kfinans-secrets -n kfinans` (düz Secret — hardening TODO: sealed-secrets) |
| [ ] | etcd encryption-at-rest aktif | hardening TODO (Hetzner) |
| [ ] | NetworkPolicy aktif | hardening TODO (Hetzner ilk-deploy'da uygulanmadı) |
| [ ] | Pod Security Standards (restricted) | hardening TODO (Hetzner) |
| [ ] | DB TLS (`DATABASE_SSL_MODE=require`) | hardening TODO (Hetzner ilk-deploy'da `disable`) |

## 7. İlk deploy senaryosu (GitLab — deploy job Oracle hedefli, Hetzner retarget TODO)

> ⚠️ **Hetzner geçiş notu:** GitLab CI `deploy-production` job'u hâlâ Oracle K3s'i hedefliyor (retarget edilecek). Hetzner'de deploy şimdilik **lokal kubectl ile manuel** yapılır:
> ```bash
> export KUBECONFIG=~/.kube/hetzner-kfinans.yaml
> # build aşaması Docker Hub'a image push ettikten sonra (örn. v0.11.4):
> kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/hetzner | kubectl apply -f -
> # veya yalnız image bump:
> kubectl -n kfinans set image deployment/backend backend=celikada/kfinans-backend:v0.11.4
> kubectl -n kfinans set image deployment/frontend frontend=celikada/kfinans-frontend:v0.11.4
> kubectl -n kfinans rollout status deployment/backend --timeout=5m
> ```
> Aşağıdaki GitLab pipeline akışı (lint→test→quality→build→scan) Hetzner'de de geçerlidir; yalnız son `deploy-production` adımı manuel kubectl ile yapılır.

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
#    - scan (trivy-image-scan): HIGH/CRITICAL --ignore-unfixed → açık varsa DURUR
#    - deploy-production: when: manual — OTOMATIK BAŞLAMAZ

# 4. Deploy job'unu manuel tetikle (GitLab UI "play" VEYA API):
curl -s --request POST --header "PRIVATE-TOKEN: $GITLAB_PAT" \
  "http://gitlab.192.168.3.191.nip.io/api/v4/projects/<PID>/jobs/<JOB_ID>/play"
#    → (deploy job şu an Oracle K3s'i hedefliyor — Hetzner retarget TODO; bkz. üstteki manuel akış)

# 5. smoke-test job otomatik çalışır (needs: deploy-production):
#    frontend HTTPS + /health {status:ok} + bogus login 401 + HSTS header
#    Fail ise pipeline kırmızı (alarm). Ek manuel doğrulama:
curl -fsS https://kfinans.app/health        # {"status":"ok"}
curl -I https://kfinans.app                  # HSTS + X-Frame + CSP
# veya: cd frontend && npm run smoke
```

> ⚠️ **deploy `set image` yapar, kustomize apply YAPMAZ** → ConfigMap/Secret değişiklikleri ayrı uygulanmalı (`kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/hetzner | kubectl apply -f -`; bkz. infrastructure-runbook §2.4). Hetzner'de düz Secret kullanıldığından canlı patch'i overlay Secret manifest'ine de yansıt (sealed-secrets kurulunca SealedSecret senkron tutulur).

## 8. Rollback senaryosu

```bash
# Smoke fail veya prod hata durumunda manuel rollback (KUBECONFIG=~/.kube/hetzner-kfinans.yaml):
kubectl rollout undo deployment/backend -n kfinans
kubectl rollout undo deployment/frontend -n kfinans

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
| 2026-06-02 | Doğruluk denetimi: son deploy v0.1.0-rc10→**rc16**. §7 pipeline'a `scan` (Trivy) + otomatik `smoke-test` stage'leri eklendi (önceki "smoke henüz yok" notu düzeltildi). Başlığa "production canlı / v1.0.0 GA için kalan = KVKK kullanıcı aksiyonları" durum notu. |
| 2026-06-23 | Oracle Cloud'dan Hetzner Cloud'a taşındı (CX23, k3s v1.35, IP 91.99.123.163). §5 DNS `@` A → 91.99.123.163. §6 başlık "Hetzner Cloud k3s" + VM/cluster satırları + hardening TODO (DB TLS disable, NetworkPolicy yok, düz Secret, backup-cronjob yok, 2 GB swap, firewall). §7 deploy job Oracle hedefli (retarget TODO) + Hetzner manuel kustomize akışı. §8 rollback lokal kubectl. §1 DPA Oracle→Hetzner (Almanya/AB). §4 ORACLE_SSH_KEY retarget notu. |
