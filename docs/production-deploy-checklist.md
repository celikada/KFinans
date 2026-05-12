# Production Deploy Checklist (v0.1.0)

> Faz F çıkış kriterleri. Tüm satırlar ✓ olunca `git tag v0.1.0` ile ilk prod deploy.

## 1. Yasal / KVKK (kullanıcı aksiyonu)

| | Item | Durum |
|---|------|-------|
| [ ] | **#11 COMP-001** — KVKK Aydınlatma Metni'nde `[TİCARİ ÜNVAN]` placeholder | Mayotek tüzel kimlik (vergi no, MERSIS, KEP, tebligat adresi, mahkeme) doldurulacak |
| [ ] | **#12 COMP-002** — `kvkk@kfinans.app` + `privacy@kfinans.app` mailbox | Namecheap Private Email veya Google Workspace ($6/ay) |
| [ ] | **#13 COMP-005** — Anthropic + Resend + Oracle Cloud DPA imzaları | 3 sağlayıcıdan DPA isteyip Mayotek adına imza (KVKK m.9 zayıf zemin) |

**Why:** KVKK Aydınlatma Metni'nde placeholder yayında bırakmak idari para cezası riskidir. Mailbox olmadan kullanıcı veri erişim talebi yanıtsız kalır (KVKK m.13 30 gün şartı). DPA olmadan veri sorumlusu zinciri eksik.

## 2. SonarCloud (kod kalitesi gate)

| | Item | Durum |
|---|------|-------|
| [ ] | SonarCloud'a GitHub OAuth ile giriş | Flag kalktı, yapılabilir |
| [ ] | `celikada/KFinans` projesi oluşturuldu | https://sonarcloud.io/dashboard?id=celikada_KFinans |
| [ ] | `SONAR_TOKEN` GitHub Secrets'a eklendi | Settings → Secrets → Actions |
| [ ] | `ENABLE_SONAR=true` GitHub Variables'a eklendi | Settings → Variables → Actions |
| [ ] | `sonar.yml` `continue-on-error: true` kaldırıldı | Ben yapacağım (Faz 2) |
| [ ] | Develop'a push → Sonar workflow yeşil | İlk deneme |
| [ ] | Main branch protection status checks → `SonarCloud Code Analysis` ekli | Settings → Branches → main |

## 3. Repository Settings

| | Item | Durum |
|---|------|-------|
| [ ] | Repository public mı? | Settings → General → Visibility (Private → Public) |
| [ ] | Main branch protection açık | Settings → Branches → main (PR + lineer history + force-push kapalı) |
| [ ] | Dependabot enable | Settings → Security → Dependabot |
| [ ] | Code scanning enable (CodeQL) | Settings → Security → Code scanning (workflow zaten var) |
| [ ] | Secret scanning + Push protection | Settings → Security → Secret scanning |

## 4. GitHub Secrets (release.yml için)

| Secret | Açıklama | Durum |
|--------|----------|-------|
| `SONAR_TOKEN` | SonarCloud auth | Faz 1 |
| `GHCR_TOKEN` | ghcr.io image push (PAT with `write:packages`) | ⚠️ kontrol |
| `ORACLE_SSH_KEY` | Oracle VM SSH private key (`~/.ssh/oracle.key`) | ⚠️ kontrol |

## 5. DNS — kfinans.app (Namecheap)

| | Item | Durum |
|---|------|-------|
| [ ] | A record `@` → `141.144.243.54` (Oracle VM) | DNS panel |
| [ ] | A record `www` → `141.144.243.54` | DNS panel |
| [ ] | A record `api` → `141.144.243.54` (opsiyonel, path-based ingress var) | DNS panel |
| [ ] | MX record `@` → mailbox sağlayıcı (Faz 1 mailbox setup sonrası) | DNS panel |
| [ ] | TXT record SPF/DKIM/DMARC (Resend email gönderimi için) | DNS panel |
| [ ] | DNS propagation kontrol: `dig kfinans.app` 141.144.243.54 göstermeli | Lokal CLI |

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

## 7. İlk deploy senaryosu

```bash
# 1. Develop'taki her şey hazır + main'e merge
git checkout main
git merge develop --ff-only  # lineer history

# 2. İlk semver tag
git tag -a v0.1.0 -m "First production release"
git push origin main --tags

# 3. release.yml otomatik tetiklenir:
#    - Sonar Quality Gate (geçmeli)
#    - Docker build (backend + frontend) → GHCR
#    - Trivy image scan (HIGH/CRITICAL fail durdurur)
#    - Oracle SSH deploy (kubectl apply + rollout)
#    - Playwright @smoke (production URL)
#    - GitHub Release notes

# 4. Smoke verify (manuel):
curl -fsS https://kfinans.app/health
curl -I https://kfinans.app   # HSTS + X-Frame + CSP
```

## 8. Rollback senaryosu

```bash
# Smoke fail veya prod hata durumunda:
# release.yml zaten otomatik rollout undo yapar (DEVOPS-005 #53 ile)
# Manuel rollback gerekirse:
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl rollout undo deployment/backend -n kfinans"
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl rollout undo deployment/frontend -n kfinans"

# Veya release silip eski tag'e geri dön:
gh release delete v0.1.0
git tag -d v0.1.0
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
