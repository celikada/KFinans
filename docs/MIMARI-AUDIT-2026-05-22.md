# KFinans Mimari Audit — 2026-05-22

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

> **Kapsam:** Production rc7 deploy sonrası ilk kapsamlı mimari gözden geçirme.
> **Bağlam:** 2026-05-21 büyük audit fix turu (PII mask, MultiFernet, zxcvbn+HIBP, DB TLS, age backup, etcd encryption, NetworkPolicy 7 default-deny, MFA TOTP, ROFS, SealedSecrets) tamamlandı; 13 commit `develop`'a push edildi.
> **Yöntem:** 6 kavram × 3 prensip = 18 mini bölüm + numaralı düzeltme notları (P0/P1/P2/P3 öncelikli).
> **Çıktı:** Salt analiz; bu PR kod değiştirmez.

---

## Yönetici Özeti

KFinans, "modüler monolit" kararını doğru uygulamış. `BaseIntegration` + `BaseBlockchainIntegration` + `BaseExchangeIntegration` arayüzleri 13 entegrasyon servisi (10 blockchain + 3 exchange) tarafından tutarlı kullanılıyor; `AssetData` dataclass ile aggregator/snapshot boyunca tek normalize tip taşınıyor. Bu mimari karar projenin en sağlam yanıdır.

Buna karşılık portability ve reusability ekseninde **3 kritik tema** öne çıkıyor:

1. **Hard-coded production değerleri** (`141.144.243.54`, `kfinans.app`, `sonar.192.168.3.191.nip.io`, `docker.io/celikada/...`) en az 7 dosyaya dağılmış — multi-env / multi-cloud taşıma için kustomize overlay disiplini eksik.
2. **Vendor lock-in noktaları** sistematik adapter pattern yerine doğrudan SDK import ediyor: `anthropic.AsyncAnthropic` doğrudan `advisor.py`'a bağlı; `ccxt`, `Resend SDK`, `sentry_sdk` benzer şekilde.
3. **Frontend reusability borcu** — 17 dashboard page'inde tekrar eden auth/fetch/error pattern'i (`useState/useEffect` + `try/catch err.message.includes("401")` + `setLoading`) için `useResource` veya React Query gibi bir abstraction yok; FE-005 sadece auth guard'ı tek noktaya çekti, data fetching hâlâ kopyalanıyor.

Aşağıdaki 18 mini bölüm bu temaları detaylandırıyor; sonra 27 numaralı düzeltme notu öncelik sırasıyla listeleniyor.

---

## 1. Tasarım

### 1.1 Modüler Monolit Kararı

- **İyi:** `app/services/{exchange,blockchain}/` net ayrımı + `BaseIntegration` arayüzü ile 13 entegrasyon tek pattern (`fetch()` + `health_check()`). `aggregator.py` → `snapshot.py` veri akışı tek yöne; cyclic dependency yok. `project_saas_architecture_decision.md` mikroservise geçmeme kararını dokümante etmiş.
- **Risk:** `app/api/v1/` altında 24 router var (advice, asset_catalog, audit_logs, auth, bes, budget, cash, cash_flow, commodity, credit_cards, expenses, goal, income, integrations, manual_crypto, metrics, mfa, planned_expenses, portfolio, stocks, tefas, user, wallets). "Finans" ve "yatırım" sınırı silikleşmeye başladı; finans grubu (expenses/income/budget/cash_flow/planned/credit_cards/goal) ayrı bir alt-domain modülü olarak ayırılabilir.
- **Eksik:** Domain-driven design anlamında "bounded context" yok — `app/services/` flat; finans-içi servis (örn. `ExpenseService`) yok, business logic API katmanında.

### 1.2 Domain Modelleme

- **İyi:** Pydantic v2 modern stiller (DEPS-001) zorunlu kuralda, `model_config = ConfigDict(...)`.
- **Risk:** Anemic Domain Model. `app/models/` SQLAlchemy ORM nesneleri sadece veri taşıyor; business logic API katmanına dağılmış. Örnek: çift sayım kuralı (`credit_card_id IS NOT NULL AND is_paid=true` → hariç tut) en az 3 endpoint'te tekrar eder (`expenses/summary`, `budgets/comparison`, `planned-expenses/forecast`).
- **Eksik:** `Expense` domain method'u (`is_double_counted()`) yok; mantık SQL filter'ında. Test edilebilirlik düşük.

### 1.3 Event-Driven Olur mu?

- **İyi:** Şu an synchronous + scheduler yeterli — kullanıcı volumesi düşük.
- **Risk:** APScheduler in-process; multi-replica deploy'da `pg_try_advisory_lock` ile leader election yapılıyor (ARC-011) — defence-in-depth iyi ama lock acquire'lı tek pod hâlâ büyük iş yapıyor.
- **Eksik:** SaaS Faz 2'de "kredi alındı → email gönder → audit log yaz → kullanıcıya bildir" gibi multi-step iş akışları için event bus (Redis Streams / RabbitMQ) yok. Şu an sync chain — biri fail ederse rollback transactional değil. `redis_url` config var ama sadece slowapi için.

---

## 2. Uygulama

### 2.1 Async/Await Tutarlılığı

- **İyi:** SQLAlchemy async + asyncpg + httpx + anthropic.AsyncAnthropic + asyncio.gather paralelizm. Blockchain servislerinde modül seviyesinde `asyncio.Future` ile single-flight pattern (bitcoin.py, avalanche.py).
- **Risk:** Test sürelerinde sync code path yok ama `RequestTimingMiddleware` `time.perf_counter()` global event loop için doğru ölçer; multi-worker uvicorn'da per-process metric.
- **Eksik:** Backup CronJob shell script (`wget age binary`) ve `cert-prep initContainer`'da Python kullanılmıyor — Pod restart süresi ekstra 2-3 sn (her yedeklemede internet'ten age binary indiriliyor). Birden fazla ROFS=true initContainer var ama image katmanına age binary gömme alternatifi denenmemiş.

### 2.2 Error Handling

- **İyi:** BACK-008 generic exception handler (`IntegrityError → 409`, `SQLAlchemyError → 500`, `Exception → 500`) + sanitized `{detail, code, request_id}` formatı + `request_id` log korelasyonu. SEC-007 ile 5 yerden `str(e)` echo'su temizlenmiş.
- **Risk:** `advisor.py` 6 farklı Anthropic exception tipini ayrı handle ediyor (RateLimitError, APITimeoutError, APIConnectionError, AuthenticationError, BadRequestError, APIStatusError, AnthropicError fallback) — pattern tutarlı ama 60+ satır boilerplate her external SDK için ayrı yazılmak zorunda kalacak. `httpx` çağıran 10 blockchain servisinde benzer mapping yok (status code'lar log'a düşüyor, FastAPI'ye exception olarak ulaşmıyor → 503).
- **Eksik:** `app/core/exceptions.py` gibi domain-spesifik exception hierarchy yok (`KFinansError → ExternalAPIError → AnthropicAPIError`). External API failure'ları "circuit breaker" pattern ile değil "log + return 0" pattern'i ile karşılanıyor (fault-tolerance pattern dokümante ama mekanik koruma yok).

### 2.3 Logging — Structured mı?

- **İyi:** `logger.info/warning/exception` her yerde kullanılıyor, `request_id` audit log'a eşleşiyor.
- **Risk:** `main.py:22-25` `logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")` — **plain text**, JSON değil. Sentry breadcrumb'lar yapılandırılmış ama Loki/CloudWatch aggregator'da grep ile filtre zor.
- **Eksik:** `python-json-logger` veya `structlog` ile JSON log formatter prod'da aktif değil. Kubernetes log ingestion için kritik (Promtail/Fluent Bit JSON parse istiyor).

### 2.4 Test Coverage

- **İyi:** Backend 192 unit + 357 integration (~%57 line, %50 branch, kritik path %90). `tests/integration/conftest.py` autouse `_truncate_after_test` test isolation'ı (TEST-004).
- **Risk:** Frontend tek test dosyası: `frontend/__tests__/api.test.ts`. Vitest threshold %30'dan %15'e düşürülmüş (`.gitlab-ci.yml:121-123`). 17 dashboard page için zero component test, zero render test, zero hook test.
- **Eksik:** Playwright @smoke E2E var ama unit/component test yok. Custom hook'lar (`useFocusTrap`, `useTranslation`, `useConfirm`) test edilmemiş — refactor'da regression yakalanmaz.

---

## 3. Bakım

### 3.1 Observability — Sentry + OpenTelemetry

- **İyi:** OBS-001 opt-in tasarım — DSN/endpoint boş ise no-op, KVKK güvenli (`send_default_pii=False`). FastAPI + SQLAlchemy + asyncpg + httpx instrumentation hazır.
- **Risk:** Production rc7 deploy edildi ama `SENTRY_DSN` ve `OTEL_ENDPOINT` configmap/secrets'ta set edilmiş mi belgelenmiş değil; runbook'ta deploy doğrulama adımı yok.
- **Eksik:** Sentry alert kuralları ve OTel sampling stratejisi tanımlanmamış. `traces_sample_rate=0.1` (%10) production trafiğine göre revize edilmeli — düşük volume'de %100 ekonomik olabilir.

### 3.2 Runbook

- **İyi:** `docs/infrastructure-runbook.md` DNS + Email + propagation komutlarını içeriyor; her değişiklik için git commit zorunluluğu var.
- **Risk:** Acil durum komutları (full DB restore, master key swap, secret rotation, Oracle VM disk full, K3s node-down recovery) dokümante değil veya dağınık.
- **Eksik:** RTO/RPO tanımı yok. KVKK m.12 "veri ihlali 72 saat içinde bildirim" ile uyumlu DR drill yapılmamış (`tech_debt_xpub_encryption.md` memory'de mekanik test eksikliği belirtiyor).

### 3.3 Dependency Rotation

- **İyi:** `pyproject.toml` pinning 2026-05-21'de yapıldı; Dependabot haftalık pip + npm + actions + docker.
- **Risk:** `release.yml` GHCR atıl durumda (`k8s/README.md:122`), GitLab CI primary; ama GHCR workflow'u silinmedi — kafa karışıklığı yaratabilir.
- **Eksik:** `package.json` ve `pyproject.toml` deprecation policy yok. `Next.js 16` + `React 19` + `Tailwind v4` cutting edge — bug yüzeyi artıyor.

### 3.4 Database Migration Zinciri

- **İyi:** 40 migration head'i `f7a8b9c0d1e2_dba001_fk_cascade_sec002_lockout.py` (gerçek son revision). `tests/integration/test_migrations.py` ile up/down roundtrip test ediliyor.
- **Risk:** CLAUDE.md "Migration head: c0d1e2f3a4b5 (AI-005 anthropic_consent kolonları, 2026-05-10)" diyor — **eski**. Gerçek head 7 migration daha ileride. Doküman güncel değil.
- **Eksik:** 5+ yıl proje horizonu için Alembic squash stratejisi yok. Cold start migration testi 40 migration tarayacak.

---

## 4. Kullanım

### 4.1 API Discoverability — Swagger UI

- **İyi:** FastAPI default `/docs` + `/openapi.json` (FastAPI 0.x).
- **Risk:** `csp_policy = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"` — Swagger UI'nin script-src + style-src + img-src ihtiyacı ile çakışıyor. Production'da `/docs` muhtemelen kırık (CSP block) ama belgesi yok. `config.py:51` yorumu "Swagger UI kullanımı için override" diyor ama override şartı belirtilmiyor.
- **Eksik:** Production'da `/docs` ve `/openapi.json` `enable_security_headers=True` ile birlikte ya **disable** edilmeli ya da CSP exception eklenmeli. Şu an saldırgan `/openapi.json` ile tüm endpoint listesini alabilir.

### 4.2 Frontend i18n

- **İyi:** `tr.json` ve `en.json` 335 anahtar eşleşmiş (parity).
- **Risk:** CLAUDE.md "Şu an çevrili: login + dashboard layout. Geri kalan sayfalar TR-only" — i18n-002 progress (project_i18n_002_full_translation.md memory) incremental devam ediyor.
- **Eksik:** TR-only string'lerin RTL/numeric format'ı için ICU MessageFormat yok; `Intl.NumberFormat` doğru kullanılıyor mu test edilmemiş.

### 4.3 Error UX

- **İyi:** 422 detail TR mesajlar; 500 sanitized `request_id` ile.
- **Risk:** `request_id` frontend'e dönüyor ama kullanıcıya gösterilmiyor (support ticket için kritik).
- **Eksik:** Error boundary yok (Next.js `error.tsx` her route segment için). Component crash sonrası beyaz ekran.

---

## 5. Yedekleme

### 5.1 Postgres Logical Backup

- **İyi:** DEVOPS-009 + audit #4 — `pg_dump | gzip | age -r <pub-key>` her gün 02:00 Europe/Istanbul. Asymmetric encryption — cluster compromise olsa bile yedek okunamaz.
- **Risk:** `backup-cronjob.yaml:125-129` age binary'sini her run **internet'ten** indiriyor (GitHub release). Supply-chain riski (GitHub down → backup down) + ağ trafik maliyeti. Image katmanına gömüldüğünde her run 3-5sn tasarruf + offline kapasite.
- **Eksik:** Backup integrity test (`gunzip -t` ve `age -d` test mode) cron yok. Bozuk backup tespiti silindiği güne kadar geç.

### 5.2 Off-Site Sync

- **İyi:** Backup retention 30 gün, local-path PVC 5Gi.
- **Risk:** **PVC local-path → node failure = total data loss.** Hem postgres-data hem postgres-backups aynı node'da; Oracle VM ölürse iki katman birden gider. CLAUDE.md `Off-site sync YOK (rclone Oracle Object Storage epic)` doğrulandı.
- **Eksik:** Rclone Oracle Object Storage / S3 sync CronJob yok. KVKK m.12 + ISO 27001 backup off-site zorunluluğu karşılanmıyor.

### 5.3 DR Drill

- **İyi:** Restore prosedürü `backup-cronjob.yaml` yorumlarında dokümante.
- **Risk:** Mekanik test edilmedi (`tech_debt_xpub_encryption.md` memory'de master key drill yok).
- **Eksik:** Yıllık DR drill kalender event'i yok. Hangi runbook + hangi sürede restore edileceği belirsiz.

---

## 6. Güvenlik

### 6.1 Audit Fix Status

- **İyi:** 2026-05-21 audit raporu 11/11 fix tamam: PII mask, MultiFernet rotation, zxcvbn+HIBP, DB TLS (TLSv1.3), age backup, etcd encryption, NetworkPolicy 7 default-deny, MFA TOTP, ROFS, SealedSecrets.
- **Risk:** SealedSecrets controller private key tek node'da; controller kaybedilirse SealedSecret'lar decrypt edilemez (yeni encrypt mümkün ama eski'ler yetim).
- **Eksik:** Audit raporu sonrası 30 günlük "deep scrub" (forgotten secret in git history, .env.example'da örnek değerler vs.) yapılmamış.

### 6.2 KVKK Compliance

- **İyi:** COMP-004 hard-delete cron + COMP-022 audit retention + KVKK rights endpoints + anthropic_consent.
- **Risk:** 13 placeholder bekliyor (project_kvkk_placeholders.md memory: ticari ünvan, KEP, tebligat adresi, mahkeme, mailbox `kvkk@kfinans.app` + `privacy@kfinans.app`). Bu **production blocker**.
- **Eksik:** VERBIS kayıt durumu belirsiz (KVKK m.16 — veri sorumluları siciline kayıt zorunlu).

### 6.3 Vendor Lock-In Riskleri

- **İyi:** PostgreSQL standart SQL.
- **Risk:** `pg_try_advisory_lock` PostgreSQL-spesifik (`backend/app/scheduler.py:46-49`); SQLite/MySQL'e taşınamaz. Bu kabul edilebilir bir trade-off ama dokümante edilmemiş.
- **Eksik:** Anthropic API tek noktada (`advisor.py:177` `anthropic.AsyncAnthropic`); OpenAI/Gemini fallback adapter yok. Anthropic outage = advice feature 0.

---

## 7. Yeniden Kullanılabilirlik

### 7.1 BaseIntegration

- **İyi:** `BaseBlockchainIntegration` 10 zincir tarafından (sonic, ethereum, bitcoin, avalanche P+C, solana, cardano, algorand, polkadot, litecoin) tutarlı uygulanmış. `BaseExchangeIntegration` 3 borsa (binance, binancetr, icrypex) için.
- **Risk:** `evm_tokens.py` ortak ERC-20 logic'i içeriyor ama bir class değil; module-level function'lar. Test fixture standardize değil.
- **Eksik:** Ortak cache pattern (`_BALANCE_CACHE` + `_INFLIGHT`) bitcoin.py ve avalanche.py'da neredeyse aynı (~30 satır kopya). `app/services/blockchain/_cache.py` shared helper yok.

### 7.2 Frontend Component Reuse

- **İyi:** `_components/{ConfirmDialog, Logos, MkkHint, PageHeader, TLValue}.tsx` + `_hooks/useFocusTrap.ts` + `_i18n/I18nProvider.tsx`.
- **Risk:** 17 dashboard page boilerplate'i: `useState(loading)`, `useState(error)`, `useState(data)`, `useEffect(() => refresh(), [...])`, `try/catch err.message.includes("401") → handle401()`. Her sayfada ~30 satır tekrar.
- **Eksik:** `useResource(fetcher)` hook veya `@tanstack/react-query` ile data fetching standardize edilmemiş. `handle401` her dosyada `useCallback` ile yeniden tanımlanıyor.

### 7.3 Backend Helper Modules

- **İyi:** `app/core/masking.py::mask_address`, `app/core/upload_validation.py::validate_excel_upload`, `app/services/audit.py::log_audit()` — tek noktada.
- **Risk:** `audit.log_audit()` best-effort (try/except yutar) iyi pattern ama 8 farklı eylem (auth.login/register/logout/password_change vs.) her endpoint'te manuel çağrı; FastAPI dependency veya middleware ile otomatik audit eksik.
- **Eksik:** Fernet helper modülü (`app/core/crypto.py`) yok; `cryptography.Fernet` + `MultiFernet` import'u her yerden ayrı (`security.py`, wallet model hybrid_property, vs.).

### 7.4 Migration Pattern Yeni Geliştirici Onboarding

- **İyi:** `alembic/versions/` naming convention `<rev>_<snake_case>.py`. Her migration commit mesajı Türkçe açıklama.
- **Risk:** 40 migration uzun chain; aralarında bağımlılık sırası okumak zor (revision id 12 char hex, dosya adı semantic değil — `1f2e3d4c5b6a_add_bes_holdings.py`).
- **Eksik:** `MIGRATION_GUIDE.md` yok. Yeni geliştirici "yeni migration nasıl üretilir, naming convention, rollback test" zincirini koddan keşfetmek zorunda.

---

## 8. Taşınabilirlik

### 8.1 Env Config

- **İyi:** `pydantic-settings` BaseSettings + `.env` + `.env.example` + `.env.prod.example`. Default değerler dev'e uygun, prod'da env override.
- **Risk:** `settings.allowed_hosts: list[str] = ["*"]` dev default — production'da `ALLOWED_HOSTS=["kfinans.app",...]` env ile override şart; unutulursa Host header injection açık. Test env ne durumda? (`config.py:56`)
- **Eksik:** `.env.staging.example` yok; staging environment için yapılandırma örneği eksik.

### 8.2 Hard-Coded Değerler

- **İyi:** Çoğu hard-coded değer dokümante (örn. `k8s/configmap.yaml:32` yorumu, `gitlab-ci.yml:24` ORACLE_VM_HOST).
- **Risk:** Aşağıdaki dosyalarda runtime/build değerler **inline**:
  - `k8s/networkpolicies/02-backend-ingress.yaml:32` — `ipBlock: 141.144.243.54/32` (kubelet probe için)
  - `k8s/backend.yaml:142,153,164` — `httpHeaders.Host: kfinans.app` (probe için)
  - `k8s/ingress.yaml:30-31, 34, 62` — `kfinans.app` + `www.kfinans.app` hosts
  - `k8s/configmap.yaml:22, 24, 31, 32` — CORS, ALLOWED_HOSTS, EMAIL_FROM, FRONTEND_URL
  - `.gitlab-ci.yml:24, 27, 252` — Oracle VM + SonarQube URL + production env URL
  - `docs/01-tasarim-dokumani.md:226` — Oracle VM IP
- **Eksik:** Kustomize **overlay** (`k8s/overlays/{oracle-prod, staging, dev}/`) yapısı yok. Tüm değerler base manifest'lere gömülü.

### 8.3 Cloud-Agnostic K8s

- **İyi:** Vanilla K8s primitives kullanılıyor; K3s spesifik yalnızca local-path storage class.
- **Risk:** `local-path` StorageClass K3s built-in; cloud-managed K8s'e (EKS, GKE, AKS) taşıma için storageClassName override şart. `postgres.yaml:158-159` yorumda multi-node migration planı var ama aktif değil.
- **Eksik:** Embedded Traefik K3s-spesifik. nginx-ingress veya Istio gateway'e taşıma için ingress.yaml `ingressClassName: traefik` + Traefik Middleware CRD'lerini yeniden yazma gerekecek.

### 8.4 Vendor Lock-In

- **İyi:** PostgreSQL, Docker, K8s — açık standartlar.
- **Risk:** Anthropic API → adapter yok (`advisor.py` Claude SDK doğrudan import). Resend → adapter yok (`email.py`). Docker Hub → registry değişimi `kustomization.yaml::images` + Dockerfile build değişikliği gerektirir.
- **Eksik:** LLM provider abstraction (`AIProvider` interface → `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`). Email provider abstraction (`EmailService` interface → `ResendBackend`, `SESBackend`, `SendGridBackend`).

### 8.5 Multi-Region Readiness

- **İyi:** Statelet servisler (backend, frontend) horizontal scale'e açık (replicas).
- **Risk:** Postgres tek replica, tek region. ARC-011 advisory lock multi-replica'ya hazır ama multi-region'a değil.
- **Eksik:** PostgreSQL streaming replication, async replica okuma trafiği için. CDN (Cloudflare/Akamai) frontend statik içeriği için yok — Oracle VM tek bölge bandwidth tasarrufu eksik.

### 8.6 Database Vendor Lock-In

- **İyi:** Çoğu sorgu standart SQL.
- **Risk:** `pg_try_advisory_lock` (scheduler.py), `JSONB` (audit_logs), `array_agg`/`tstzrange` (varsa) PostgreSQL spesifik. SQLite migration test ortamına bile alternative değil; `tests/integration/conftest.py` PG kullanıyor.
- **Eksik:** Database vendor değişimi senaryosu (RDS Aurora MySQL gibi) için adapter pattern yok.

---

## DÜZELTME NOTLARI — Numbered Priority List

### P0 — Production Blocker

**N1. KVKK 13 placeholder boşluğu**
- **SORUN:** Ticari ünvan, KEP adresi, tebligat adresi, mahkeme, `kvkk@kfinans.app` + `privacy@kfinans.app` mailbox kurulmamış (`project_kvkk_placeholders.md`).
- **ETKİ:** Production yayını yasal risk; KVKK m.10 (aydınlatma yükümlülüğü) ihlali. Veri öznesinin başvuru hakkı kullanılamaz.
- **ÖNERİ:** `docs/legal/` altındaki şablonları doldur; Namecheap Private Email veya Google Workspace ($6/ay) ile iki mailbox kur. VERBIS kaydını başlat.

**N2. Off-site backup yok — node failure = total data loss**
- **SORUN:** Hem postgres-data hem postgres-backups aynı Oracle VM'de local-path PVC'de. `141.144.243.54` ölürse 30 günlük backup da gider.
- **ETKİ:** KVKK m.12 + ISO 27001 backup off-site zorunluluğu karşılanmıyor; RPO ∞.
- **ÖNERİ:** Yeni CronJob (`k8s/backup-offsite-cronjob.yaml`): rclone ile age-encrypted backup'ları Oracle Object Storage (veya BackBlaze B2 / Cloudflare R2) bucket'a senkronize et. Her gün 03:00 (backup'tan 1 saat sonra). IAM bucket-write-only key. CLAUDE.md doğrulandı: "Off-site sync YOK (rclone Oracle Object Storage epic)" — bu epic P0 olmalı.

**N3. CSP + Swagger UI çakışması production'da**
- **SORUN:** `config.py:51` CSP `default-src 'none'` Swagger UI script-src + img-src + style-src ihtiyacı ile çakışıyor; ama `/docs` endpoint disable edilmemiş.
- **ETKİ:** `/openapi.json` saldırgana tüm endpoint envanterini veriyor (recon kolaylığı). Yerleşik enumeration başlığı.
- **ÖNERİ:** Production'da FastAPI `docs_url=None, redoc_url=None, openapi_url=None` (env-driven); dev'de aktif. Veya CSP'ye Swagger için exception path bazlı route handler ile uygula (sadece `/docs` için override).

### P1 — Önemli (Sonraki Sprint)

**N4. CLAUDE.md migration head bilgisi yanlış**
- **SORUN:** CLAUDE.md "Migration head: `c0d1e2f3a4b5`" diyor; gerçek head 7 migration ilerideki `f7a8b9c0d1e2_dba001_fk_cascade_sec002_lockout.py`.
- **ETKİ:** Yeni geliştirici yanlış `down_revision` ile migration yazar → çakışma.
- **ÖNERİ:** CLAUDE.md'yi `alembic heads` çıktısıyla senkronize tut; CI'da `alembic heads | grep <doc-head>` check ekle.

**N5. Hard-coded production değerleri (`141.144.243.54`, `kfinans.app`)**
- **SORUN:** 7+ dosyada (`k8s/networkpolicies/02-backend-ingress.yaml:32`, `k8s/backend.yaml:142/153/164`, `k8s/ingress.yaml:30-31/34/62`, `k8s/configmap.yaml:22/24/31/32`, `.gitlab-ci.yml:24/252`) inline.
- **ETKİ:** Multi-node K8s'e veya farklı cloud provider'a taşıma için 7 dosya elle düzenleme. Staging environment kurulamaz.
- **ÖNERİ:** `k8s/base/` + `k8s/overlays/{prod-oracle, staging-oracle, local-dev}/` kustomize overlay yapısı kur. Her overlay kendi configmap + networkpolicy + ingress patch'ini içersin. Liveness probe için `nodeSelector` + `kubernetes.io/hostname` etiketiyle ipBlock yerine label selector.

**N6. Frontend test coverage ~%3-15**
- **SORUN:** `.gitlab-ci.yml:121-123` vitest threshold %30'dan %15'e düşürüldü; sadece `__tests__/api.test.ts` var.
- **ETKİ:** 17 dashboard page için zero component test. Refactor regression yakalanmaz.
- **ÖNERİ:** Vitest + React Testing Library ile her `_components/` için snapshot + interaction test. `useFocusTrap`, `useTranslation`, `useConfirm` için unit test. Threshold'u kademeli %15 → %30 → %50.

**N7. Backup CronJob age binary'sini her run internet'ten indiriyor**
- **SORUN:** `backup-cronjob.yaml:125-129` `wget age-v1.2.1` GitHub release her gün.
- **ETKİ:** GitHub outage → backup down. Supply-chain riski (binary integrity her seferinde HTTPS güvene bağlı). Disk I/O + ağ ekstra 3-5sn.
- **ÖNERİ:** Custom backup image: `Dockerfile` → `FROM postgres:16-alpine` + `RUN wget age + verify SHA256 + COPY`. Image'i kendi registry'ne push et; CronJob bu image'i kullansın. Ya da `initContainer` ile binary persist (PVC'ye bir kez yaz).

**N8. Frontend dashboard 17 page data fetching boilerplate**
- **SORUN:** Her sayfa ~30 satır `useState/useEffect/try-catch err.message.includes("401")/handle401` kopya.
- **ETKİ:** DRY ihlali; yeni endpoint eklemek 17 yerden değişim gerektirir. Race condition / stale data riskleri bağımsız.
- **ÖNERİ:** `@tanstack/react-query` (ya da SWR) ile global data layer. `useResource(api.listExpenses, [year, month])` hook. 401 handling tek noktada (axios/fetch interceptor + react-query queryClient.setDefaultOptions). Tahmini saving: 500+ satır.

**N9. Anthropic API vendor lock-in (no adapter)**
- **SORUN:** `advisor.py:177` `self._client = anthropic.AsyncAnthropic(...)` doğrudan SDK. 6 exception type ayrı handle.
- **ETKİ:** Anthropic outage = advice 503; alternative LLM olmadan business continuity yok. Faz 2'de tavsiye paywall'lı feature olacak.
- **ÖNERİ:** `app/services/ai/base.py::AIProvider` interface (`generate(prompt: str, max_tokens: int) -> str`); `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider` ayrı module'ler. `advisor.py` provider'ı `settings.ai_provider` env'inden seç. Exception mapping ortak helper'da.

**N10. Email vendor lock-in (Resend SDK direct)**
- **SORUN:** `app/services/email.py` Resend SDK doğrudan import.
- **ETKİ:** Resend outage / fiyat değişimi → tek nokta arıza.
- **ÖNERİ:** `EmailService` interface; `ResendBackend`, `SESBackend`, `SendGridBackend`. Settings'ten provider seç.

**N11. Anemic Domain Model — çift sayım kuralı 3 endpoint'te kopya**
- **SORUN:** `or_(credit_card_id IS NULL, is_paid=false)` filtresi `expenses/summary`, `budgets/comparison`, `planned-expenses/forecast`'ta tekrar.
- **ETKİ:** Logic değişimi 3 dosyada eşzamanlı; biri unutulursa raporlar tutarsız.
- **ÖNERİ:** `app/services/expense_service.py::is_double_counted_filter()` helper veya SQLAlchemy `@hybrid_method` ile `Expense.is_raw_expense`. Tek yerden tüketim.

**N12. SealedSecrets controller private key tek node'da**
- **SORUN:** `kube-system/sealed-secrets-controller` master key oraclu VM'de.
- **ETKİ:** Node ölürse SealedSecret'lar decrypt edilemez (yeni encrypt başarısız değil ama mevcut secret'lar yetim). DR senaryosu kırık.
- **ÖNERİ:** Controller master key'i offline backup et (`age` ile encrypt → `.credentials.local.md §9 + USB`). DR runbook'a "controller restore" prosedürü ekle.

**N13. Frontend `NEXT_PUBLIC_API_URL` build-time bake**
- **SORUN:** `frontend/lib/api.ts:1` `process.env.NEXT_PUBLIC_API_URL ?? "..."` — runtime'da değişmez (Dockerfile ARG ile bake).
- **ETKİ:** Aynı container image staging + prod'a deploy edilemez; her env için ayrı build.
- **ÖNERİ:** Runtime config injection: `public/config.js` (deploy-time scriptle generate) veya `useApiBase()` hook (window.location.origin'den türet). Alternative: Next.js `next.config.ts::publicRuntimeConfig` (deprecated; ama Next 16'da `headers()` ile runtime read).

**N14. Plain text logging (JSON structured eksik)**
- **SORUN:** `main.py:22-25` `format="%(asctime)s %(levelname)s %(name)s %(message)s"`.
- **ETKİ:** Loki/CloudWatch/Datadog log aggregator JSON parse zorlanır; structured query (filter by `user_id`, `request_id`) regex bazlı.
- **ÖNERİ:** `python-json-logger` veya `structlog` ile JSON formatter; `request_id` extra dict'te. Sentry breadcrumb'lar zaten JSON; bütünlük için log da olmalı.

**N15. APScheduler in-process — multi-replica leader sadece advisory lock**
- **SORUN:** Her replica scheduler başlatıyor, sadece lock alabilen iş yapar.
- **ETKİ:** N replica × 4 cron × kalkış overhead'i; lock contention log'larında gürültü.
- **ÖNERİ:** `SCHEDULER_ENABLED=true` sadece 1 replica'ya (kustomize patch); diğerleri başlatma. Veya Celery Beat + Redis ile dış scheduler.

**N16. Backend exception hierarchy yok**
- **SORUN:** `app/core/exceptions.py` yok; `HTTPException` her endpoint'te doğrudan raise.
- **ETKİ:** Domain hatası (örn. `InsufficientCreditError`) ile HTTP transport hatası ayrılmıyor.
- **ÖNERİ:** `class KFinansError → InsufficientCreditError, ExternalAPIError, ValidationError`. `main.py`'a `KFinansError` exception_handler ile HTTP status mapping. Domain layer transport bağımsız test edilebilir.

**N17. Frontend `error.tsx` route error boundary yok**
- **SORUN:** Next.js App Router her route segment için `error.tsx` boundary tanımlanmamış.
- **ETKİ:** Component crash = beyaz ekran; Sentry browser SDK yok (`docs/runbook`'ta belirtilmemiş).
- **ÖNERİ:** `frontend/app/dashboard/error.tsx` + `frontend/app/error.tsx` ekle. Sentry browser SDK init.

### P2 — İyileştirme

**N18. Blockchain servislerinde cache pattern kopya**
- **SORUN:** `bitcoin.py` ve `avalanche.py` her ikisi de `_BALANCE_CACHE` (dict, 10dk TTL) + `_INFLIGHT` (asyncio.Future) pattern'ini ~30 satır kopya içeriyor.
- **ETKİ:** Yeni zincir eklerken bu pattern üçüncü kez yazılacak.
- **ÖNERİ:** `app/services/blockchain/_cache.py::TTLCache` + `@single_flight` decorator. Mevcut iki servis migrate.

**N19. Migration naming convention eksik**
- **SORUN:** `1f2e3d4c5b6a_add_bes_holdings.py` — revision id semantic değil; yeni geliştirici sırasını okumak için file mtime veya `alembic history`'e bakar.
- **ETKİ:** Onboarding sürtünmesi; PR review'da bağımlılık sırası gözden kaçar.
- **ÖNERİ:** `MIGRATION_GUIDE.md` yaz: naming convention, `alembic revision --autogenerate -m "..."` flow, rollback testi, head update zorunluluğu.

**N20. `audit.log_audit()` her endpoint'te manuel çağrı**
- **SORUN:** 8 kritik eylem her birinde 3-5 satır audit log boilerplate.
- **ETKİ:** Unutulma riski; yeni endpoint sahibi audit log'u atlar.
- **ÖNERİ:** FastAPI dependency veya middleware ile otomatik audit (route metadata'da `audit_action="wallet.add"` annotation). Decorator: `@audited("wallet.add", resource_key="wallet_id")`.

**N21. CONFIG `enable_security_headers=True` test'te de aktif**
- **SORUN:** `config.py:47` yorum "Production'da True; testlerde header beklemek için açık tutulur. Dev ortamda Swagger UI deneyimini bozmamak için False yapılabilir." Ancak default True.
- **ETKİ:** Dev'de Swagger UI broken (yukarıdaki N3 ile bağlantılı).
- **ÖNERİ:** Dev'de False default; test'te conftest fixture'da explicit True. Production env override.

**N22. Frontend `useEffect` lint uyarısı (settings)**
- **SORUN:** `tech_debt_settings_useeffect.md` memory'de "React 19 cascading renders; useSyncExternalStore'a refactor önerilir".
- **ETKİ:** Render performansı + potansiyel double-fetch.
- **ÖNERİ:** Settings sayfasında `useSyncExternalStore` ile localStorage subscription. React Compiler aktif olduğunda otomatik optimize.

**N23. Cost basis validation testleri fail (3 test)**
- **SORUN:** `tech_debt_cost_basis_validation.md` memory: "3 test 422 bekliyor ama schema 0/negative → None çeviriyor; testler güncellenmeli."
- **ETKİ:** Test suite kırık veya `pytest --deselect` ile gizli.
- **ÖNERİ:** Test beklentilerini schema davranışına uyumla (None için 200 + cost_basis_tl=None expected). Veya schema'yı 422 dönecek şekilde değiştir + kullanıcı UX ile uyumlu hata mesajı.

**N24. Backup integrity verification eksik**
- **SORUN:** CronJob backup oluşturuyor ama doğrulamıyor.
- **ETKİ:** Bozuk backup sessizce birikir; restore anında fark edilir.
- **ÖNERİ:** Backup CronJob sonuna `age -d -i <key> | gunzip -t` smoke test ekle (test key cluster'da hot mount, sadece test mode). Veya weekly ayrı CronJob ile son 7 backup'ı test et.

**N25. Sentry/OTel production'da set edilmiş mi belgesi yok**
- **SORUN:** rc7 deploy edildi; runbook'ta `SENTRY_DSN` + `OTEL_ENDPOINT` aktivasyon adımı yok.
- **ETKİ:** Hatalar yakalanmıyor olabilir, fark edilmez.
- **ÖNERİ:** `docs/infrastructure-runbook.md`'a "Observability Aktivasyon" bölümü ekle: secret kurulum + smoke test (`/health` → Sentry breadcrumb).

### P3 — Gelecek

**N26. Alembic migration squash (5+ yıl horizon)**
- **SORUN:** 40 migration; cold start uzayacak (her test setup'ta 40 step run).
- **ETKİ:** CI hızı düşer (~30sn migration overhead per job).
- **ÖNERİ:** 5+ yıl sonra (~100 migration eşiği) squash etap: ilk N migration'ı tek `00000000_baseline.py`'a birleştir; eski migration'lar archive folder'a.

**N27. Multi-region readiness — Postgres streaming replication**
- **SORUN:** Stateful service tek region, tek replica.
- **ETKİ:** Bölgesel outage = total downtime.
- **ÖNERİ:** Postgres replica (Patroni ya da `pg_basebackup` + streaming) ikinci region (örn. Frankfurt). Read-only replica analytic query'lere yönlendir. SaaS Faz 2 sonrası uygun.

---

## Somut Kod Çelişkileri (Özet Liste)

| # | Konum | Tip | Sorun |
|---|-------|-----|-------|
| 1 | `k8s/networkpolicies/02-backend-ingress.yaml:32` | Hard-coded IP | `ipBlock: 141.144.243.54/32` |
| 2 | `k8s/backend.yaml:142,153,164` | Hard-coded host | probe `httpHeaders.Host: kfinans.app` |
| 3 | `k8s/ingress.yaml:30,31,34,62` | Hard-coded host | TLS + rules host'ları |
| 4 | `k8s/configmap.yaml:22,24,31,32` | Hard-coded | CORS_ORIGINS, ALLOWED_HOSTS, FRONTEND_URL inline |
| 5 | `.gitlab-ci.yml:24,27,252` | Hard-coded | Oracle VM + SonarQube URL + env URL |
| 6 | `frontend/lib/api.ts:1` | Build-time bake | NEXT_PUBLIC_API_URL Docker ARG'a bağlı |
| 7 | `backend/app/services/advisor.py:177` | Vendor lock | `anthropic.AsyncAnthropic` direct import |
| 8 | `backend/app/services/email.py` | Vendor lock | Resend SDK direct |
| 9 | `backend/app/scheduler.py:46-49` | DB vendor lock | `pg_try_advisory_lock` PostgreSQL-only |
| 10 | `backend/app/services/blockchain/bitcoin.py + avalanche.py` | DRY ihlali | `_BALANCE_CACHE + _INFLIGHT` 30 satır kopya |
| 11 | `frontend/app/dashboard/*/page.tsx` (17 sayfa) | DRY ihlali | data fetching boilerplate ~30 satır kopya |
| 12 | `backend/app/api/v1/{expenses,budgets,planned_expenses}.py` | DRY ihlali | çift sayım filter 3 yerde |
| 13 | `k8s/backup-cronjob.yaml:125-129` | Build-time anti-pattern | her run age binary GitHub'dan indirilir |
| 14 | `CLAUDE.md` migration head bilgisi | Stale doc | `c0d1e2f3a4b5` yerine `f7a8b9c0d1e2` (gerçek head) |
| 15 | `backend/app/main.py:22-25` | Logging | plain text format; structured JSON yok |
| 16 | `backend/app/config.py:47-51` + Swagger UI | CSP çakışması | `/docs` production'da CSP block, disable belgesi yok |
| 17 | `frontend/__tests__/` | Test gap | tek dosya, vitest threshold %15'e düşürülmüş |
| 18 | `k8s/postgres.yaml:158-159` (storageClass) | Portability | `local-path` K3s spesifik, multi-node migration plan yorumda |
| 19 | `backend/app/api/v1/router.py` (24 router) | Modüler sınır | finans + yatırım domain ayrımı silikleşti |
| 20 | `frontend/app/dashboard/settings/page.tsx` | React 19 anti-pattern | useEffect cascade (tech_debt memory) |

---

## Reusability / Portability İyileştirme Önerileri

### A. Backend

1. **`app/services/blockchain/_cache.py`** — TTLCache + `@single_flight` decorator (bitcoin/avalanche kopyasını ortadan kaldır).
2. **`app/services/ai/base.py`** — AIProvider interface; AnthropicProvider/OpenAIProvider/GeminiProvider implementasyonları. Settings'ten seç.
3. **`app/services/email/base.py`** — EmailService interface; ResendBackend/SESBackend implementasyonları.
4. **`app/core/exceptions.py`** — KFinansError hierarchy + HTTP mapping handler.
5. **`app/services/expense_service.py`** — Çift sayım kuralı tek noktada.
6. **`app/core/crypto.py`** — Fernet/MultiFernet helper, encrypt/decrypt/fingerprint helper'ları.

### B. Frontend

1. **`app/_hooks/useResource.ts`** — react-query veya custom hook ile data fetching standardize.
2. **`app/_hooks/useApiBase.ts`** — runtime config (window.location.origin türevli) bake'siz API URL.
3. **`app/_components/DataTable.tsx`** — 17 sayfa farklı ama benzer table'lar için generic component.
4. **`app/error.tsx`** + **`app/dashboard/error.tsx`** — Next.js error boundary.
5. **Sentry browser SDK** — runtime exception capture frontend.

### C. K8s / DevOps

1. **`k8s/base/`** + **`k8s/overlays/{prod-oracle, staging-oracle, local-dev}/`** kustomize overlay yapısı.
2. **`k8s/overlays/aws-eks/`** (gelecek) — storageClassName + ingressClass + cert-manager issuer + node selector farklılıkları.
3. **`docker/backup/Dockerfile`** — age binary gömülü custom postgres-backup image.
4. **`k8s/backup-offsite-cronjob.yaml`** — rclone Oracle Object Storage / S3 sync (P0).

### D. Documentation

1. **`docs/MIGRATION_GUIDE.md`** — Alembic naming + flow + rollback test + CLAUDE.md head sync.
2. **`docs/PORTABILITY.md`** — multi-cloud migration playbook (Oracle K3s → AWS EKS / GCP GKE / Hetzner / DigitalOcean).
3. **`docs/DR_DRILL.md`** — yıllık DR drill prosedürü (full restore + master key swap + SealedSecrets controller restore).
4. **`docs/OBSERVABILITY.md`** — Sentry + OTel aktivasyon + alert kuralları + dashboard query'leri.

---

## Sonuç

KFinans'ın **mimari iskeleti** sağlam — `BaseIntegration` arayüzü, async-first, modüler monolit, Pydantic v2 + SQLAlchemy async + Fernet + Audit Log + NetworkPolicy. 2026-05-21 audit fix turu güvenlik açısından önemli atılım.

Önümüzdeki sprint'lerde **2 P0 + 14 P1 düzeltme** odakta olmalı: KVKK placeholder + off-site backup + CSP/Swagger çakışması = production yayın blocker; sonra portability (kustomize overlay, vendor adapter, frontend data layer) yatırımları SaaS Faz 2'ye hazırlık için.

**Sonraki adım önerisi:**
1. P0 sırasında: KVKK mailbox + ticari bilgiler doldur (manuel/insan), `backup-offsite-cronjob` epic'i hazırla, `/docs` production disable kontrolü.
2. P1 sırasında: BACK adapter pattern (advisor → AIProvider), FE data fetching layer (react-query), kustomize overlay refactor (`k8s/overlays/`).
3. CLAUDE.md güncelle (migration head) — 30sn'lik bir doc fix ama yanlış bilgi compounding cost'a sebep oluyor.
