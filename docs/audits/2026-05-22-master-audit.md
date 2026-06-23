# KFinans Master Audit Raporu — 2026-05-22

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

> **Bağlam:** 2026-05-21'de büyük güvenlik audit fix turu tamamlandı (13 commit, rc7 production'da). Bu rapor o turun sonrasında **6 kavram × 3 prensip** matrisinde tüm sistemi gözden geçiren **11 paralel uzman ajan** çalışmasının konsolidasyonudur.
>
> **Kavramlar:** Tasarım · Uygulama · Bakım · Kullanım · Yedekleme · Güvenlik
> **Prensipler:** Best Practice · Yeniden Kullanılabilirlik (Reusability) · Taşınabilirlik (Portability)
>
> **Süreç:** Her uzman ajan kendi domain'inde ✓ pozitif + ⚠ çelişki notları (P0/P1/P2/P3) üretti. Bu master doc her domain'in özetini + cross-domain çakışan notları içerir.
>
> **Önemli ilke:** Bu rapor **NOT** içerir, kod değişikliği DEĞİL. Düzeltmeler ayrı PR/epic olarak takip edilir.

---

## Yönetici Özeti

KFinans **teknik olarak production-ready** (rc7 canlı, HEALTH 200, DB TLS=on, 7 NetworkPolicy + ROFS + age backup + etcd encryption + MFA TOTP + PII mask + Fernet rotation + zxcvbn+HIBP password policy). Audit'ten önce 11/11 kritik güvenlik fix kapatıldı.

Ancak **3 sınıf engel** kaldı:

| Engel | Sayı | Önem |
|-------|------|------|
| **KVKK + legal placeholder** | 13 alan | Production launch blocker (yasal) |
| **Vendor lock-in + hard-coded değerler** | ~25 dosya | Multi-cloud/multi-tenant geçişi engelliyor |
| **Frontend reusability borcu** | 68 yerde Tailwind copy-paste, 1511 satır `lib/api.ts` | UX consistency + scale riski |

**Sayısal özet:**
- **11 ajan, 175+ NOT** (yaklaşık 12 P0 + 60 P1 + 70 P2 + 30 P3)
- **9 yeni audit dosyası** + 2 üst-rapor (`SYSTEM-DOC-AUDIT-2026-05-22.md`, `MIMARI-AUDIT-2026-05-22.md`)
- **0 kod değişikliği** (audit çalışması — düzeltmeler ayrı epic)

---

## 1. Kavram × Domain Matrisi

### 1.1 Tasarım (Design)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **Mimari** | Modüler monolit kararı tutarlı; `BaseIntegration` + `BaseBlockchainIntegration` + `BaseExchangeIntegration` 13 servis tutarlı | `aggregator.py` 4 sorumluluk yüklü (ARC-005), `snapshot.py` 624 satır god module (ARC-002), event-driven (Celery/Redis pub-sub) yok |
| **Backend** | Pydantic v2 modern stil 4/20 schema (DEPS-001 %20), async-first | Schema'ların geri kalan %80'i v1 stil (BACK-002), Anthropic + Resend SDK doğrudan import (adapter pattern yok) |
| **Frontend** | Next.js 16 native pattern (`proxy.ts`), `output: "standalone"` | Tailwind class duplikasyonu 68 yerde, dashboard `page.tsx` 727 satır (config-driven refactor öneriliyor), legal sayfaları gereksiz `"use client"` |
| **Veritabanı** | 40 migration lineer (multi-branch DEĞİL — doğrulandı), FK CASCADE/SET NULL tutarlı (DBA-001), PERF-003 user_id indexes | `pg_try_advisory_lock` tek gerçek PostgreSQL lock-in noktası — `services/db_lock.py` abstraction önerisi |

### 1.2 Uygulama (Implementation)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **Backend** | ruff 0 hata + format gate hard, 642 test (192 unit + 357 integration + 93 ek), error chain 3-katmanlı (`{detail, code, request_id}`) | Cache + single-flight 5 servisde duplike (~200 satır → `core/cache.py` extract), 15 dosyada hard-coded public API URL'leri |
| **Frontend** | ConfirmDialog accessible alertdialog (FE-013), refresh token single-flight rotation | `handle401` 5 sayfada 21 çağrı (substring check fragile), `lib/api.ts` 1511 satır 50+ endpoint + 30+ DTO + format helper tek dosyada |
| **AI** | Anthropic 7 exception tipi ayrı yakalanıyor, `_CLAUDE_TIMEOUT=60s`, SPK m.40 disclaimer post-processing | Prompt injection sanitization yok (`user.risk_profile` DB string), output validation yok, multi-jurisdiction disclaimer yok (sadece TR) |
| **Finans** | TL normalize 3-katmanlı (GBp→GBP→USD→TL), multi-currency cash (FIN-007), Decimal precision `Numeric(28,10)` SHIB/PEPE için yeterli | **Decimal rounding mode global ayarsız** — Python default `HALF_EVEN` (banker's), muhasebede `HALF_UP` standart — P0 |

### 1.3 Bakım (Maintenance)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **Observability** | Sentry + OTel opt-in (OBS-001), `X-Response-Time` header + slow request log (PERF-004), audit log Enum-driven | Sentry DSN production'da set edilmemiş (kontrol gerekli), AI cache hit oranı izlenmiyor (DB'de var, dashboard yok) |
| **Runbook** | `docs/infrastructure-runbook.md` kapsamlı kurulum + bakım, `incident-response-plan.md` ISO 27035 + KVKK m.12/5 | Operations playbook (on-call + alerting + troubleshooting) ayrı doc YOK, DR drill prosedürü ayrı doc YOK |
| **Dependency rotation** | pyproject.toml pinning (2026-05-21), Dependabot haftalık | `xlrd 1.2.0` Python 3.13+ riski, `python-jose >= 3.3.0` (3.4.0+ daha güvenli) |

### 1.4 Kullanım (Usability)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **API** | OpenAPI/Swagger UI mevcut, 21 router net | Swagger UI prod'da CSP `default-src 'none'` ile çakışıyor; `/openapi.json` saldırgan enumeration vektörü (P0) |
| **Frontend i18n** | TR/EN foundation (i18n-001), 32 mfa.* anahtar, login + dashboard layout çevrili | i18n-002: 600+ string TR-only kalan, 17 dashboard sayfa hâlâ çevrilmemiş |
| **A11y** | WCAG 2.1 AA %60-70 uyum tahmini (A11Y-001: skip-link, focus trap, aria-label icons) | `aria-live` "Yükleniyor..." duyurulmuyor, gray-400 placeholder kontrast 3.2:1 (4.5:1 altı), axe-core entegrasyonu yok |
| **UX bug** | `/auth/resend-verification` endpoint + register sayfası akışı sağlam | Login sayfasında "yeniden gönder" butonu YOKTU — **bu raporun yazımı sırasında düzeltildi** (commit `23eb761`) |

### 1.5 Yedekleme (Backup)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **Backup encrypt** | age asymmetric encryption + 30 gün retention, master key offline (`.credentials.local.md` §8) | **3-2-1 yedek kuralı ihlal — off-site sync YOK** (P0). Oracle Object Storage (Always Free 20 GB) rclone sidecar planı backlog'ta |
| **DR** | restore prosedürü dokümante (`backup-cronjob.yaml:13-17`) | **DR drill production'da hiç test edilmedi** (P0). Quarterly staging drill protokol gerekli |
| **PITR** | Logical backup günlük (RPO 24 saat) | **PITR yok** — manuel entry kayıpları 24 saate kadar kaybolur. WAL-G + S3 önerisi (RPO 5-15 dk) |
| **Master key** | offline backup prosedür var, 3-2-1 talimat | Master key recovery drill yapılmadı — kayıp senaryosu test edilmemiş |

### 1.6 Güvenlik (Security)

| Domain | ✓ Pozitif | ⚠ Risk |
|--------|-----------|--------|
| **Auth** | JWT HS256 + jti + refresh rotation + revoked_tokens cleanup, MFA TOTP RFC 6238, MultiFernet key rotation | Access token default 480 dk (prod 30 dk override) — default 30 dk olmalı, `localStorage` access token + CSRF yok |
| **Crypto** | Fernet MultiFernet (key rotation hazır), bcrypt cost 12, `secrets.token_urlsafe(32)` | DB TLS `ssl_mode="prefer"` cert verify OFF (P0 — `require` + CA bundle gerek) |
| **Network** | 7 NetworkPolicy default-deny + allowlist, HSTS + CSP `default-src 'none'` + COOP/CORP, Traefik + cert-manager | `allowed_hosts=["*"]` default permissive (fail-closed validator gerek), SealedSecret name/namespace hard-coded |
| **K8s** | PSS baseline + ROFS=true + SealedSecrets + age backup, etcd at-rest encryption AES-CBC | Single replica StatefulSet startupProbe yok (~30sn restart downtime), age binary her run GitHub'dan indir (supply-chain risk) |

---

## 2. Yeniden Kullanılabilirlik (Reusability) — Cross-Domain

**Pozitif (oluşmuş abstraction'lar):**
- `BaseIntegration` + `BaseBlockchainIntegration` + `BaseExchangeIntegration` 13 servis tutarlı
- `AssetData` dataclass uniform return
- `masking.py` saf modül (mask_email, hash_email, mask_address)
- conftest fixture pattern (autouse + marker-based bypass)

**Eksik abstraction'lar (notlar):**
1. **Cache + single-flight pattern duplikasyonu** — 5 blockchain servisinde (`bitcoin`, `solana`, `polkadot`, `litecoin`, `avalanche`) `_BALANCE_CACHE` + `_INFLIGHT` + `_cache_lock` global'leri birebir kopyalanmış (~200 satır → `core/cache.py::AsyncTTLCache`)
2. **EVMService + BinanceCompatibleService base** — Ethereum/Avalanche multi-RPC fallback ve Binance/BinanceTR HMAC pagination kodu %80 ortak
3. **`aggregator.py` 4 sorumluluk** — `services/pricing/{tcmb,binance,coingecko,fx}.py` split
4. **`security.py` god module** — 100 satır 6 sorumluluk → `app/core/security/` paketi
5. **`audit.py` tenant_id eksik** — multi-tenant SaaS hazır değil
6. **Frontend `Card` + `PageShell` + `EmptyState` primitive'leri yok** — Tailwind 68 yerde copy-paste
7. **`lib/api.ts` 1511 satır** — modüler split `lib/api/{auth,portfolio,mfa,...}.ts`
8. **`handle401` boilerplate** — 21 çağrı, `lib/api.ts::request()` zaten redirect ediyor, fragile substring check
9. **GitLab CI template extraction** — `mayotek/gitlab-ci-templates` shared project (Python-FastAPI, NextJS, Kaniko-build template'leri); KFinans `.gitlab-ci.yml` 257 → 40 satır
10. **Test fixture merkezi yok** — respx mock'ları her dosya URL constant referanslıyor; `tests/_mocks/external.py` factory önerisi

---

## 3. Taşınabilirlik (Portability) — Cross-Domain

### 3.1 Hard-coded değerler (vendor lock-in heat map)

| Değer | Yer | Yoğunluk | Etki |
|-------|-----|----------|------|
| `141.144.243.54` (Oracle IP) | `k8s/networkpolicies/02-backend-ingress.yaml`, `.gitlab-ci.yml`, 6+ | 8 dosya | Multi-node K8s/cloud migration blocker |
| `kfinans.app` (domain) | `next.config.ts`, `proxy.ts`, 2 legal + 3 test + ingress | 7+ dosya | Multi-tenant SaaS / white-label engeli |
| `gitlab.192.168.3.191.nip.io` | `.gitlab-ci.yml`, README, credentials | LAN-spesifik | Runner taşınabilirliği yok |
| Oracle K3s spesifik | `svclb-traefik` ServiceLB, `local-path` PVC | manifest'ler | Vanilla K8s veya cloud-managed K8s'e geçiş gerektirir uyarlamalar |
| `docker.io/celikada/kfinans-*` | `kustomization.yaml`, deploy scripts | tek registry | Mirror/fallback yok, Docker Hub rate limit riski |

### 3.2 Vendor lock-in matrisi

| Servis | Şu an | Risk seviyesi | Alternatif/abstraction önerisi |
|--------|-------|---------------|--------------------------------|
| **LLM (Anthropic)** | Tek provider, SDK direkt import | YÜKSEK (SPOF) | `BaseLLMProvider` Protocol + OpenAI/Gemini fallback chain |
| **E-mail (Resend)** | Tokyo region, SDK direkt import | ORTA | `BaseEmailProvider` + SendGrid/Mailgun |
| **Object Storage (yok)** | Off-site backup için planlı | DÜŞÜK (henüz yok) | S3-compatible adapter; Oracle/AWS/B2/R2 hepsi aynı API |
| **Registry (Docker Hub)** | Tek registry | ORTA | Kaniko `--destination` multi-mirror (Docker Hub + GHCR + Quay) |
| **K8s Distro (K3s)** | Oracle-spesifik (svclb, local-path) | ORTA | Kustomize `base/` + `overlays/{oracle-k3s,aws-eks,gcp-gke}/` split |
| **CI/CD (GitLab self-hosted iosrv)** | Tek nokta arıza | ORTA | Yedek runner Oracle VM veya GitHub Actions mirror |

### 3.3 Build-time vs Runtime config

- **`NEXT_PUBLIC_API_URL` build-time bake**: Aynı image staging + prod'da kullanılamaz (P1)
- **Runtime config pattern eksik**: `/__env.json` endpoint veya environment.js sırasında inject — eksik

---

## 4. P0 — Production Launch Blocker (toplam 8 madde)

| # | Domain | Sorun | Etki | Öneri |
|---|--------|-------|------|-------|
| 1 | Compliance | KVKK aydınlatma 13 placeholder | KVKK m.10 ihlali | Ticari ünvan, KEP, tebligat, mahkeme doldur |
| 2 | Compliance | KEP adresi yok | 72 saat ihlal bildirimi imkansız | PTT KEP başvurusu |
| 3 | Compliance | `privacy@`/`kvkk@`/`security@kfinans.app` mailbox yok | SECURITY.md + gizlilik vaadi karşılanmıyor | Cloudflare/Zoho routing |
| 4 | Backup | Off-site backup YOK | Node failure = total data loss | rclone + Oracle Object Storage (Always Free 20 GB) |
| 5 | Backup | DR drill yapılmadı | Restore prosedürü test edilmemiş | Quarterly staging drill protokol |
| 6 | Security | ~~DB TLS `ssl_mode="prefer"` cert verify OFF~~ ✅ **2026-05-22 (a8496ca)** — `require` + CA bundle aktif, NetworkPolicy DNS fix gerekli oldu | MITM koruması güçlü | — |
| 7 | Security | ~~CSP + Swagger UI çakışma + `/openapi.json` enum vektörü~~ ✅ **2026-05-22 (a3f0503)** — prod'da `EXPOSE_SWAGGER=false` ile docs_url/redoc_url/openapi_url None | Endpoint enumeration kapalı | — |
| 8 | Finance | ~~Decimal rounding mode global ayarsız (HALF_EVEN banker's)~~ ✅ **2026-05-22 (a3f0503)** — `main.py` import-time `getcontext().rounding = ROUND_HALF_UP` + regression test | Vergi raporlamaya uygun | — |

---

## 5. Reorganize Sonucu

### 5.1 Yeni klasör yapısı

```
docs/
├── README.md                           (UPDATED — yeni yapı index)
├── 01-09-*.md                          (KORUNDU — UPDATE backlog)
├── operations/                         (YENİ klasör)
│   ├── infrastructure-runbook.md       (TAŞINDI)
│   ├── production-deploy-checklist.md  (TAŞINDI)
│   ├── operations-playbook.md          (YENİ — taslak)
│   └── disaster-recovery.md            (YENİ — taslak)
├── reference/                          (YENİ klasör)
│   ├── user-guide.md                   (YENİ — taslak)
│   ├── portability-matrix.md           (YENİ — taslak)
│   └── reusability-patterns.md         (YENİ — taslak)
├── audits/                             (YENİ klasör — eski "backlog/")
│   ├── 2026-05-08-faz-g-audit.md       (TAŞINDI)
│   ├── 2026-05-08-sprint-plan.md       (TAŞINDI)
│   └── 2026-05-22-master-audit.md      (BU DOSYA)
├── audit-2026-05-22/                   (uzman ajan notları)
│   ├── compliance-notes.md
│   ├── security-notes.md
│   ├── dba-notes.md
│   ├── ai-notes.md
│   ├── backend-notes.md
│   ├── devops-notes.md
│   ├── test-notes.md
│   ├── finance-notes.md
│   └── frontend-notes.md
├── SYSTEM-DOC-AUDIT-2026-05-22.md      (doc-expert üst raporu)
├── MIMARI-AUDIT-2026-05-22.md          (architect üst raporu)
└── legal/incident-response-plan.md     (KORUNDU)
```

### 5.2 Silinenler

- `docs/github-support-followup-2026-05-12.md` — GitHub flag drama bitti, GitLab CI primary; relevant değil

### 5.3 Eski doc UPDATE backlog (ayrı PR önerisi, ~6 saat)

| Doc | Eklenecek |
|-----|-----------|
| `docs/07-guvenlik.md` | Faz I 10 audit fix (MFA, MultiFernet, zxcvbn+HIBP, PII mask, DB TLS, age, etcd, NetworkPolicy, ROFS, SealedSecrets) |
| `docs/09-altyapi-test.md` | GitLab CI primary + Kaniko build + self-hosted SonarQube |
| `docs/02-mimari.md` | Traefik + cert-manager + SealedSecrets + NetworkPolicy diyagram revizyonu |
| `docs/03-api-referansi.md` | MFA endpoint'leri (setup/enable/verify/disable) + HIBP politikası + rate limit tablosu + 423 status code |
| `docs/01-tasarim-dokumani.md` | v4.4, link rot fix, "Production rc7 canlı" başlığı |

---

## 6. Sonraki Sprint Önceliklendirme

### Sprint 1 (1 hafta) — P0 Production Launch Blocker (2026-05-22 ara durum)
1. KVKK 13 placeholder doldur + KEP başvuru başlat + mailbox kurulumu (compliance) — **kullanıcı aksiyonu bekleniyor**
2. Off-site backup PR (rclone + Oracle Object Storage) — **kalan**
3. ~~DB TLS `require` + CA bundle~~ ✅ a8496ca (NetworkPolicy DNS root-cause çözüldü + require aktif)
4. ~~Swagger UI prod auth-gated~~ ✅ a3f0503 (EXPOSE_SWAGGER=false default, docs/openapi None)
5. ~~Decimal `ROUND_HALF_UP` global~~ ✅ a3f0503 (import-time set + 4 regression test)
6. DR drill staging cluster — **kalan** (eskiden Sprint 2 #6 idi)

### Sprint 2 (1 hafta) — P1 Önemli Düzeltmeler
6. DR drill staging cluster (devops + dba)
7. CSP nonce-based yeniden deneme (frontend)
8. Access token default 30 dk (security)
9. AI cache hit oranı dashboard + alert (ai)
10. Frontend i18n-002 incremental (~600 string)

### Sprint 3 (2 hafta) — Reusability + Portability
11. `core/cache.py::AsyncTTLCache` (5 blockchain dedup, backend)
12. `lib/api.ts` split (frontend)
13. `Card`/`PageShell`/`EmptyState` primitive'leri (frontend)
14. Kustomize `base/` + `overlays/` (devops)
15. `BaseLLMProvider` Protocol (ai)

### Sprint 4+ (gelecek) — Yapısal İyileştirmeler
16. WAL-G PITR (dba)
17. ArgoCD GitOps (devops)
18. CloudNativePG HA (dba — multi-node migration sonrası)
19. `aggregator.py` split + `snapshot.py` Collector pattern (architect)
20. React Compiler opt-in + Server Action'lar (frontend)

---

## 7. Referans Dokümanlar

**Uzman ajan notları (her biri 5-15 numbered NOT içerir):**
- [`audit-2026-05-22/compliance-notes.md`](audit-2026-05-22/compliance-notes.md) — KVKK + GDPR + production blocker (10 not)
- [`audit-2026-05-22/security-notes.md`](audit-2026-05-22/security-notes.md) — OWASP ASVS L2 + 13 not
- [`audit-2026-05-22/dba-notes.md`](audit-2026-05-22/dba-notes.md) — DB + backup + DR (14 not)
- [`audit-2026-05-22/ai-notes.md`](audit-2026-05-22/ai-notes.md) — Claude API + prompt + 12 not
- [`audit-2026-05-22/backend-notes.md`](audit-2026-05-22/backend-notes.md) — Backend kod kalite + 14 not + 12 reusability
- [`audit-2026-05-22/devops-notes.md`](audit-2026-05-22/devops-notes.md) — Altyapı + 18 not + 4 fazlı portability roadmap
- [`audit-2026-05-22/test-notes.md`](audit-2026-05-22/test-notes.md) — Test stratejisi + 12 not
- [`audit-2026-05-22/finance-notes.md`](audit-2026-05-22/finance-notes.md) — Finans hesaplama + 15 not
- [`audit-2026-05-22/frontend-notes.md`](audit-2026-05-22/frontend-notes.md) — Frontend mimari + 18 not

**Üst raporlar:**
- [`SYSTEM-DOC-AUDIT-2026-05-22.md`](SYSTEM-DOC-AUDIT-2026-05-22.md) — Dokümantasyon audit (doc-expert)
- [`MIMARI-AUDIT-2026-05-22.md`](MIMARI-AUDIT-2026-05-22.md) — Mimari audit (architect)

---

**Audit yapım tarihi:** 2026-05-22
**Kapsam:** Faz I 13 commit + rc7 deploy sonrası
**Yöntem:** 11 paralel uzman ajan (Claude Sonnet/Opus 4.7)
**Çıktı:** 175+ NOT, 8 P0, 60+ P1, 0 kod değişikliği
**Sonraki revizyon:** Sprint 1 sonu (P0 kapatıldıktan sonra)
