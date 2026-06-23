# Güvenlik Audit Notları — 2026-05-22

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

> **Bağlam:** 2026-05-21 büyük audit fix turu (PII mask + Fernet MultiFernet + zxcvbn + HIBP + DB TLS + age backup + etcd encryption + NetworkPolicy 7 + MFA TOTP + ROFS + SealedSecrets) tamamlandı; rc7 production'da.
> **Kapsam:** 6 kavram (tasarım/uygulama/bakım/kullanım/yedekleme/güvenlik) + 3 prensip (best practice / reusability / portability).

---

## ✓ Mevcut Pozitif (audit fix sonrası)

1. **Kriptografi katmanlı:** Fernet MultiFernet rotation (`_build_fernet`), bcrypt (parola + recovery code), JWT HS256 + jti, SHA-256 fingerprint xpub adresleri için. Şifre/anahtar/secret artık tek bir noktadan döner.
2. **Defence-in-depth header kümesi tam:** `SecurityHeadersMiddleware` HSTS (1y + preload) + CSP `default-src 'none'` + XFO DENY + COOP/CORP + Permissions-Policy + Server maskeleme; `.app` TLD HSTS preload üst kat. Frontend `next.config.ts` aynı header'ları HTML için tekrarlıyor.
3. **PII minimizasyonu uygulamada:** `mask_email`, `mask_address`, `hash_email` helper'ları + `WalletOut.address` Pydantic `field_serializer` (xpub leak yok). Audit log her satıra `user_agent[:512]` slice + `request.client.host` (X-F-F spoofing kapalı SEC-004).
4. **Şifre politikası iki katmanlı:** zxcvbn ≥3 (offline, her zaman aktif) + HIBP k-anonymity (fail-open, opt-in). NIST 800-63B + OWASP ASVS V2.1.7 hizalı.
5. **MFA TOTP olgun:** RFC 6238, ±30sn window, recovery code'lar bcrypt one-time, `pre_mfa_token` 15dk TTL ayrı `type` claim ile login akışında izolasyon, audit hook'ları 7 farklı MFA event'i kapsıyor.
6. **K8s sıkılaştırma tam:** Pod Security `restricted` (runAsNonRoot=10001, ROFS, capabilities drop ALL, seccomp RuntimeDefault), NetworkPolicy default-deny + 7 allow, SealedSecrets (etcd'de plaintext yok), age asymmetric encryption (private key cluster-dışı, 3-2-1 backup kuralı planlı).
7. **Audit log + retention compliance-uyumlu:** `audit_logs` 17 farklı action, `_purge_old_audit_logs_job` 365 gün KVKK m.7 retention; `_hard_delete_expired_users_job` 30 gün soft-delete sonrası fiziksel silme.

---

## ⚠ Çelişki / Düzeltme Notları (öncelik sırasıyla)

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | **P0** | KVKK aydınlatma metni placeholder'ları (ticari ünvan, KEP, tebligat adresi, mahkeme) hâlâ doldurulmamış (`MEMORY.md::project_kvkk_placeholders`). | Production launch blocker — KVKK m.10 ihlali, ilk şikayette tebligat yapılamaz, idari para cezası riski. | Ticari ünvan + KEP + tebligat adresi + yetkili mahkeme bilgilerini `docs/kvkk/*.md` içine yerleştir; mailbox `kvkk@kfinans.app` kur. **`compliance-expert` ajanına devret.** |
| 2 | **P0** | `database_ssl_mode` default `"prefer"` (cert verify OFF). Postgres pod cert-manager ile SSL açık ama backend MITM'e karşı yalnızca defence-in-depth — gerçek doğrulama yok. | Cluster-içi node compromise olduğunda saldırgan sahte Postgres pod ile in-flight DB trafiği yakalayabilir. | `database_ssl_mode="require"` + asyncpg `ssl_ca` mount (cert-manager CA bundle ConfigMap → backend pod `/etc/ssl/postgres-ca.crt`). Migration: dev'de `prefer`, prod'da `require`. **`dba` + `devops` koordineli.** |
| 3 | **P1** | `access_token_expire_minutes` default **480 dk (8 saat)**; prod'da env ile 30 dk override ediliyor ama default risk taşıyor (dev/staging environment'ta sızdırılan token uzun ömürlü). | OWASP ASVS V3.3.1 ≤ 15 dk önerir; 480 dk reflected XSS sızıntısında saldırgana büyük pencere. | Default'u `30` dk yap; dev için `.env.example` ayrı override koy. Refresh rotation zaten aktif — kısa access acıyı azaltmaz. |
| 4 | **P1** | `cors_origins` default `["http://localhost:3000"]` — config.py kod içinde, env override. **`allowed_hosts` default `["*"]`** (TrustedHost permissive). Prod-env değişkeni unutulursa wildcard. | Production deploy'da `ALLOWED_HOSTS` env eksik kalırsa Host header injection + cache poisoning + password reset link tampering. | Default'u `[]` yap (boş = fail startup); `app/config.py`'ye `@field_validator("allowed_hosts")` ekle: prod env'de boş ise `ValueError`. Fail-closed. |
| 5 | **P1** | Frontend `localStorage` access token saklıyor (XSS sızıntı yüzeyi). CSRF token middleware yok — write endpoint'ler `Authorization: Bearer` ile korunuyor ama cookie-fallback senaryosu varsa CSRF açık. | XSS reflected/stored bir noktada sızarsa access token çalınır (refresh rotation tek isabet sonrası 401 verir ama saldırgan ilk 30 dk içinde "ben gerçek user'ım" der). | Access token'ı `httpOnly; Secure; SameSite=Strict` cookie'ye taşı; CSRF için double-submit pattern (cookie + header). Refresh zaten cookie tabanlı ise tutarlı. **Frontend ajanıyla koordineli.** |
| 6 | **P1** | HIBP fail-open. API down olduğunda zayıf sızmış parola (örn. `Password123!`) kabul edilir. zxcvbn yeterince sıkı diye varsayılıyor ama `Password123!` zxcvbn skoru 3 alabilir (long enough). | Sızmış parola DB'ye girer; kullanıcı sonradan kredential stuffing kurbanı olur. | (a) HIBP `httpx.TimeoutException` retry 1x; (b) prod'da `hibp_check_enabled` zorunlu + circuit breaker 5dk; (c) login akışında da haftalık HIBP re-check ile aktif kullanıcılara uyarı. |
| 7 | **P2** | `SealedSecrets` controller key rotation prosedürü yok. SealedSecrets kontrolcü private key rotate edilirse mevcut `encryptedData` decrypt edilemez. | Operasyonel risk: key compromise senaryosunda yedek yok; controller pod kaybedilirse tüm sealed-secrets manifest'leri yeniden encrypt edilmeli. | (a) Controller private key off-cluster backup (age-encrypted, 3-2-1); (b) `kubeseal --re-encrypt` runbook → `docs/runbook/sealed-secrets-rotation.md`. **`devops` ajanı yazsın.** |
| 8 | **P2** | `_client_ip` sadece `request.client.host` okuyor (SEC-004 doğru karar) ama K8s ingress-nginx default'ta X-F-F'i `client.host`'a normalize etmez — `--forwarded-allow-ips` flag'i deploy'da set edilmemişse audit log'larda her zaman ingress IP görünür (e.g. `10.42.0.1`). | Audit forensic değer kaybeder — gerçek kullanıcı IP'si maskelenmiş olur, incident-response zorlaşır. | k8s/backend.yaml `command:` veya configmap'e `UVICORN_PROXY_HEADERS=true` + `UVICORN_FORWARDED_ALLOW_IPS=10.0.0.0/8,127.0.0.0/8` ekle. **`devops` doğrulasın.** |
| 9 | **P2** | `csp_policy` `default-src 'none'` API için ideal ama `/docs` Swagger UI prod'da açıksa CSP override yok → Swagger inline JS çalışmaz. | (a) `/docs` prod'da kapalı ise sorun yok; (b) açıksa silent breakage. | Prod'da Swagger UI'yi `app.openapi_url = None` ile kapat (security best practice); açık tutmak gerekirse path-specific CSP `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net`. |
| 10 | **P2** | `slowapi` MemoryStorage + `replicas=1` (SEC-003). Multi-replica'ya geçilmeden Redis backend deploy etmek gerek; aksi halde scale-out attack için kapı açık. | Şu anki saldırgan tek replica üzerinden zaten 10/dk'ya sınırlı. Ama trafik artarsa replica artırılınca rate-limit çarpansal genişler. | Redis pod + NetworkPolicy + `settings.redis_url` env zincir hazır; Faz I'da deploy. **`devops` PR.** |
| 11 | **P3** | `address_fingerprint` SHA-256 plaintext lowercase address; pepper yok. Rainbow table mümkün değil (256 bit) ama known-address oracle saldırısı — saldırgan DB'yi alır + bilinen popüler xpub'ları hash'leyip eşleşme arar. | Bilinen exchange hot wallet / whale adresleri ile kullanıcı ilişkilendirilebilir. | `address_fingerprint(addr, pepper=settings.fingerprint_pepper)` — HMAC-SHA256. Pepper Fernet key gibi ayrı env. Migration: yeniden compute (existing rows). |
| 12 | **P3** | `audit.py` `log_audit` `try/except Exception` yutuyor (best-effort design). Sentry/OTel'e exception forward edilmiyor. | Audit yazma silent fail ederse forensic incident-response sırasında bilinmeyen gap çıkar. | `except Exception as exc:` içinde `sentry_sdk.capture_exception(exc)` (best-effort + uyarı). OBS-001 entegre. |
| 13 | **P3** | `RequestTimingMiddleware` X-Response-Time header her response'a eklenir — saldırgana timing-channel ipucu (örn. user-exists vs not). | Timing attack için ölçülebilir delta (login `verify_password` her zaman çalışsın diye constant-time yapılıyor mu?). Genelde marjinal. | Prod'da `X-Response-Time` header'ı `enable_security_headers=True` iken kapatılabilir flag (`enable_response_time_header: bool = False`). Internal `/metrics/performance` zaten token-protected. |

---

## Best Practice / Reusability / Portability

### Best Practice (OWASP ASVS L2 + NIST 800-63B gap'leri)

- **V2.1.7 (Password Strength):** ✓ zxcvbn + HIBP — uyumlu.
- **V2.2.1 (Anti-Automation):** ✓ slowapi rate limit auth endpoint'lerinde mevcut; eksik → write endpoint'lerin (`POST /expenses`, `POST /wallets`) bazıları rate-limit'siz. **`POST` zincirine genel `30/minute` koy.**
- **V3.3.1 (Session Token Lifetime):** ⚠ Default 480 dk, prod 30 dk; bkz. Not #3.
- **V3.5.2 (Session Termination):** ✓ refresh rotation + `revoked_tokens` blacklist + cleanup cron.
- **V4.3.2 (Anti-Clickjacking):** ✓ XFO DENY + CSP `frame-ancestors 'none'`.
- **V6.2.2 (Algorithms):** ✓ Fernet (AES-128-CBC + HMAC-SHA256), bcrypt (cost default 12), SHA-256. **Eksik:** Argon2id parola hash'i bcrypt'ten daha modern; göç planı yok.
- **V7.1.1 (Logging):** ⚠ `logger.exception` stack trace'leri yazıyor ama log aggregator'da PII filter middleware uygulanıyor mu doğrulanmalı (örn. Sentry breadcrumb'da email görünmemeli).
- **V9.1.1 (TLS):** ✓ ingress; ⚠ backend↔postgres bkz. Not #2.
- **V10.3.1 (Code Integrity):** ✓ image SHA pinning kustomize ile mümkün; ⚠ şu an semver tag (`v0.0.0` placeholder). Mutable tag yerine immutable digest'e geç.
- **V13.1.5 (API Versioning):** ✓ `/api/v1/...` prefix.

### Reusability (security helper'ları modül-bağımsız mı?)

- `app/core/masking.py` → ✓ `mask_email/mask_address/hash_email` saf fonksiyon, dependency yok. Bir başka proje import edebilir.
- `app/core/security.py` → ⚠ `_fernet` modül-seviyesi global; `Settings` import zinciri Pydantic'e bağlı. **Daha portable:** `def build_fernet(primary: str, secondaries: list[str])` factory + caller cache.
- `app/services/audit.py` → ⚠ `log_audit` `AuditLog` ORM modeline + AsyncSession'a sıkı bağlı. SaaS multi-tenant'ta tenant_id kolonu zorunlu olur; şu an yok.
- `app/core/password_policy.py` → ✓ `check_password_strength` saf; `check_hibp_pwned` httpx'e bağlı (kabul edilebilir).
- **Genel öneri:** `app/core/security/` paketine refactor — `fernet.py`, `jwt.py`, `bcrypt.py`, `mask.py`. Şu an `security.py` 100 satır ama 6 sorumluluk taşıyor (god module).

### Portability (hard-coded değerler)

- ⚠ `email_from = "KFinans <noreply@kfinans.app>"` config.py default — `.kfinans.app` domain'i koda gömülü. Multi-tenant SaaS'a geçişte sorun. **Öneri:** env zorunlu, default boş.
- ⚠ `k8s/backend.yaml::livenessProbe.httpHeaders[].value: kfinans.app` — TrustedHost workaround'u olarak makul ama kustomize overlay'siz override yok. **Öneri:** kustomize `patches` ile env-specific.
- ⚠ `mfa.py::provisioning_uri(issuer_name="KFinans")` — TOTP issuer hard-coded; white-label senaryosunda dinamik olmalı. **Öneri:** `settings.app_name`.
- ⚠ SealedSecret `name: kfinans-secrets` + `namespace: kfinans` her yerde gömülü. Multi-env (staging/prod) için namespace override gerekli; kustomize `namePrefix`/`namespace` zaten kullanılabilir, doğrulanmalı.
- ⚠ Master Fernet key path: `.env` (lokal) + SealedSecret (prod). **Eksik:** dev/staging arasında otomatik provisioning script yok — yeni geliştirici manuel `Fernet.generate_key()` çalıştırıp `.env`'e yazmak zorunda. `scripts/dev-bootstrap.sh` veya `make dev-secrets`.
- ✓ Database URL, Redis URL, OTEL endpoint, Sentry DSN hepsi env — taşınabilir.

---

## Eylem Sırası (Production Launch Öncesi)

1. **P0-1 KVKK placeholder** → `compliance-expert` ajanı (1 gün)
2. **P0-2 DB TLS require + CA mount** → `dba` + `devops` (1 gün)
3. **P1-3 Access token default 30 dk** → tek satır config (5 dk)
4. **P1-4 allowed_hosts fail-closed validator** → 30 dk
5. **P1-5 httpOnly cookie + CSRF** → frontend + backend koordineli (1-2 gün)
6. **P1-6 HIBP retry + circuit breaker** → 2 saat

P2/P3 launch sonrası ilk iterasyona ötele.
