# CHANGELOG

Tüm önemli değişiklikler bu dosyada tarihsel olarak kaydedilir.
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) /
Versiyon: [Semantic Versioning](https://semver.org/lang/tr/spec/v2.0.0.html).

---

## [Unreleased] — develop branch

### FAZ H — Production Öncesi Sertleştirme (2026-05-06 → 2026-05-10)

FAZ G audit'i 240 bulgu raporladı; FAZ H'de 50+ issue kapatıldı (17 critical
kod + 33 high + ek doc/test). Production deploy önünde kod-tarafı blocker
kalmadı; 3 critical KVKK kullanıcı aksiyonu (#11/#12/#13) bekliyor.

#### Added — Yeni özellikler / endpoint'ler

- **AI tavsiye motoru SPK uyumlu** (#8 AI-003 + #10 AI-008): system prompt
  ~1500-2000 tokene çıkarıldı (Anthropic prompt cache aktif), zorunlu
  disclaimer footer + post-processing safety net.
- **Anthropic özel açık rıza** (#9 AI-005): `users.anthropic_consent_at` +
  `_version`. POST/DELETE `/user/anthropic-consent`. `/advice/generate`
  LLM çağrısından önce 403 gate (KVKK m.9).
- **AI kredi tüketim mantığı** (#41 AI-007): `ADVICE_COST=1` sabit, 402
  yetersiz kredi, slowapi 5/hour, atomik düşüm + `credits_used` kaydı.
- **Anthropic prompt cache metrikleri** (AI-002): `investment_advice.cache_read_tokens`
  + `cache_creation_tokens` kolonları, log'a metrik yazımı.
- **Advisor audit log** (AI-004): `ADVICE_GENERATE` action — KVKK m.12 üçlü
  taraf veri aktarımı izleme.
- **Password reset endpoint'leri** (#27 SEC-001): OWASP Forgot Password
  Cheat Sheet uyumlu `/auth/forgot-password` + `/auth/reset-password`,
  1 saat TTL, token rotation, generic 202 (kullanıcı enumeration engeli),
  lockout state clear. 8 yeni test.
- **Account lockout** (#28 SEC-002): `users.failed_login_count` +
  `locked_until`. 10 deneme = 15 dk kilit (OWASP ASVS V2.2.1). 423 Locked +
  Retry-After header.
- **Veri taşınabilirliği** (#42 COMP-003): `GET /user/data-export` JSON dump
  16+ tablo (KVKK m.11/d, GDPR Art.20). Audit `DATA_EXPORT`.
- **Açık rıza geri çekme** (#44 COMP-006): `overseas_consent_at`,
  `terms_accepted_at`, `kvkk_read_at` timestamp kolonları (KVKK m.5/1
  ispat yükü). `DELETE /user/consent/overseas`.
- **E-posta değiştirme** (#48 COMP-029): `email_change_new` + `email_change_token`
  (1 saat TTL). `POST /user/email/request` + `GET /user/email/confirm`
  (KVKK m.11/d düzeltme hakkı).
- **18+ yaş doğrulama** (#46 COMP-010): `RegisterRequest.age_confirmed`
  zorunlu (KVKK Kurul kararı 2018/482, TMK m.16). Frontend register'a
  zorunlu checkbox.
- **30 gün hard-delete cron** (#43 COMP-004): `_hard_delete_expired_users_job`
  her gün 04:00 (KVKK m.7). FK CASCADE + `audit_logs.user_id ON DELETE SET NULL`.
- **audit_logs retention cron** (#67 COMP-022): her gün 04:30, 365 gün TTL
  (KVKK m.7). PII fiziksel silme.
- **Veri ihlali müdahale planı** (#49 COMP-021): `docs/legal/incident-response-plan.md`
  ISO 27035 esinli, KVKK m.12/5 + GDPR Art.33 uyumlu. T+0..T+1 hafta timeline,
  KVKK Kurul + kullanıcı + basın şablonları, yıllık tatbikat (Ocak ayı).
- **Yahoo stale price detection** (#61 FIN-004): `StockQuote.is_stale` +
  `market_state`. `regularMarketTime > 30 saat` veya `chartPreviousClose`
  fallback halinde uyarı + UI rozet.
- **Cash flow özet kartı** (kullanıcı isteği): Dashboard header'a Toplam
  Portföy yanına bu ay + gelecek ay net (gelir − gider) Finans (Net Bakiye)
  kartı. Pozitif yeşil, negatif kırmızı.
- **Yükleniyor spinner**: Toplam Portföy başlığı yanında kripto + cüzdan
  loading durumunda spinner.
- **CHANGELOG.md** (#68 DOC-010): Bu dosya.
- **Production smoke test genişletme** (#79 DEPLOY-001):
  `release.yml::smoke-test` job Playwright'tan ÖNCE 4-step curl gate
  çalıştırır (~5 sn): frontend up, /health JSON, /auth/login bogus → 401,
  HSTS + X-Frame + CSP. Curl fail = deploy gate. Lokal runner:
  `frontend/scripts/smoke.sh` + `npm run smoke`. 2 yeni @smoke test
  (security headers + i18n switcher). docs/09-altyapi-test.md güncel.
- **i18n switcher overlap düzeltmesi**: TR/EN switcher dashboard
  layout'ta fixed-position'dan dashboard header'ına ve PageHeader'ına
  taşındı (kullanıcı geri bildirimi: Ayarlar/Çıkış üstüne biniyordu).
- **EN dil desteği foundation** (#78 i18n-001): Client-side cookie tabanlı
  TR/EN. `app/_i18n/dictionaries/{tr,en}.json` (auth + common + legal +
  footer anahtarları), `I18nProvider` React Context (`kfinans-locale`
  cookie, samesite=lax, 1 yıl), `useTranslation()` hook + `t("auth.login")`,
  `LanguageSwitcher` segmented (dashboard top-right + login top-right).
  Eksik anahtarlar key fallback. `<html lang>` dinamik güncelleme (ekran
  okuyucu duyurur). Login sayfası tam çevrildi (proof of concept). 16
  dashboard sayfası TR-only kaldı — incremental ileride. `app/[lang]/...`
  routing kullanılmadı (foundation için cookie context yeterli).
- **Sentry + OpenTelemetry distributed tracing** (#77 OBS-001):
  `app/observability.py::init_sentry/init_otel` `main.py` lifespan startup'ta
  çağrılır. Hepsi opt-in: `SENTRY_DSN` boş = no-op; `OTEL_ENDPOINT` boş = no-op.
  Sentry FastAPI + SQLAlchemy integration (exception capture, breadcrumb,
  perf monitoring, `send_default_pii=False` KVKK güvenli). OTel: FastAPI +
  SQLAlchemy + asyncpg + httpx instrumentation, `OTLPSpanExporter` HTTP.
  `traces_sample_rate` default %10. 7 yeni unit test (192 toplam unit).
  Frontend Sentry (`@sentry/nextjs`) ayrı issue.
- **Erişilebilirlik temel eklemeler** (#76 A11Y-001): `<html lang="tr">`,
  dashboard layout'ta sr-only "Ana içeriğe atla" skip-link, `useFocusTrap`
  hook (Tab/Shift+Tab modal döngüsü + Esc + initial focus restore),
  `SnapshotIssuesModal` aria-labelledby/describedby + focus trap, login
  formu `htmlFor` + `autoComplete=email|current-password` + error toast
  `role="alert" aria-live="assertive"`. 11 dosyada icon-only `✕` butonlarına
  aria-label + `<span aria-hidden="true">` + `focus-visible:ring-2`. 4 yeni
  Playwright @smoke test (`a11y.spec.ts`). Axe-core entegrasyonu ileride.
- **Request timing middleware** (#75 PERF-004): `RequestTimingMiddleware`
  her response'a `X-Response-Time` header'ı ekler; `>= 500ms` requestler
  WARNING log'a yazılır. Per-route ring buffer (deque maxlen=1000,
  template path ile gruplanır). `GET /api/v1/metrics/performance`
  token korumalı snapshot endpoint'i (p50/p95/p99/max + slow_count).
  OBS-001 (Sentry/OTel) eklenince deprecate edilebilir.

#### Changed — Mevcut davranış değişiklikleri

- **CI coverage gate** (#55 TEST-007): Line %50 → %60, branch %50, critical
  path (auth/security/masking) %90.
- **DB connection pool** (#33 DBA-004): pool_size=20, max_overflow=10,
  recycle=1800, pool_pre_ping. Multi-replica güvenli.
- **FK ondelete** (#31 DBA-001): integrations/wallets/snapshots/asset_positions/
  advice CASCADE; asset_positions.wallet_address_id + advice.snapshot_id
  SET NULL (history koru). Migration `f7a8b9c0d1e2`.
- **TEFAS fiyat helper** (#20 ARC-001): `_fetch_tefas_prices_for_codes`
  `app/api/v1/manual_crypto.py`'tan `app/services/tefas.py::fetch_tefas_prices_by_codes`'a
  taşındı (dependency inversion).
- **Snapshot job paralelizm** (#21 ARC-003): `asyncio.gather + Semaphore(5)`;
  100 user × 30sn → ~10 dk.
- **Multi-replica scheduler safety** (#23 ARC-011): `SCHEDULER_ENABLED` env
  + `pg_try_advisory_lock` defence-in-depth.
- **Multi-replica rate limit** (#29 SEC-003): `slowapi` Redis backend
  (`settings.redis_url`). K8s `replicas: 2 → 1` (Redis enable olana kadar).
- **WalletOut + WalletPositionOut address mask** (#26 BACK-013): Pydantic
  `field_serializer` ile `mask_address` (ilk 6 + son 4). xpub leak engeli.
- **Generic exception handler** (#22 ARC-006 + #25 BACK-008): main.py'a
  `IntegrityError → 409`, `SQLAlchemyError → 500 db_error`, `Exception →
  500 internal_error`. Hepsi `{detail, code, request_id}` sanitized format.
- **Snapshot endpoint response_model** (#24 BACK-001): `SnapshotPreviewOut`
  schema, `create_snapshot` dual-type fallback kaldırıldı.
- **Dashboard layout**: Finans grubu yukarı, Portföy aşağı; Snapshot al +
  Geçmiş butonları Portföy başlığı yanında, Nakit Akışı butonu Finans
  yanında (kullanıcı isteği).
- **Dashboard refactor** (#35 FE-003): page.tsx 971 → 654 satır. 3 component
  extraction (`icons.tsx`, `DashboardCard.tsx`, `SnapshotIssuesModal.tsx`).
- **Dashboard fetch orchestration** (#36 FE-004): 14 silent
  `.catch(() => {})` → `safe(label, fn)` wrapper + `cancelled` flag +
  `Promise.allSettled` orchestration.
- **DB izolasyon** (#53 TEST-004): function-scoped TRUNCATE autouse fixture
  her test sonunda. Testler artık kümülatif değil.
- **Migration test pattern** (#32 DBA-003): subprocess + `fresh_db` fixture
  ile alembic upgrade/downgrade round-trip 4 step.

#### Fixed — Hata düzeltmeleri

- **TCMB stale price USD fallback** (#58 FIN-005): Yahoo fail durumunda son
  bilinen USD fiyatına düş.
- **TCMB multi-currency cache** (#59 FIN-007): Cash holding GBP/USD/EUR
  TCMB rate cache (300s TTL).
- **unit_price_tl Numeric(28,10)** (#60 FIN-018): SHIB/PEPE mikro fiyat
  hassasiyeti (önce Numeric(18,4) yetersizdi).
- **Anthropic exception → HTTP status** (#38 AI-001): RateLimitError → 429
  Retry-After, APITimeoutError → 504, APIConnectionError → 503,
  AuthenticationError → 500, BadRequestError → 500, OverloadedError → 503.
- **JWT refresh rotation race** (TEST-005): rotation idempotency sequential
  test. Concurrent paralel test ASGITransport limit nedeniyle skip.
- **Yahoo Finance graceful degradation** (TEST-005): timeout / connect /
  malformed JSON / 5xx hepsi `_fetch_one` None döner.
- **CSP dev fix**: `next.config.ts` `connect-src` localhost:8000'a izin
  verir, `upgrade-insecure-requests` sadece prod. Dev'de "Failed to fetch"
  hatası düzeldi.

#### Security — Güvenlik düzeltmeleri

- **Wallet xpub Fernet** (FAZ C1): `wallet_addresses.address_encrypted` +
  `address_fingerprint` (SHA-256). `@hybrid_property` transparent
  decrypt/encrypt. Migration `b3c4d5e6f7a8`.
- **SecurityHeadersMiddleware** (FAZ C2): HSTS (1 yıl + preload), X-Frame
  DENY, X-Content-Type-Options, Referrer-Policy, CSP `default-src 'none'`,
  Permissions-Policy, COOP, CORP, Server maskeleme.
- **TrustedHostMiddleware** (FAZ C3): `settings.allowed_hosts` env'den.
  Host header injection koruması.
- **JWT TTL prod 30 dk + Refresh rotation** (FAZ C4): Prod 30 dk access;
  `/auth/refresh` her çağrıda eski refresh `jti` blacklist'e atar.
  Frontend single-flight refresh + 401 retry.
- **revoked_tokens cleanup cron** (FAZ C5): APScheduler her gün 03:00
  Europe/Istanbul.
- **Audit log altyapısı** (FAZ C6): `audit_logs` tablo + 10 hook (auth,
  wallet, integration, snapshot, account, advice, email_change, consent,
  data_export, password_reset). `GET /audit-logs` IDOR korumalı.
- **X-Forwarded-For spoofing engeli** (#30 SEC-004): `_client_ip` sadece
  `request.client.host`. Production Dockerfile CMD `--proxy-headers
  --forwarded-allow-ips="10.0.0.0/8,127.0.0.0/8"`.
- **Wallet xpub Excel mask** (#47 COMP-024): default maskeli; full xpub
  opt-in `?include_full_address=true` audit'li.

#### Test — Kapsam genişlemesi (FAZ H sonu)

- **192 unit test** (FAZ G öncesi 60'lı seviye; FAZ H ile 192).
- **357 integration test** (FAZ G öncesi 200'lü seviye; FAZ H ile 357).
- **TEST-001 + TEST-020** servis unit test'leri: audit (10), bitcoin (8),
  solana (5), reports (11), evm_tokens (17), simple_rest blockchain (9),
  binance (10), email (8), advisor (19), aggregator/exchange/security/
  stocks_currency/stocks_stale_price/limiter/negative_paths.
- **TEST-011** endpoint testleri: credit_cards (15 + çift sayım regression),
  stocks (8), tefas (8).
- **9 KVKK + auth test** (consent + email change + password reset + lockout).
- **4 migration round-trip test** (alembic upgrade/downgrade subprocess).

---

## [0.1.0] — 2026-05-06 (FAZ B sonu, repo public)

### Added (Faz 1+2+3 MVP özeti)

- Backend FastAPI iskeleti, JWT auth, slowapi rate limiting
- TEFAS, kripto (Binance/iCrypex), 10 blockchain (Bitcoin, Ethereum, Sonic,
  Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin), hisse
  (Yahoo Finance), kıymetli madenler (TCMB + Yahoo), BES manuel
- Manuel kripto modülü (API'siz borsalar — BinanceTR/iCrypex/BTCTurk vs.)
  3 fiyat modu (auto/manual/linked) + asset catalog autocomplete
- Harcama/gelir/bütçe/planlı ödemeler/finansal hedef/recurring income/
  realize akışı
- Kredi kartları (kart + ekstre + taksit nested CRUD; çift sayım kuralı)
- Nakit/banka (manuel; TRY/USD/EUR/GBP TCMB ile TL'ye normalize)
- Yıllık nakit akış projeksiyonu (recharts ComposedChart + xlsx/pdf rapor)
- Snapshot health/usd_try_rate (haftalık snapshot servisi)
- MKK e-Yatırımcı Excel import (xlrd 1.2.0)
- Frontend Next.js 16 dashboard, login, register, 17 alt sayfa
- Docker Compose dev + Kubernetes prod (Oracle Cloud Always Free + K3s)
- 6 GitHub Actions workflow (ci-backend, ci-frontend, e2e, security, sonar,
  release)
- Apache-2.0 LICENSE + SECURITY.md + CONTRIBUTING.md + CODE_OF_CONDUCT.md
- KVKK Aydınlatma Metni + Kullanım Şartları + Gizlilik Politikası +
  Çerez Politikası taslak

---

> **Not:** v0.1.0 öncesi "Faz" başlıkları (Faz 1, 2, 2.5, 3, A, B, C, D, E,
> F, G, H) `docs/01-tasarim-dokumani.md` §7-8'de detaylanır.
> Production v1.0.0 release planı: COMP-001/002/005 kullanıcı aksiyonları
> tamamlandıktan sonra (`gh release create v1.0.0`).
