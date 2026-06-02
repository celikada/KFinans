# KFinans — Sistem Tasarım Dokümanı

**Versiyon:** 4.4
**Tarih:** 2026-06-02
**Durum:** **Production canlı** (`v0.1.0-rc16`, Oracle K3s, `https://kfinans.app`). Faz 1 tamam, Faz 2 tamam (10/10 + 2.5 cleanup); **Faz 3 MVP genişletildi**: harcama takibi + planlı ödemeler + finansal hedef + gelir takibi + bütçe takibi + kıymetli madenler + ayarlar + maliyet bazı + MKK Excel import + modern UI yenileme + **kredi kartları (kart + ekstre + taksit) + nakit/banka + yıllık nakit akış projeksiyonu (xlsx/pdf rapor) + manuel kripto (linked_source) + recurring income realize + snapshot health/usd_try_rate + audit_logs (FAZ C6) + AI tavsiye motoru aktif (advisor.py — AI-003 + AI-008 SPK uyumlu, kredi tüketimli) + 10 zincir blockchain (Bitcoin/Solana/Cardano/Algorand/Polkadot/Litecoin eklendi) + ERC-20 token discovery + MFA TOTP + i18n (TR/EN)** tamamlandı. Faz I güvenlik audit'i (11/11 kritik fix) kapatıldı. **Hâlâ açık (backlog):** kredi sistemi tam implementasyonu (`credit_transactions` tablosu) + iyzico ödeme entegrasyonu, bazı KVKK placeholder metinleri.
**Üretici:** Mayotek

---

## Doküman Yapısı

Bu doküman bir **kapı dokümanı**dır — projenin genel vizyonunu, fazlarını ve detaylı dokümanlara yönlendirmeleri içerir. Her teknik konunun derinlemesine açıklaması ilgili alt dokümandadır.

| Doküman | İçerik | Sahip Ajan |
|---------|--------|------------|
| [mimari.md](./mimari.md) | Sistem mimarisi, modüler monolit yapı, veritabanı şeması, indeks stratejisi | architect + dba |
| [api-referansi.md](./api-referansi.md) | Tüm REST endpoint'leri, request/response örnekleri, hata kodları | backend-expert |
| [frontend.md](./frontend.md) | Next.js App Router yapısı, component sınırları, state, API client | frontend-expert |
| [altyapi-test.md](./altyapi-test.md) | Docker Compose, Kubernetes, CI/CD, test stratejisi ve coverage hedefleri | devops + test-expert |
| [guvenlik.md](./guvenlik.md) | Auth akışı, JWT, Fernet şifreleme, rate limiting, OWASP kontrol listesi | security-expert |
| [uyumluluk-kvkk.md](./uyumluluk-kvkk.md) | KVKK, GDPR, SPK lisans sınırı, gizlilik politikası, kullanıcı hakları | compliance-expert |
| [ai-ve-finans.md](./ai-ve-finans.md) | Claude API entegrasyonu, prompt tasarımı, portföy hesaplama formülleri | ai-expert + finance-expert |
| [kredi-sistemi.md](./kredi-sistemi.md) | Kredi paketleri, iyzico ödeme akışı, kredi tüketim kuralları | architect + finance-expert |

---

## 1. Platform Vizyonu

KFinans, kişisel finansı tek ekranda yöneten **çok kiracılı (multi-tenant) SaaS platformudur**. Hedef pazar: Türkiye bireysel yatırımcısı. Erişim kanalları: web (Next.js) ve mobil (Flutter — Faz 3). Temel takip ücretsiz; AI tavsiye, kripto/blockchain otomatik senkronizasyon ve gelişmiş analiz **kredi sistemi** ile ücretlendirilir.

### 1.1 Üretici ve Marka
- **Üretici Firma:** Mayotek (kurucu: celikada@gmail.com)
- **Ürün:** KFinans
- **Logolar:** `frontend/public/images/kfinans-logo.png`, `mayotek-logo.png`

### 1.2 Faz Planı

| Faz | Kapsam | Durum |
|-----|--------|-------|
| **Faz 1** | Yatırım takibi (TEFAS, kripto, blockchain, hisse senedi), Excel import/export, dashboard | ✅ Tamamlandı |
| **Faz 2** | Kullanıcı kaydı + e-posta doğrulama ✅, scheduler + snapshot servisi ✅, TCMB fallback ✅, BES manuel giriş ✅, JWT blacklist + logout ✅, Kubernetes manifest'leri ✅ | ✅ Tamamlandı (Faz 2.5: test coverage + frontend parçalama) |
| **Faz 3** | Kredi sistemi + iyzico, AI tavsiye motoru aktivasyonu, harcama takibi, çoklu zincir cüzdan desteği (Solana/Cardano/Algorand/Polkadot/Litecoin), ERC-20 token tarama | 🚧 Devam ediyor (harcama/bütçe/emtia/MKK import/Solana/ERC-20 tamam; AI/kredi/iyzico + Cardano/Algorand/Polkadot/Litecoin servisleri açık) |
| **Faz 4** | Flutter mobile app, Play Store yayın, Apple sertifikasyonu | Planlı (web tamamlandıktan sonra) |
| **Faz 5** | MCP Server — Claude Desktop ve diğer MCP istemcilerinden KFinans verilerine erişim (read-only portföy + manuel kayıt ekleme) | Planlı (mobil tamamlandıktan sonra) |

> **Yol haritası kuralı (2026-05-04):** Sıralı ilerleme — web tam stabilize olmadan mobil/MCP'ye dağılma. Tek backend, çoklu istemci stratejisi.

---

## 2. İş Modeli

### 2.1 Kullanıcı Tipleri ve Fiyatlandırma

| Tip | Erişim | Fiyat |
|-----|--------|-------|
| **Ücretsiz** | TEFAS takibi, manuel varlık, temel portföy görünümü, Excel import/export | — |
| **Kredi Paketi** | AI tavsiye, kripto entegrasyonu, blockchain sorgu, gelişmiş analiz | Kredi başına |

### 2.2 Kredi Tüketim Kuralları

| İşlem | Maliyet |
|-------|---------|
| AI portföy tavsiyesi (orta vade) | 5 kredi |
| AI portföy tavsiyesi (uzun vade) | 10 kredi |
| Kripto senkronizasyonu (Binance/iCrypex/BinanceTR) | 1 kredi/çekim |
| Blockchain bakiye sorgusu | 1 kredi/sorgu |
| Gelişmiş harcama analizi (Faz 3) | 3 kredi |

> Detaylı tüketim mantığı, ödeme akışı ve idempotency: [kredi-sistemi.md](./kredi-sistemi.md)

### 2.3 Kredi Paketleri

| Paket | Kredi | Fiyat |
|-------|-------|-------|
| Başlangıç | 50 | 29 ₺ |
| Standart | 150 | 69 ₺ |
| Profesyonel | 500 | 199 ₺ |

Ödeme: **iyzico** (sandbox + production). Stripe çoklu para birimi için Faz 4'te değerlendirilecek.

---

## 3. Teknoloji Yığını

### 3.1 Backend
- Python 3.12 + FastAPI (async-first)
- PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg driver) + Alembic
- APScheduler (4 cron job, Europe/Istanbul): Pazar 23:00 haftalık snapshot, 03:00 revoked_tokens cleanup, 04:00 hard-delete (KVKK), 04:30 audit_logs purge — multi-replica'da `pg_try_advisory_lock` leader election
- Anthropic Python SDK (Claude API tavsiye motoru — aktif, kredi tüketimli)
- CCXT (Binance, iCrypex, BinanceTR), web3.py (Ethereum, Sonic, Avalanche C), httpx (Avalanche P, Bitcoin, Solana, Cardano, Algorand, Litecoin, TEFAS, Yahoo Finance), substrate-interface (Polkadot), bip-utils (xpub HD)
- slowapi (rate limiting), Fernet/MultiFernet (API key + xpub encryption + rotation), bcrypt (şifre hash + TOTP recovery code), python-jose (JWT + refresh rotation), pyotp + qrcode (MFA TOTP), zxcvbn (parola gücü)
- Sentry + OpenTelemetry (opt-in observability)

### 3.2 Frontend
- Next.js 16.2.6 (App Router, Turbopack), React 19, TypeScript (strict mode), Tailwind CSS v4
- `proxy.ts` (Next.js 16 yeni adlandırma — `middleware.ts` deprecated)
- i18n: cookie tabanlı TR/EN dil desteği (`_i18n/I18nProvider`, `useTranslation()`)

### 3.3 Mobile (Faz 4)
- Flutter, http, flutter_secure_storage, riverpod
- Backend API'sini birebir tüketir (REST). Push bildirim + biyometrik auth (FaceID/TouchID) eklenecek
- Hem Android (Play Store) hem iOS (App Store) hedefleniyor

### 3.5 MCP Server (Faz 5)
- Model Context Protocol server — Claude Desktop, Anthropic Workbench, Cursor gibi istemcilerden KFinans verilerine erişim
- Tools (örnek): `get_portfolio`, `get_holdings`, `get_changes`, `add_expense`, `analyze_spending`
- Auth: kullanıcı kendisi için ayrı **MCP API key** üretir (revocable, scope-limited)
- Stack: Python `mcp` SDK, backend ile aynı service katmanını paylaşır (yeni `/mcp/*` endpoint grubu veya ayrı sidecar)
- Use case: "Claude'a 'bu ay portföyüm nasıl performans gösterdi?' diye sor, KFinans gerçek verilerle yanıtlasın"

### 3.4 Altyapı
- Docker + Docker Compose (geliştirme — bilinçli teknik borç)
- Kubernetes / K3s (production canlı — Oracle Cloud Always Free VM, namespace: `kfinans`)
- **CI/CD primary = GitLab CI** (`.gitlab-ci.yml`, self-hosted K8s runner + Kaniko): lint → test → quality (self-hosted SonarQube BLOCKING gate) → build (Docker Hub `celikada/kfinans-*`) → scan (Trivy) → deploy → smoke. `.github/workflows/*` dormant (GitHub hesabı flagged — Actions çalışmaz)
- Kalite: self-hosted SonarQube (`projectKey=KFinans`), SonarCloud DEĞİL
- Helm (bitnami/postgresql), nginx-ingress, cert-manager (Let's Encrypt)

---

## 4. Veri Kaynakları

| Tür | Kaynak | Yöntem |
|-----|--------|--------|
| TEFAS fonu | TEFAS API | httpx + JSON (`fonkod/sonPortfoyDegeri/sonPayAdedi`) |
| Hisse (BIST/ABD/UK) | Yahoo Finance | httpx (`v8/finance/chart/{ticker}`) — auth gerekmez |
| Kripto Spot | Binance, iCrypex | CCXT |
| Kripto TR Earn | Binance TR | session token (cid cookie) — geçici çözüm |
| Manuel kripto (API'siz borsalar) | Kullanıcı girişi | `manual_crypto_holdings`; anlık fiyat Binance USDT + CoinGecko fallback |
| Sonic | EVM (RPC) | web3.py + SFC staking contract (Semaphore(20)) |
| Avalanche P-Chain | Glacier REST → platform.getBalance/getStake | httpx (10 dk cache + single-flight) |
| Avalanche C-Chain | EVM (RPC) | web3.py (multi-RPC fallback) + curated ERC-20 |
| Ethereum | EVM (RPC) | web3.py (multi-RPC fallback) + Ethplorer ERC-20 discovery |
| Bitcoin | mempool.space public API | httpx + bip-utils (xpub HD) + 10 dk cache |
| Solana | JSON-RPC | httpx (`getBalance` + `getProgramAccounts` Stake filter) |
| Cardano / Algorand / Polkadot / Litecoin | Public REST API | httpx / substrate-interface |
| Kıymetli madenler | TCMB + Yahoo Finance | TCMB USD/TRY + XAU=X/XAG=X (GC=F/SI=F fallback) |
| BES | Manuel giriş ✅ (Faz 2) | Kullanıcı plan adı + 4 metric girer; idempotent PUT + Excel import/export |
| Nakit / banka | Manuel giriş ✅ (Faz 3) | `cash_holdings`; TCMB döviz kuruyla TL'ye çevrilir |

> Blockchain entegrasyonlarında **özel anahtar asla sisteme girmez** — yalnızca public adres saklanır.
> Detaylı entegrasyon mantığı: [mimari.md](./mimari.md#7-veri-kaynaklari-ve-servisler)

---

## 5. Mimari Özeti

KFinans **modüler monolit** mimarisi kullanır:
- Tek FastAPI uygulaması (3 Kubernetes Deployment: backend, frontend, postgres)
- Servis ayrımı kod içinde (`api/v1/*`, `services/*`)
- Mikroservise geçişe gerek yok — mevcut ölçek ve trafik için aşırı karmaşıklık

```
İstemci (Web / Mobile)
    │
    ▼ HTTPS / REST
Kubernetes Ingress (nginx)
    │
    ├──► backend Deployment (FastAPI + uvicorn, replicas: 2)
    │         │
    │         ▼
    │    PostgreSQL StatefulSet (bitnami/postgresql)
    │
    └──► frontend Deployment (Next.js standalone, replicas: 2)
```

> Tam mimari, modül sınırları ve veri akışı: [mimari.md](./mimari.md)

---

## 6. Geliştirme Kuralları

- **Doküman dili:** Türkçe (commit mesajları dahil)
- **Kod dili:** İngilizce (identifier, comment, log)
- **Secrets:** Asla koda yazılmaz; `.env` üzerinden `pydantic-settings` ile okunur
- **Migration:** Tüm DB değişiklikleri Alembic üzerinden
- **PR akışı:** `feature/*` → `develop` → `release/*` → `main` (korumalı; GitLab MR primary, sadece squash merge)
- **CI:** GitLab CI (`.gitlab-ci.yml`) — lint + test + SonarQube quality gate geçmeden merge yapılamaz (BLOCKING)

> Git Flow detayları: [altyapi-test.md](./altyapi-test.md#git-flow)

---

## 7. Güncel Durum (2026-06-02)

> **Özet (2026-06-02):** Production **canlı** — `v0.1.0-rc16` Oracle K3s'te, `https://kfinans.app` sağlıklı (`/health` → `{"status":"ok"}`). CI/CD primary GitLab CI'ya taşındı (self-hosted SonarQube BLOCKING gate); GitHub Actions dormant kaldı (hesap flagged). Faz I güvenlik audit'i 11/11 kritik fix ile kapatıldı (MFA TOTP, MultiFernet rotation, DB TLS, NetworkPolicy, SealedSecrets, zxcvbn+HIBP, PII mask, age backup, etcd encryption). Aşağıdaki FAZ A-F notları tarihsel kayıt; GitHub Actions / SonarCloud / "deploy bekliyor" ifadeleri bayat — güncel CI/deploy mimarisi için CLAUDE.md ve `docs/09-altyapi-test.md`'ye bakın.

### ✅ FAZ A — OSS Hijyeni + Public Repo Hazırlığı (2026-05-06)
- Repo public yapıldı (https://github.com/celikada/KFinans)
- Apache-2.0 LICENSE + NOTICE
- SECURITY.md (zafiyet bildirim akışı, TR + EN, 90 gün disclosure)
- CONTRIBUTING.md (branch stratejisi, commit format, test, güvenlik)
- CODE_OF_CONDUCT.md (Contributor Covenant 2.1, TR)
- README.md (Apache rozet, KVKK uyarısı, Geri Bildirim bölümü)
- Dependabot (.github/dependabot.yml) — pip + npm + actions + docker, haftalık
- gitleaks (.gitleaks.toml) — test fixture allowlist; CI'da her PR/push tarama
- .credentials.local.md — lokal dev secret'larının açıklamalı yedeği (gitignore'da)

### ✅ FAZ B — CI/CD Workflow (2026-05-06)
6 workflow:
- **ci-backend.yml**: lint (ruff) + unit + integration + coverage gate (%50)
- **ci-frontend.yml**: ESLint + Vitest + Next.js build
- **e2e.yml**: Playwright (Chromium) — 5 senaryo
- **security.yml**: gitleaks + Trivy fs (HIGH/CRITICAL fail) + pip-audit (osv strict) + npm-audit + CodeQL (Python + JS/TS)
- **sonar.yml**: backend pytest cov XML + frontend vitest LCOV → SonarCloud quality gate (`vars.ENABLE_SONAR='true'` iken aktif; GitHub flag bekleme döneminde skip)
- **release.yml**: semver tag (`v*.*.*`) → 5 job (Sonar QG → matrix Docker buildx & GHCR push → Trivy image scan → Oracle K3s deploy → Playwright @smoke → GitHub Release notes)

Branch protection: `main` PR şart + lineer history + force-push kapalı; `develop` doğrudan push'a izin (force-push kapalı). Sadece squash merge.

### ✅ FAZ C — Production Öncesi Güvenlik Patch'leri (2026-05-06/07)
33 yeni güvenlik testi, 293/293 backend test geçti.

| # | Patch | Detay |
|---|-------|-------|
| C1 | Wallet xpub Fernet şifrelemesi | `address_encrypted` + `address_fingerprint` (SHA-256), `@hybrid_property` transparent encrypt/decrypt; migration `b3c4d5e6f7a8`; 7 test |
| C2 | SecurityHeadersMiddleware | HSTS + X-Frame-Options DENY + X-Content-Type-Options + Referrer-Policy + CSP `default-src 'none'` + Permissions-Policy + COOP + CORP + Server maskeleme; frontend Next.js `headers()` HTML için aynı set |
| C3 | TrustedHostMiddleware | `settings.allowed_hosts` env'den; Host header injection koruması |
| C4 | JWT TTL prod env + Refresh rotation | Prod 30 dk access; `/auth/refresh` her çağrıda eski refresh `jti` blacklist'e atar; **Frontend single-flight refresh akışı + 401 retry** (lib/api.ts) |
| C5 | revoked_tokens cleanup cron | APScheduler her gün 03:00 Europe/Istanbul `expires_at < now` siler |
| C6 | Audit log altyapısı | `audit_logs` tablosu + 8 hook (auth.login/login_failed/logout/register/password_change, wallet.add/delete, integration.add/delete, snapshot.delete, account.soft_delete) + `GET /audit-logs` IDOR korumalı endpoint; migration `c4d5e6f7a8b9`; 9 test |

### ✅ FAZ F — Community Management (2026-05-06)
- 4 issue template (.github/ISSUE_TEMPLATE/): bug_report, feature_request, question, config (blank issues kapalı)
- 27 standart issue label (gh API + PowerShell): tip / öncelik / durum / alan kategorileri
- README.md "Geri Bildirim" bölümü (6 kategori tablosu)
- Frontend `/dashboard/settings` "Geri Bildirim" bölümü (3 kart link: Bug, Feature, Discussion + private vulnerability link)

### 🟡 GitHub Hesap Flag (Ticket #4360519) — çözüm GitLab'a geçişle aşıldı
2026-05-06 yoğun aktivite GitHub anti-spam'i tetikledi (hesap flagged). Çözüm beklenmek yerine **CI/CD ve VCS primary self-hosted GitLab'a taşındı** (`http://gitlab.192.168.3.191.nip.io/root/KFinans`); GitHub yalnızca public mirror. SonarCloud yerine **self-hosted SonarQube** (`projectKey=KFinans`) kullanılıyor. GitHub Actions dormant.

### ✅ Production Deploy (tamamlandı)
- Oracle Cloud Always Free VM + K3s (`141.144.243.54` → `kfinans.app`) + nginx-ingress + cert-manager (Let's Encrypt) canlı
- GitLab CI pipeline: build (Kaniko → Docker Hub `celikada/kfinans-*`) → Trivy image scan → manuel deploy → post-deploy smoke gate
- Güncel production tag: **`v0.1.0-rc16`** (`/health` → `{"status":"ok"}`)
- `kfinans.app` (.app TLD HSTS preload listesinde — tarayıcı zorunlu HTTPS)

### 📚 Sıradaki — Kullanıcı Dokümanları (FAZ E)
Production deploy bittikten sonra:
- `docs/user-guide/` — 10 markdown (kayıt, exchange API key ekleme, cüzdan, TEFAS, MKK Excel import, bütçe, AI tavsiye, KVKK hakları, SSS, troubleshooting)
- Production'dan ekran görüntüleri
- GitHub Wiki sync
- (Opsiyonel) docs.kfinans.app subdomain + MkDocs Material

---

## 8. Eski Durum (arşiv — 2026-04-30 — güncel sayılar §7'de)

> **DOC-008 (FAZ H):** Bu bölüm tarihsel referans için saklanır; test sayıları ve durum kararları **§7 Güncel Durum**'dadır. Aşağıdaki "141 backend test" rakamı 2026-04-30 itibarıyladır; gerçek sayı 290+'a ulaştı (FAZ H'de pytest çıktıları).

### Faz 1+2+3 referansı (2026-04-30)

### ✅ Faz 1 Tamamlandı
- Backend iskeleti, JWT auth, slowapi rate limiting (login 10/dk, register 5/dk, refresh 30/dk), `/health` endpoint
- TEFAS, kripto (Binance/BinanceTR/iCrypex), blockchain (Sonic/Avalanche/Ethereum), hisse (Yahoo Finance)
- Excel import/export tüm varlık türleri için
- Frontend dashboard, login, kripto/wallets/stocks sayfaları
- Docker Compose dev ortamı (Kubernetes port-forward watchdog kaldırıldı)
- CI/CD: 4 ayrı workflow — `ci-backend`, `ci-frontend`, `e2e`, `security`
- 11 domain expert ajanı (`.claude/agents/`) — backend, frontend, dba, devops, security, test, architect, finance, doc, ai, compliance
- 9 odaklı doküman (`docs/`)
- Migration durumu güncel: `users` lifecycle kolonları (email_verified, verify_token, deleted_at, credit_balance), `investment_advice.credits_used`, performans index'leri

### ✅ Faz 2 — Tamamlanan Maddeler (develop'ta)

**1. Stocks (hisse senedi) modülü**
- Backend: `models/stock.py` (StockHolding), migration `c3d4e5f6a7b8`. Mevcut `services/stocks.py` ve `api/v1/stocks.py` artık çalışır durumda (model olmadığı için broken'dı)
- Frontend: `/dashboard/stocks` — Yahoo Finance fiyat preview, Excel import/export
- Endpoint'ler: `GET/PUT /portfolio/stocks/holdings`, `POST /portfolio/stocks/preview`, `GET /portfolio/stocks/export`, `POST /portfolio/stocks/import`

**2. Wallets UI sayfası**
- Frontend: `/dashboard/wallets` — cüzdan ekle/sil/listele, pozisyon tablosu, Excel import/export
- Backend zaten mevcuttu (`api/v1/wallets.py`)

**3. Kullanıcı kayıt + e-posta doğrulama akışı**
- Backend: `RegisterRequest(email, password, risk_profile)`, `verify_token` üretimi (24 saat TTL), Resend SDK ile mail
- Yeni endpoint'ler: `GET /auth/verify-email`, `POST /auth/resend-verification` (her zaman 202 — account enumeration koruması), `POST /auth/login` 403 hard block (email_verified=False)
- Yeni servis: `services/email.py` (Resend SDK + HTML şablon)
- Yeni env: `RESEND_API_KEY`, `EMAIL_FROM`, `FRONTEND_URL`, `VERIFY_TOKEN_EXPIRE_HOURS=24`
- Migration `9a8b7c6d5e4f`: `users.verify_token_expires_at` + `ix_users_verify_token`
- Frontend: `/register`, `/verify-email` (Suspense + useSearchParams), `/login`'e "Kayıt ol" linki
- 14 yeni backend test (`test_auth.py`)

**4. Scheduler + snapshot servisi**
- Yeni servis: `services/snapshot.py::compute_and_save_snapshot()` — tüm kaynakları (Binance, BinanceTR, iCrypex, Sonic, Avalanche P/C, Ethereum, TEFAS, hisse) paralel toplar, TL'ye normalize eder, `portfolio_snapshots` + `asset_positions` yazar
- İdempotent (aynı gün eskiyi siler, yenisi yazılır), hata izolasyonu (bir kaynak fail diğerleri devam)
- USD/TL kritik kur — başarısız olursa snapshot iptal (raise); GBP/USD opsiyonel — başarısız olursa 0 ile devam (UK hisseleri 0 değer + log warning)
- `app/scheduler.py`: `AsyncIOScheduler` (Europe/Istanbul, Pazar 23:00, misfire_grace_time=3600s)
- Yeni endpoint: `POST /portfolio/snapshot` (manuel tetikleme — test/UI için), kur servisleri erişilemezse 503
- Frontend dashboard'da "Snapshot al" butonu
- 4 yeni snapshot integration test

**5. TCMB API USD/TRY (ve GBP/USD) fallback**
- `services/aggregator.py` baştan yazıldı: `TCMB_URL = https://www.tcmb.gov.tr/kurlar/today.xml` (primary)
- Fallback: `https://api.exchangerate-api.com/v4/latest/{USD,GBP}`
- `_fetch_tcmb_rates()` — TCMB XML'i parse eder (`ForexBuying`); `Unit=100` (JPY vb.) tek birime normalize edilir
- `fetch_usd_to_tl()`: TCMB → exchangerate-api → fail ise `RuntimeError`
- `fetch_gbp_to_usd()`: TCMB'den derive (`GBP/TRY ÷ USD/TRY`) → exchangerate-api → fail ise `RuntimeError`
- 5 dakikalık in-memory TCMB cache (aynı snapshot içinde tek HTTP çağrısı)
- `services/snapshot.py`: `asyncio.gather(..., return_exceptions=True)` ile USD/TL kritik (raise), GBP/USD opsiyonel (0 ile devam)
- `POST /portfolio/snapshot` `RuntimeError` → 503
- 9 yeni unit test (`test_exchange_rates.py`) + 2 yeni integration test (kur fail senaryoları)

**6. BES (Bireysel Emeklilik Sistemi) manuel giriş modülü** _(2026-05-02 genişletildi)_
- Backend: `models/bes.py` `BesHolding(id, user_id, plan_name, contract_number?, paid_principal, paid_returns, govt_contribution, govt_returns)` — 4 ayrı metric (yatırılan ana para + getirisi, devlet katkısı + getirisi). Toplam `total_value_tl` model property olarak hesaplanır.
- Migration `1f2e3d4c5b6a` (ilk hal) + `3b4c5d6e7f8a` (4 metric + contract_number genişletme, eski `total_value_tl` kolonu kaldırıldı)
- `User.bes_holdings` ilişkisi (cascade all, delete-orphan)
- `schemas/bes.py`: `BesHolding(plan_name min_length=1 max_length=200, contract_number? max_length=100, 4× Decimal ge=0)`
- Yeni router: `api/v1/bes.py` (prefix `/portfolio/bes`, tag `bes`)
  - `GET /holdings` → liste
  - `PUT /holdings` → idempotent (replace-all)
  - `GET /export` → `bes-holdingleri.xlsx`
  - `POST /import` → Excel'den yükle (mevcut kayıtları değiştirir)
- `services/snapshot.py`: `_gather_bes_assets()` — BES holding'leri tek `AssetData`'ya çevrilir (`asset_type="pension"`, `provider="bes"`, `source_type="bes"`, `liquid_quantity=1`, `unit_price_tl=` 4 metric toplamı); ana paralel toplama dalına `bes_holdings` DB çekimi eklendi
- Frontend: `/dashboard/bes` sayfası (plan adı + toplam ₺ tek satırda iki input, "Plan ekle" + "Kaldır" + "Kaydet" + Excel İndir/Yükle), dashboard kartı pasif "yakında"dan aktif `besTotal`/`besPlanCount` özetli butona dönüştü
- `lib/api.ts`: `getBesHoldings`, `saveBesHoldings`, `exportBesHoldings`, `importBesHoldings` + `BesHoldingDTO`
- 8 yeni API test (`test_bes_api.py`) + 1 IDOR test + 1 snapshot integration test

**7. JWT blacklist + logout endpoint'i**
- Backend: `models/revoked_token.py` — `RevokedToken(jti TEXT PK, user_id, token_type, expires_at, created_at)`. Migration `2a3b4c5d6e7f` — `revoked_tokens` tablosu + `ix_revoked_tokens_expires_at` (cleanup için)
- `core/security.py` — `create_access_token` ve `create_refresh_token` artık her token'a `jti=uuid.uuid4().hex` claim ekler
- `core/deps.py::get_current_user` — decode sonrası jti blacklist kontrolü; eski jti'siz tokenlar geriye dönük uyumlu (jti yoksa atlanır)
- Yeni endpoint: `POST /auth/logout` — `LogoutRequest(refresh_token: str | None)`. Header'daki access ve body'deki refresh (varsa, sub eşleşiyorsa) blacklist'e alınır. PK çakışmasında rollback (idempotent), bozuk refresh sessizce yutulur
- `POST /auth/refresh` güncellendi — refresh token blacklist'teyse 401 "Token iptal edilmiş"
- Schema: `LogoutRequest` `schemas/auth.py`'a eklendi
- Frontend: `lib/api.ts::logout(refreshToken?)` ve `/dashboard/page.tsx` logout butonu (`clearAuth()` öncesi `api.logout()` çağırır)
- Bilinen limitasyon: frontend `localStorage`'da yalnızca access tutuyor; refresh akışı eklendiğinde refresh token da blacklist'e alınmalı
- 8 yeni integration test (`test_logout.py`)

**Test paketi (güncel):**
- **141 backend** + 3 frontend Vitest + 5 Playwright E2E senaryosu
  - Unit: security (22), aggregator (22), exchange_rates (9), GBp dönüşümü (7), TEFAS (6), advisor (6) — toplam 72
  - Integration: auth (21), portfolio (8), IDOR (8), integrations (5), wallets (5), snapshot (7), bes (8), logout (8) — toplam 70
  - E2E: login redirect, register + login akışı (Playwright)
  - Coverage: %52.21 (CI gate %50)

### 🐛 Son Sprint'te Düzeltilen Bug'lar
- **`AssetPositionOut.id` ve `SnapshotOut.id` Pydantic v2 strict UUID rejection** — `str → uuid.UUID` düzeltildi
- **Binance `_sign` paralel istek recvWindow aşımı** — `recvWindow=60000` eklendi
- **Migration cycle düzeltmesi** — `c3d4e5f6a7b8.down_revision = a1b2c3d4e5f6`, `9a8b7c6d5e4f.down_revision = f6a7b8c9d0e1`

### 🐛 Faz 1'de Düzeltilen Bug'lar
- **GBp dönüşüm hatası** — UK hisseleri için GBP/USD kuru zinciri (`api/v1/stocks.py::convert_to_tl`)
- **Duplicate wallet 500 → 409** — `IntegrityError` doğru HTTP koduyla yakalanıyor
- **Pydantic v2 uyumsuzluk** — `class Config` → `model_config` (kısmi)
- **Service katmanı logger eksikliği** — 9 servise module-level `logger` eklendi

### ✅ Faz 2 — Kalan Öncelikler (Tamamlandı)
- [x] Kullanıcı kayıt frontend sayfası + e-posta doğrulama akışı (Resend)
- [x] Haftalık snapshot servisi + scheduler implementasyonu
- [x] Stocks ve Wallets UI sayfaları
- [x] TCMB API USD/TRY fallback (TCMB primary + exchangerate-api fallback, 5 dk in-memory cache)
- [x] BES manuel giriş ekranı (model + endpoint'ler + Excel + snapshot entegrasyonu + frontend)
- [x] JWT blacklist + `/auth/logout` endpoint'i (revoked_tokens tablosu + jti claim + refresh blacklist kontrolü)
- [x] KVKK metinleri (KVKK aydınlatma, gizlilik, kullanım şartları, çerez — `/legal/*` sayfaları + register'da 3 ayrı onay; placeholder'lar kullanıcı tarafından doldurulacak)
- [x] Kubernetes manifest'leri (`k8s/` klasörü — namespace, configmap, postgres StatefulSet, backend/frontend Deployment, nginx-ingress + cert-manager, kustomization, kapsamlı README; tek komut: `kubectl apply -k k8s/`)

### 🔄 Faz 2.5 — Cleanup (Faz 3 öncesi)
- [ ] Şifre sıfırlama akışı (`/auth/forgot-password`, `/auth/reset-password`)
- [ ] Binance TR Earn endpoint'i için Resmi API yanıtı bekleniyor — geçici çözüm `encrypted_extra` ile cookie token `feature/binancetr-session-token` branch'inde
- [x] Test coverage %30 → %50 hedefi (2026-05-02: %52.21 — `services/advisor.py` 6 unit test ile %0 → ~%85; orphan `services/bes.py` silindi; CI gate %50)
- [ ] Frontend bileşen parçalama + Vitest/RTL component test'leri

### 📋 Faz 3 — Durum

**MVP tamamlanan:**
- [x] **Harcama takibi (manuel)** — `expenses` tablosu (migration `4c5d6e7f8a9b`), 5 endpoint (`GET/POST/PUT/DELETE /expenses` + `GET /expenses/summary`), 10 sabit kategori (`Literal`), `/dashboard/expenses` sayfası (4 component pattern: ExpenseForm + ExpenseTable + CategoryPieChart + MonthSelector), dashboard 6. kart "Harcamalar (bu ay)" (kırmızı tema, top 3 kategori). 18 yeni integration test (`test_expenses_api.py`) — IDOR + auth + filter + summary. **Excel import/export eklendi** (`GET /expenses/export`, `POST /expenses/import`).
- [x] **Planlı Ödemeler & Nakit Akışı Tahmini** — `planned_expenses` tablosu (migration `5d6e7f8a9b0c`), 7 kategori, 6 tekrar tipi, 5 endpoint + tahmin motoru, `/dashboard/planned` yıllık timeline görünümü, dashboard kartı. 16 yeni integration test.
- [x] **Finansal Hedef ve Özgürlük Takibi** — `users.goal_amount` + `users.goal_currency` (migration `6e7f8a9b0c1d` + `7f8a9b0c1d2e`). USD/EUR/GBP/TRY desteği ile pasif gelir hedefi takip ediliyor; `/dashboard/goal` sayfası + dashboard kartı (yüzde göstergesi).
- [x] **Gelir Takibi (manuel)** — `incomes` tablosu (migration `8a9b0c1d2e3f`), 7 kategori (maaş, serbest meslek, kira, temettü, ikramiye, varlık satışı, diğer), CRUD + summary + Excel import/export, `/dashboard/income` sayfası + dashboard kartı.
- [x] **Bütçe vs. Gerçekleşen** — `budgets` tablosu (migration `9b0c1d2e3f4a`, `(user_id, category)` UNIQUE), kategori bazlı aylık bütçe upsert; `GET /budgets`, `PUT /budgets/{category}`, `DELETE /budgets/{category}`, `GET /budgets/comparison?year=&month=`. `/dashboard/budget` sayfası (BudgetForm + ComparisonTable) + dashboard kartı (aşılan bütçe sayısı).
- [x] **Kıymetli Maden (altın/gümüş) Modülü** — `commodity_holdings` tablosu (migration `a0b1c2d3e4f5`). 3 birim tipi (gram, BiGA, sikke), 15 BiGA kodu (A01-A08 altın, G01-G07 gümüş), 6 sikke türü. `services/commodity.py` Yahoo Finance Chart API (XAU=X/XAG=X primary, GC=F/SI=F fallback) + 5 dk in-memory cache. `/portfolio/commodities` 6 endpoint (CRUD + Excel import/export). `/dashboard/commodities` sayfası + dashboard kartı + UI fault-tolerance uyarı bandı.
- [x] **Maliyet Bazı (avg_cost_tl) ve Distributor (kurum) Alanları** — TEFAS + Stocks holding'lerine `avg_cost_tl` (migration `b1c2d3e4f5a6`) ve `distributor` (migration `c2d3e4f5a6b7`) eklendi. Preview/list response'larında kâr/zarar (₺ + %) hesaplanıyor; aynı kodun farklı kurumlardan (örn. ZJI fonu Ziraat + Foneria) ayrı satır olarak izlenebilmesi sağlandı.
- [x] **MKK e-Yatırımcı Excel Import** — `xlrd==1.2.0` ile MKK "Tüm Kıymetler" .xls binary dosyası direkt parse ediliyor. `POST /portfolio/tefas/import-mkk` (Kıymet Sınıfı=Fon filtresi) + `POST /portfolio/stocks/import-mkk` (Kıymet Sınıfı=HS + Ek Tanım=A filtresi, BIST kodları `.IS` suffix ile Yahoo Finance ticker'ına çevrilir). MKK distributor (Üye sütunu) otomatik dolduruluyor. Import sonrası `compute_and_save_snapshot` otomatik tetikleniyor (best-effort, fail olsa bile import korunur). UI: paylaşılan `MkkHint` bileşeni + doğrudan upload butonu.
- [x] **Kullanıcı Hesap Yönetimi & Ayarlar** — `GET /user/me`, `PUT /user/profile` (risk profili), `PUT /user/password` (mevcut şifre doğrulamalı), `DELETE /user/me` (soft-delete, `users.deleted_at` set). `/dashboard/settings` sayfası 5 bölüm: hesap özeti, risk profili, şifre değiştir, dashboard kart gizleme (localStorage `kfinans_hidden_cards`), hesap silme.
- [x] **Modern UI Yenileme** — Emoji ikonlar inline SVG'lere dönüştürüldü; KFinans + Mayotek logoları SVG bileşenleri (`Logos.tsx`); 11 dashboard kartı `DASHBOARD_CARDS` üzerinden render ediliyor; container `max-w-5xl`, satırlar `flex-wrap` ile mobile uyumlu; Stocks + TEFAS form bileşenleri yeniden düzenlendi.

**Tamamlanan (2026-05/06 turlarında — eskiden "açık kalan"):**
- [x] AI tavsiye motoru aktivasyonu (`/advice/generate` — kredi tüketimli, SPK uyumlu disclaimer; AI-003 + AI-008)
- [x] KVKK endpoint'leri: `/user/me` DELETE soft-delete + hard-delete cron (04:00, COMP-004) + audit_logs purge cron (04:30, COMP-022) + veri dışa aktarımı
- [x] `audit_logs` tablosu (FAZ C6) — 8 kritik eyleme hook + IDOR korumalı `GET /audit-logs`
- [x] Redis cache desteği — `settings.redis_url` set ise slowapi rate limit multi-replica güvenli
- [x] **Bitcoin xpub Fernet şifreleme** (FAZ C1) — `address_encrypted` + `address_fingerprint`, migration `b3c4d5e6f7a8`
- [x] Snapshot sağlık uyarıları (`portfolio_snapshots.health_issues` JSONB) + çift para birimi (`usd_try_rate`) + History TL/USD toggle (migration `e4f5a6b7c8d9`)

**Hâlâ açık (backlog — bkz. `docs/audits/2026-05-22-master-audit.md`):**
- [ ] Harcama AI analizi (`/expenses/analysis/generate` — 3 kredi)
- [ ] Kredi sistemi tam implementasyonu + iyzico sandbox (`credit_transactions` tablosu, idempotency, webhook) — kodda henüz YOK
- [ ] Background job kuyruğu (Celery/RQ)
- [ ] Bazı KVKK yasal metin placeholder'ları (ticari ünvan, KEP, tebligat adresi)
  - Amaç: TL eğimi enflasyonlu, USD eğimi gerçek satın alma gücü değişimini gösterir

---

### Faz 3 #2 — Planlı Ödemeler & Yıllık Nakit Akışı Tahmini (2026-05-03)

#### Backend

**Model:** `PlannedExpense` — `models/planned_expense.py`
- Migration: `5d6e7f8a9b0c`
- Kategoriler (7): `loan`, `tax`, `insurance`, `subscription`, `rent`, `utility`, `other`
- Tekrar tipleri (6): `one_time`, `monthly`, `quarterly`, `biannual`, `yearly`, `custom`
- Alanlar:
  - `title` — ödeme başlığı
  - `amount NUMERIC(18, 2)` — tutar
  - `is_estimated BOOLEAN` — tahmini tutar bayrağı
  - `category` — yukarıdaki 7 kategoriden biri (`Literal`)
  - `recurrence` — yukarıdaki 6 tekrar tipinden biri (`Literal`)
  - `months INTEGER[]` — custom recurrence için hangi aylar (1-12 dizisi)
  - `day_of_month INTEGER` — ayın hangi günü (1-31)
  - `start_date DATE` — geçerlilik başlangıcı
  - `end_date DATE` — geçerlilik sonu (opsiyonel)
  - `remaining_count INTEGER` — aylık kredi için kalan taksit; otomatik olarak `end_date`'e çevrilir
  - `notes VARCHAR(500)` — serbest not (opsiyonel)

**Endpoint'ler:**
- `GET /planned-expenses` — kullanıcının planlı ödemeleri
- `POST /planned-expenses` — yeni planlı ödeme ekle
- `PUT /planned-expenses/{id}` — güncelle
- `DELETE /planned-expenses/{id}` — sil
- `GET /planned-expenses/forecast?year=` — tahmin motoru: 12 aylık breakdown + yıl toplamı

**Tahmin motoru:** `_applies_in_month(expense, year, month)` fonksiyonu her planlı ödemenin belirtilen ay için geçerli olup olmadığını (`start_date`, `end_date`, `recurrence`, `months` alanları değerlendirilerek) belirler; 12 ay için çağrılır ve yıllık nakit akışı breakdown'ını döndürür.

**Test:** 16 yeni integration test

#### Frontend

- **Sayfa:** `/dashboard/planned` — yıllık timeline görünümü, bar chart stili (`YearlyForecast` component)
- **Component'ler (3):**
  - `PlannedForm` — planlı ödeme ekle/düzenle formu (kategori, tekrar tipi, tutar, tarih aralığı)
  - `PlannedList` — mevcut planlı ödemeleri listele/sil
  - `YearlyForecast` — 12 aylık bar chart stili nakit akışı tahmini
- **Dashboard 7. kart:** "Planlı Ödemeler (bu yıl)" — violet tema
- **`lib/api.ts` eklemeleri:**
  - 5 metot: `getPlannedExpenses`, `createPlannedExpense`, `updatePlannedExpense`, `deletePlannedExpense`, `getPlannedForecast`
  - DTO'lar: `PlannedExpenseDTO`, `PlannedExpenseCreateDTO`, `PlannedForecastDTO`
  - Sabitler: `PLANNED_CATEGORY_LABELS`, `PLANNED_RECURRENCE_LABELS`, `MONTH_NAMES`

---

### Faz 3 #3 — Finansal Hedef, Gelir Takibi, Bütçe, Kıymetli Madenler ve UI Yenileme (2026-05-03)

#### Finansal Hedef ve Pasif Gelir Takibi
- **Migration `6e7f8a9b0c1d`** + **`7f8a9b0c1d2e`**: `users.monthly_expense_goal` eklendi, sonra `users.goal_amount` (NUMERIC 18,2) + `users.goal_currency` (VARCHAR 3, default `TRY`) lehine değiştirildi. USD/EUR/GBP/TRY 4 para birimi destekleniyor.
- Endpoint: `GET /goals/me`, `PUT /goals/me` (yalnızca giriş yapmış kullanıcı; risk profili mantığı ile aynı pattern).
- Frontend: `/dashboard/goal` sayfası (hedef tutar + para birimi + ilerleme barı), dashboard kartı pasif gelir yüzdesi gösterir.

#### Gelir Takibi
- **Migration `8a9b0c1d2e3f`**: `incomes` tablosu (id, user_id, amount, category, date, description?, created_at) + `ix_incomes_user_date` (user_id + date) — Expense'le birebir paralel şema.
- 7 kategori (`Literal`): salary, freelance, rental, dividend, bonus, sale, other (Türkçe etiketler `INCOME_CATEGORY_LABELS`).
- Endpoint'ler: `GET /income`, `POST /income`, `PUT /income/{id}`, `DELETE /income/{id}`, `GET /income/summary?year=&month=`, `GET /income/export`, `POST /income/import`.
- Excel import Türkçe label haritası içerir (`maaş` → `salary` vb.).
- Frontend: `/dashboard/income` sayfası (4 component pattern + ay seçici + pasta grafiği) + dashboard kartı.

#### Bütçe vs. Gerçekleşen
- **Migration `9b0c1d2e3f4a`**: `budgets` tablosu (id, user_id, category, amount, updated_at) + `uq_budget_user_category` UNIQUE constraint. Kategori seti `Expense` ile aynı (10 sabit kategori).
- Endpoint'ler:
  - `GET /budgets` — kullanıcının tanımlı bütçeleri (kategori sıralı)
  - `PUT /budgets/{category}` — UPSERT (PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`)
  - `DELETE /budgets/{category}` — bütçe sil
  - `GET /budgets/comparison?year=&month=` — kategori bazlı bütçe vs. gerçekleşen (kalan tutar + yüzde + over_budget flag)
- Frontend: `/dashboard/budget` (BudgetForm + ComparisonTable) + dashboard kartı (aşılan bütçe sayısı sayacı).

#### Kıymetli Madenler (Altın & Gümüş)
- **Migration `a0b1c2d3e4f5`**: `commodity_holdings` tablosu (id, user_id, unit_type, metal, biga_code?, coin_type?, quantity, notes?, created_at) + `ix_commodity_holdings_user_id`.
  - `unit_type`: `gram` | `biga` | `coin`
  - `metal`: `gold` | `silver` (sikke için her zaman `gold`)
  - `biga_code`: A01-A08 (altın 1g→1kg) veya G01-G07 (gümüş 1g→1kg)
  - `coin_type`: ceyrek (1.7517g), yarim (3.5033g), tam (7.0166g), cumhuriyet/resat/ata (7.2164g)
- Servis: `services/commodity.py`
  - `fetch_metal_prices()` — TCMB USD/TRY (kritik) + Yahoo Finance XAU=X→GC=F + XAG=X→SI=F fallback chain
  - 5 dakikalık in-memory cache; Yahoo fail durumunda TTL 30 saniyeye düşer (geçici 404 hızla telafi edilir)
  - Metal fiyatları **best-effort** — Yahoo başarısızlığı 0 döner, UI uyarı banner gösterir
- Endpoint'ler:
  - `GET /portfolio/commodities` — pozisyonlar + anlık fiyatlar + summary
  - `POST /portfolio/commodities` — yeni varlık (model_validator ile unit_type/metal/biga/coin uyumu zorlanır)
  - `PUT /portfolio/commodities/{id}` — quantity + notes güncelle
  - `DELETE /portfolio/commodities/{id}`
  - `GET /portfolio/commodities/export` — Excel
  - `POST /portfolio/commodities/import` — Excel'den **append** (mevcut kayıtlar silinmez)
- Frontend: `/dashboard/commodities` (CommodityForm + CommodityList) + dashboard kartı + UI fiyat fault-tolerance uyarı bandı.

#### Maliyet Bazı (avg_cost_tl)
- **Migration `b1c2d3e4f5a6`**: `tefas_holdings.avg_cost_tl` + `stock_holdings.avg_cost_tl` (Numeric 18,6 nullable) — TRY/adet ortalama maliyet.
- Schema validator: 0 veya negatif değer girilince `None`'a çevrilir (kullanıcı bilmiyorsa boş bırakabilir).
- Preview/list response: `cost_basis_tl`, `gain_loss_tl`, `gain_loss_pct` hesaplanır (avg_cost girilmemişse hepsi `None`).
- Excel export şablonuna "Ort. Maliyet (₺)" + "Kâr/Zarar (₺)" sütunları eklendi.
- UI: TEFAS + Stocks sayfaları formuna "Ort. maliyet ₺" inputu + tabloda yeşil/kırmızı renklendirilmiş kâr/zarar sütunu.

#### Distributor (Aracı Kurum) Alanı
- **Migration `c2d3e4f5a6b7`**: `tefas_holdings.distributor` + `stock_holdings.distributor` (VARCHAR 50 nullable).
- **Use case:** Aynı varlığı (örn. TEFAS ZJI fonu) farklı kurumlardan (Ziraat + Foneria) ayrı satır olarak izleme.
- UI: Form'a "Kurum" inputu + tabloda mavi pill badge.

#### MKK e-Yatırımcı Excel Import
- **Yeni bağımlılık:** `xlrd==1.2.0` (eski .xls binary parse — 2.0+ sürümleri xlsx desteğini kaldırdı; MKK eski Excel dosyaları için 1.2.0 zorunlu).
- Endpoint'ler:
  - `POST /portfolio/tefas/import-mkk` — `Kıymet Sınıfı = Fon` filtresi, fon kodu + adı + adet + fiyat (avg_cost_tl) + üye (distributor)
  - `POST /portfolio/stocks/import-mkk` — `Kıymet Sınıfı = HS` AND `Ek Tanım = A` filtresi (aktif tradeable pozisyonlar), BIST kodları otomatik `.IS` suffix ile Yahoo Finance ticker formatına çevrilir
- Header satırı "Üye" sütunundan otomatik tespit edilir (ilk 20 satır taranır).
- Import sonrası `compute_and_save_snapshot()` **best-effort** olarak tetiklenir — fail olsa bile import korunur (`try/except` + log warning).
- Frontend: paylaşılan `MkkHint` bileşeni + opsiyonel `onUpload` prop ile doğrudan upload butonu (Stocks + TEFAS sayfalarında).

#### Kullanıcı Hesap Yönetimi & Ayarlar
- Yeni router: `api/v1/user.py` (prefix `/user`, tag `user`)
  - `GET /user/me` — `UserMeOut` (email, risk_profile, email_verified, credit_balance, created_at)
  - `PUT /user/profile` — risk profili güncelle (Literal validation)
  - `PUT /user/password` — mevcut şifre doğrulamalı (`verify_password` → 400 "Mevcut şifre hatalı"); yeni şifre `min_length=8`
  - `DELETE /user/me` — soft-delete (`users.deleted_at = now()`)
- Frontend: `/dashboard/settings` (5 bölüm: hesap özeti, risk profili, şifre, dashboard kart gizleme, hesap silme).
- **Dashboard kart gizleme:** `localStorage.kfinans_hidden_cards` (JSON array of `DashboardCardId`); 11 kart `DASHBOARD_CARDS` üzerinden render ediliyor.

#### Modern UI Yenileme
- Emoji ikonlar inline SVG'lere dönüştürüldü (kart başlıklarında).
- Logo bileşenleri: `frontend/app/_components/Logos.tsx` — `KFinansLogo size={"sm"|"md"|"lg"|"xl"}` + `MayotekLogo`. PNG dosyaları (`public/images/kfinans-logo.png`, `mayotek-logo.png`) hâlâ erişilebilir ama UI artık SVG bileşenleri kullanıyor.
- Container `max-w-5xl`, formlar `flex-wrap` ile mobile uyumlu.
- Paylaşılan `_components/`: `Logos.tsx`, `MkkHint.tsx`, `PageHeader.tsx`.
- Excel import (Expenses + Income) için Türkçe label → İngilizce key haritası eklendi.

> Detaylı yol haritası ve TODO'lar her alt dokümanın sonundadır.
