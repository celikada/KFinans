# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje Hakkında

KFinans, kişisel yatırım portföyünü tek ekranda toplayan bir uygulamadır. Binance ve iCrypex kripto hesapları, TEFAS yatırım fonları, hisse senedi (Yahoo Finance), kıymetli madenler (altın/gümüş), BES birikimleri ve **10 zincir blockchain cüzdanları** (Bitcoin, Ethereum, Sonic, Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin) tek ekranda toplanır. Manuel harcama, gelir, planlı ödeme ve bütçe takibi modülleri Faz 3 ile eklendi. Haftalık snapshot servisi değişimleri hesaplar; Claude API aracılığıyla orta/uzun vadeli yatırım tavsiyeleri (Faz 3) sunulacaktır.

## Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend API | Python 3.12 + FastAPI |
| Exchange entegrasyonu | CCXT (Binance, iCrypex) |
| Blockchain — EVM | web3.py (Ethereum, Sonic SFC, Avalanche C-Chain) — multi-RPC fallback (publicnode, merkle, 1rpc, ankr, drpc) |
| Avalanche P-Chain | httpx + Glacier (Routescan) REST API → JSON-RPC fallback (10 dk cache + single-flight) |
| Bitcoin | httpx + mempool.space public API (no key) + bip-utils (xpub HD derivation) — 10 dk in-memory cache + single-flight pattern |
| Solana | httpx + `api.mainnet-beta.solana.com` JSON-RPC (`getBalance` + `getProgramAccounts` Stake program filter) |
| Cardano / Algorand / Polkadot / Litecoin | Public REST API'ler (Faz A taraması) |
| ERC-20 token discovery | Ethplorer free API (`api.ethplorer.io`, key='freekey'); Avalanche için curated list (sAVAX, USDT.e, USDC.e) |
| TEFAS | httpx + JSON API |
| Hisse senedi | Yahoo Finance Chart API (httpx) |
| Kıymetli madenler | TCMB USD/TRY + Yahoo Finance XAU=X / XAG=X (GC=F / SI=F fallback) |
| MKK Excel import | xlrd 1.2.0 (eski .xls binary) |
| BES | Manuel giriş + Excel |
| Zamanlayıcı | APScheduler |
| Veritabanı | PostgreSQL + SQLAlchemy (async) + Alembic |
| AI tavsiye | Anthropic Python SDK (Claude API) |
| Frontend | Next.js 16 (App Router, Turbopack) + React 19 + Tailwind CSS v4 |
| Auth | JWT (python-jose) + slowapi rate limiting + refresh token rotation |
| Güvenlik | Fernet (API key + wallet xpub) + bcrypt (şifre) + JWT blacklist (revoked_tokens) + SecurityHeadersMiddleware (HSTS, CSP, X-Frame, COOP) + TrustedHostMiddleware + audit_logs |
| CI/CD | GitHub Actions (5 workflow): ci-backend, ci-frontend, e2e, security (gitleaks+Trivy+pip-audit+npm-audit+CodeQL), sonar; release (semver tag → GHCR build → Trivy → Oracle K3s deploy → smoke) |
| Hosting | Oracle Cloud Always Free VM + K3s (`141.144.243.54` → `kfinans.app`) + nginx-ingress + cert-manager (Let's Encrypt) |
| Domain | `kfinans.app` (Namecheap, .app TLD HSTS preload listesinde — tarayıcı zorunlu HTTPS) |

## Proje Yapısı

```
KFinans/
├── backend/
│   ├── app/
│   │   ├── api/v1/                # FastAPI 21 router'ı: auth, user, portfolio, tefas,
│   │   │                          # stocks, bes, commodity, wallets, integrations,
│   │   │                          # expenses, planned_expenses, income, budget, goal,
│   │   │                          # cash, cash_flow, credit_cards, manual_crypto,
│   │   │                          # asset_catalog, audit_logs, advice
│   │   ├── services/
│   │   │   ├── exchange/          # CCXT tabanlı (Binance, iCrypex, BinanceTR)
│   │   │   ├── blockchain/        # Sonic SFC, Avalanche P/C (getBalance + getStake),
│   │   │   │                      # Ethereum (web3.py multi-RPC), Bitcoin (mempool.space + cache),
│   │   │   │                      # Solana (JSON-RPC), evm_tokens.py (ERC-20 discovery — Ethplorer + curated list + spam filter)
│   │   │   ├── tefas.py
│   │   │   ├── stocks.py
│   │   │   ├── commodity.py       # TCMB + Yahoo XAU/XAG fallback chain + 5 dk cache
│   │   │   ├── aggregator.py      # TL normalize, USD/TRY, breakdown
│   │   │   ├── snapshot.py        # compute_and_save_snapshot() — paralel toplama (manuel kripto dahil)
│   │   │   ├── email.py           # Resend SDK — verify_email
│   │   │   ├── audit.py           # FAZ C6: log_audit() + AuditAction Enum (best-effort)
│   │   │   └── advisor.py         # Claude API (Faz 3'te aktive olacak)
│   │   ├── models/                # SQLAlchemy ORM (audit_log.py dahil)
│   │   ├── schemas/               # Pydantic (manual_crypto.py dahil)
│   │   ├── core/                  # security (fernet+jwt+bcrypt+address_fingerprint), deps, limiter, middleware (SecurityHeadersMiddleware)
│   │   ├── scheduler.py           # APScheduler — Pazar 23:00 snapshot + günlük 03:00 revoked_tokens cleanup
│   │   └── main.py                # SecurityHeaders + TrustedHost + CORS middleware sırası
│   ├── alembic/versions/          # 31 migration. Faz 3 ana ekleme'ler:
│   │                              # - e0f1a2b3c4d5: credit_cards
│   │                              # - f1a2b3c4d5e6: credit_card_statements + installments
│   │                              # - f5a6b7c8d9e0: manual_crypto_holdings
│   │                              # - a6b7c8d9e0f1: manual_crypto.price_source enum
│   │                              # - b7c8d9e0f1a2: manual_crypto.linked_source
│   │                              # - c8d9e0f1a2b3: recurring_incomes
│   │                              # - d3e4f5a6b7c8: cash_holdings
│   │                              # - d9e0f1a2b3c4: incomes.recurring_income_id FK
│   │                              # - e4f5a6b7c8d9: snapshot health_issues + usd_try_rate
│   │                              # - b3c4d5e6f7a8: wallet xpub Fernet (FAZ C1)
│   │                              # - c4d5e6f7a8b9: audit_logs (FAZ C6)
│   ├── tests/{unit,integration}/  # 293 test (FAZ C: +33 test — xpub encrypt, security headers, refresh rotation, cleanup, audit log)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/                      # Next.js 16 (App Router, proxy.ts auth yönlendirme)
│   ├── app/_components/{Logos,MkkHint,PageHeader}.tsx
│   ├── app/dashboard/{tefas,stocks,wallets,crypto,manual-crypto,bes,expenses,planned,
│   │                  income,budget,commodities,goal,settings,history,
│   │                  cash,cash-flow,credit-cards}/  # 17 alt sayfa
│   ├── next.config.ts             # FAZ C2: async headers() — HSTS, CSP, X-Frame, Permissions-Policy
│   └── lib/{api,format}.ts
├── docs/                          # 9 sıralı belge (01-tasarim ... 09-altyapi-test)
├── .github/
│   ├── workflows/                 # 5 workflow: ci-backend, ci-frontend, e2e, security, sonar, release
│   ├── dependabot.yml             # FAZ A4: pip + npm + actions + docker, haftalık
│   └── pull_request_template.md   # FAZ A6: güvenlik checklist genişletilmiş
├── .gitleaks.toml                 # FAZ A1: test fixture allowlist
├── .credentials.local.md          # gitignore'da: lokal dev secret yedek + açıklama
├── sonar-project.properties       # FAZ B2: SonarCloud config (celikada_KFinans)
├── LICENSE                        # Apache-2.0 (Mayotek 2026)
├── SECURITY.md                    # zafiyet bildirim akışı (TR + EN, 90 gün disclosure)
├── CONTRIBUTING.md                # branch stratejisi + commit format + güvenlik
├── CODE_OF_CONDUCT.md             # Contributor Covenant 2.1 (TR)
└── k8s/                           # Production manifest'leri (kustomize)
```

## Build & Çalıştırma Komutları

```bash
# Backend bağımlılıklarını kur
cd backend && pip install -e ".[dev]"

# DB migration uygula
alembic upgrade head

# Geliştirme sunucusu
uvicorn app.main:app --reload

# Testler
pytest
pytest tests/services/test_binance.py   # tek test dosyası
pytest -k "test_aggregator"             # isimle filtre

# Lint & format
ruff check .
ruff format .

# Frontend
cd frontend && npm install && npm run dev
```

## Mimari Kararlar

**Veri akışı:** Her servis kendi kaynağından ham veriyi çeker → `aggregator.py` TL'ye normalize eder (kripto için anlık kur) → haftalık snapshot PostgreSQL'e yazılır → `advisor.py` bu snapshot'ı Claude API'ye gönderir.

**Scheduler (4 cron job, Europe/Istanbul):**
- Pazar 23:00 — haftalık portföy snapshot (`_weekly_snapshot_job`); ARC-003 ile `asyncio.gather + Semaphore(5)` paralel; ARC-011 ile `pg_try_advisory_lock` multi-replica leader election (yalnızca tek pod yürütür).
- Her gün 03:00 — `revoked_tokens` cleanup (FAZ C5).
- Her gün 04:00 — `_hard_delete_expired_users_job` 30 gün geçmiş soft-delete'leri fiziksel siler (COMP-004, KVKK m.7).
- Her gün 04:30 — `_purge_old_audit_logs_job` 365 gün'den eski audit_logs siler (COMP-022, KVKK m.7).

`SCHEDULER_ENABLED=false` env ile scheduler tamamen kapatılabilir (multi-replica deploy'da sadece 1 leader pod). MKK Excel import sonrası snapshot best-effort olarak ayrıca tetiklenir.

**Snapshot timezone:** `services/snapshot.py` `snapshot_date` belirlerken `datetime.now(ZoneInfo("Europe/Istanbul")).date()` kullanır (UTC tabanlı `date.today()` değil). Backend Docker container UTC'de çalıştığı için Türkiye saatine göre 00:00–03:00 arası alınan ad-hoc snapshot'lar bir önceki güne yazılıyordu — düzeltildi. Scheduler zaten `Europe/Istanbul` ile çalışıyordu; manuel tetikleme ile tutarlı.

**Snapshot silme:** `DELETE /portfolio/snapshot/{snapshot_date}` (ISO date path param) yanlış kaydedilmiş snapshot'ları temizler; cascade ile `asset_positions` de silinir, `current_user.id` filtresi IDOR koruması sağlar.

**Wallet pricing tutarlılığı:** `GET /portfolio/wallets` `total_value_tl` hesaplarken `liquid + staked + pending_rewards` toplar (snapshot servisiyle aynı formül). Sonic SFC validator rewards ve Avalanche P-Chain pending rewards her zaman dahildir; dashboard "Toplam Portföy" ile snapshot tutarı arasında fark oluşmaz.

**API key güvenliği:** Binance/iCrypex anahtarları DB'de `cryptography` kütüphanesi ile Fernet şifrelemeli saklanır, `.env`'deki master key ile açılır.

**Wallet adresi (xpub) Fernet şifrelemesi (FAZ C1):** `wallet_addresses.address` artık plaintext değil. `address_encrypted` (Fernet ciphertext) + `address_fingerprint` (SHA-256 hex of lowercase address) iki kolon. `WalletAddress.address` Python `@hybrid_property` — getter decrypt eder, setter encrypt + fingerprint hesaplar. Service ve API kodu hiç değişmedi (`wallet.address` transparent çalışır). Unique constraint `(user_id, chain, address_fingerprint)` — case-insensitive (EVM checksum varyasyonları aynı sayılır). Migration `b3c4d5e6f7a8`. Sebep: BIP-32 xpub'tan tüm child pub key'ler türetilebilir; DB sızıntısında saldırgan BTC bakiye geçmişini izleyebilirdi.

**SecurityHeadersMiddleware + TrustedHostMiddleware (FAZ C2/C3):** `app/core/middleware.py::SecurityHeadersMiddleware` her response'a HSTS (1 yıl + preload) + X-Frame-Options DENY + X-Content-Type-Options + Referrer-Policy + CSP (`default-src 'none'`) + Permissions-Policy + COOP + CORP + Server maskeleme ekler. `TrustedHostMiddleware` `settings.allowed_hosts` env'den (prod: `["kfinans.app","www.kfinans.app","api.kfinans.app"]`). **Middleware sırası kritik (LIFO):** SecurityHeaders en başta add → response zincirinin en sonunda; TrustedHost orta; CORS en son add → request zincirinin en başta (preflight OPTIONS'ları yakalar). Frontend `next.config.ts` async `headers()` HTML response'lar için aynı header'ları + CSP'ye script-src 'unsafe-inline' (Next.js inline runtime).

**JWT Refresh Token Rotation (FAZ C4):** `/auth/refresh` her çağrıda eski refresh token'ın `jti`'sini `revoked_tokens` blacklist'ine atar + yeni refresh üretir. Sızan refresh ikinci kez kullanılamaz (saldırgan ya da gerçek kullanıcı — kim önce kullandıysa o kazanır, diğeri 401 alır). `IntegrityError` paralel istek senaryosunda rollback ile idempotent. Access token TTL prod'da 30 dk (`ACCESS_TOKEN_EXPIRE_MINUTES=30` env), dev'de 480 dk default.

**revoked_tokens cleanup cron (FAZ C5):** APScheduler her gün 03:00 Europe/Istanbul `_cleanup_revoked_tokens_job` çağırır — `expires_at < now` kayıtlar silinir. `session_factory` parametresi enjekte edilebilir (test'te `TestSession`, prod'da `AsyncSessionLocal`).

**Audit Log altyapısı (FAZ C6):** `audit_logs` tablosu (id, user_id ON DELETE SET NULL, action VARCHAR(64), resource VARCHAR(128), ip_address, user_agent, extra JSONB, created_at). 8 kritik eyleme hook'lanmış: `auth.login`, `auth.login_failed`, `auth.logout`, `auth.register`, `auth.password_change`, `wallet.add/delete`, `integration.add/delete`, `snapshot.delete`, `account.soft_delete`. `app/services/audit.py::log_audit()` best-effort (try/except yutar — ana endpoint bozulmaz). X-Forwarded-For destekli (proxy/ingress arkası). `GET /api/v1/audit-logs?action_prefix=&limit=` IDOR korumalı (user kendi log'larını görür).

**.app TLD HSTS preload:** `kfinans.app` Chromium/Firefox/Safari HSTS preload listesinde — tarayıcı DNS sorgusu yapmadan zorla HTTPS kullanır. Manuel HSTS header (FAZ C2) defence-in-depth için yine eklendi. Bu nedenle ilk deploy öncesi `https://kfinans.app` "ERR_CERT_AUTHORITY_INVALID" verir (sertifika yok); cert-manager Let's Encrypt'i çekince düzelir.

**CI/CD pipeline (FAZ B):** 6 workflow var:
- `ci-backend.yml`: lint (ruff) + unit + integration (real Postgres) + coverage gate (%50 threshold)
- `ci-frontend.yml`: lint + vitest unit
- `e2e.yml`: Playwright E2E
- `security.yml`: gitleaks (.gitleaks.toml allowlist) + Trivy fs (HIGH/CRITICAL fail) + pip-audit (osv strict) + npm-audit (high) + CodeQL (Python + JS/TS, security-and-quality query)
- `sonar.yml`: backend pytest cov XML + frontend vitest LCOV → SonarCloud quality gate (`vars.ENABLE_SONAR == 'true'` iken aktif; bekleme döneminde skip)
- `release.yml`: semver tag (`v*.*.*`) → Sonar quality gate → matrix Docker buildx & GHCR push (backend + frontend) → Trivy image scan (HIGH/CRITICAL fail) → Oracle SSH `kubectl set image` + rollout → Playwright @smoke → GitHub Release notes

**Branch stratejisi (FAZ B6):** `main` PR şart + lineer history + force-push kapalı + branch silme kapalı + conversation resolution zorunlu (review opsiyonel — tek dev için, ekip büyüdükçe count=1 yapılır). `develop` doğrudan push'a izin (siz lokal), force-push kapalı, branch silme kapalı. Default branch `develop`. Sadece **squash merge** (lineer history). Merge sonrası branch otomatik silme.

**BES:** Manuel giriş + Excel import/export. 4 metric (yatırılan ana para + getirisi, devlet katkısı + getirisi). Snapshot servisi `_gather_bes_assets()` ile `asset_type="pension"` olarak entegre eder.

**Periyodik gelir (`recurring_incomes`):** Maaş, kira, temettü gibi düzenli gelirler için ayrı tablo (`PlannedExpense` ile aynı yapı). Tek seferlik kayıtlar `incomes` tablosunda kalır; recurring sadece **tahmin/beklenti** için kullanılır. Recurrence: `one_time/monthly/quarterly/biannual/yearly/custom`. `GET /income/dashboard?year=&month=` 6 metrik döner: this_month_actual, ytd_actual, this_month_recurring, ytd_recurring, remaining_year_recurring, year_total_estimate (= ytd_actual + remaining). Frontend `/dashboard/income` 3 metrik kartı + 2 sekme (Gerçekleşen / Periyodik). Dashboard "Gelirler" kartı footer'da yıl sonu beklentisi gösterir.

**Cash flow (`/cash-flow`) + raporlar:** `GET /cash-flow?year=...` 12 aylık nakit akış projeksiyonu döner: gerçek_gelir + tahmini_gelir (recurring), gerçek_gider (expenses çift sayım filtresi + kart ekstreleri due_date) + tahmini_gider (planned + taksitler). Her ay için `is_past` flag (geçmiş = sadece actual; gelecek = forecast da dolu). Frontend `/dashboard/cash-flow` yıl seçici (geçen/bu/gelecek) + ComposedChart (gelir-gider çubuk + Net çizgi) + aylık tablo + Excel/PDF indirme. Reportlab + openpyxl ile rapor üretimi (`services/reports.py`); DejaVu Sans font ile Türkçe karakter desteği.

**Snapshot raporu indirme:** `GET /portfolio/snapshot/{snapshot_date}/report.xlsx` ve `.pdf`. Excel: tüm pozisyonlar (tip, provider, sembol, isim, likit/stake/pending, fiyat, toplam, ağırlık). PDF: ilk 50 pozisyon (en büyük → küçük) + USD karşılığı + USD/TRY kuru. History sayfasında her snapshot satırında 📊 xlsx + 📄 pdf butonları.

**Çift sayım kuralı (kredi kartı + Expense / Planned):** Kredi kartından yapılmış ve gerçekleşmiş bir harcama (Expense), kart borcuyla zaten sayıldığı için ham gider toplamına eklenmemeli — aksi halde çift sayım olur. Kural: `credit_card_id IS NOT NULL AND is_paid=true` → ham toplamlardan **HARİÇ TUT**. Filtre `or_(credit_card_id IS NULL, is_paid=false)` ile uygulanır. Etkilenen endpoint'ler: `GET /expenses/summary`, `GET /budgets/comparison`, `GET /planned-expenses/forecast`. Liste endpoint'leri (`GET /expenses`, `GET /planned-expenses`) tüm kayıtları gösterir; frontend rozetlerle (`💳 kart`, `✓ ödendi`) durumu belirtir.

**Kredi kartları (`credit_cards` + `credit_card_statements` + `credit_card_installments`):** Faz 3 finans modülü. **Kart tanımı:** name, bank_name, last_4, credit_limit, statement_day, payment_due_day, **`current_period_debt`** (dönem içi henüz ekstreye düşmemiş tutar — kullanıcı manuel günceller). **Aylık ekstreler:** her kart için `(period_year, period_month)` unique kayıtlar — statement_amount, statement_date, due_date, paid_at (nullable). **Taksitler:** description, total_amount, monthly_amount, installments_total, installments_remaining, first_due_date — gelecek aylar projeksiyonu için. Endpoint'ler: `/credit-cards` CRUD + summary + `/{id}` detail (statements + installments tek seferde) + `/{id}/statements` ve `/{id}/installments` nested CRUD'ları. Frontend: ana sayfa kart listesi + her satırda "Ekstre / Taksit" linki → detay sayfası `/dashboard/credit-cards/[id]` (statement form + tablo + installment form + tablo). Dashboard "Kredi Kartları" kartı **Finans grubunun en üstünde**. Çift sayım kuralı (Expense + Planned'da credit_card_id + is_paid) sonraki adımda devreye girecek.

**Realize akışı (recurring → income):** Periyodik kayıtların belirli bir ay-yılı için `incomes` tablosuna **gerçek kayıt** üretmesi 3 endpoint ile sağlanır: `POST /income/recurring/{id}/realize` (tek dönem, body `{year, month}`), `POST /income/recurring/{id}/realize-past` (start_date'ten bugüne tüm dönemler), `POST /income/recurring/realize-all-past` (tüm recurring'ler). `incomes.recurring_income_id` (FK→recurring_incomes, ON DELETE SET NULL) çift realize'ı engelleyen `(recurring_income_id, date)` unique index ile birlikte. Frontend RecurringIncomeTable'da satır başına "Bu ay ✓" / "Geçmişi ✓" butonları + üstte "Tümünün Geçmişini Gerçekleştir". IncomeTable'da realize'lı kayıtlarda mavi "↻ periyodik" rozeti.

**Fault-tolerance pattern:** Dış servisler **kritik** ve **best-effort** olarak ayrılır. TCMB USD/TRY kritik (fail → 503); GBP/USD opsiyonel (fail → 0 + log warning). Yahoo Finance metal sembolleri için fallback chain (XAU=X→GC=F, XAG=X→SI=F); ikisi de fail ise 0 dön + UI uyarı banner. Cache TTL Yahoo fail durumunda 5 dk → 30 sn'ye düşer (geçici 404 hızla telafi edilir).

**Multi-RPC fallback (EVM zincirler):** Ethereum ve Avalanche C-Chain `settings.{ethereum,avalanche_c}_rpc_url` → publicnode → merkle → 1rpc → ankr → drpc sırasıyla denenir; upstream patladığında self-heal sağlar. Servisler ilk başarılı RPC'yi seçer.

**Bitcoin xpub cache + single-flight:** `bitcoin.py` modül seviyesinde `_BALANCE_CACHE` (10 dk TTL) ve `_INFLIGHT` dict + `asyncio.Future` tutar. Dashboard yenileme rate limit'e takılmasın diye paralel cache miss'lerde tek tarama paylaşılır; tüm metal 0 dönerse TTL 30 sn'ye düşer (geçici 404 hızla recovery).

**Ethereum ERC-20 token discovery (Ethplorer):** Ethereum mainnet için `evm_tokens.py::fetch_ethereum_tokens_via_ethplorer()` `api.ethplorer.io` free tier (key='freekey', ~50 istek/gün) ile kullanıcının tüm ERC-20 token bakiyelerini dinamik bulur. **Spam filter:** domain TLD'leri (.io/.com/.finance), Cherokee/Math Alphanumeric Unicode spoofing, "Visit/claim rewards" pattern'leri ve >1e12 miktar token'lar `_looks_like_spam()` ile atılır. Avalanche C-Chain için curated `AVALANCHE_C_TOKENS` (sAVAX, USDT.e, USDC.e) — sequential `balanceOf` (Infura/RPC rate limit), 3 retry + 0.5 sn backoff.

**422 Validation log handler:** `main.py` `RequestValidationError` exception handler 422 hata detayını (`exc.errors()`) log'a yazar; frontend'e mevcut formatta dönüş — debug ipucu.

**MKK e-Yatırımcı Excel import:** `xlrd 1.2.0` ile eski .xls binary parse. Header satırı "Üye" sütunundan otomatik tespit. Sınıfa göre filtre: TEFAS için `Kıymet Sınıfı=Fon`, hisse için `Kıymet Sınıfı=HS AND Ek Tanım=A`. BIST kodları otomatik `.IS` suffix ile Yahoo Finance ticker'ına çevrilir. Mevcut kayıtlar replace-all silinir.

**Distributor (aracı kurum) alanı:** TEFAS + Stocks holding'lerinde aynı varlığı (örn. ZJI fonu) farklı kurumlardan (Ziraat + Foneria) ayrı satır olarak izlemek için `distributor` (VARCHAR 50). MKK Üye sütunu otomatik bu alana yazılır.

**Maliyet bazı (avg_cost_tl):** TEFAS + Stocks `avg_cost_tl` (Numeric 18,6 nullable) — TRY/adet ortalama maliyet. Schema validator: 0 veya negatif → None (kullanıcı bilmiyorsa boş bırakabilir). Preview/list'te `cost_basis_tl`, `gain_loss_tl`, `gain_loss_pct` hesaplanır.

**Manuel kripto (API'siz borsalar):** API erişimi olmayan borsalar (BinanceTR, iCrypex, BTCTurk, Paribu, Bybit, KuCoin, Bitget vb.) için kullanıcının manuel kayıt yapabildiği `manual_crypto_holdings` tablosu. Endpoint prefix `/manual-crypto`; CRUD + Excel import/export + anlık fiyatla zenginleştirilmiş listeleme. **`price_source` 3 mod:** `'auto'` (Binance USDT + CoinGecko fallback — varsayılan), `'manual'` (kullanıcının `manual_unit_price_tl` alanı), `'linked'` (asset catalog ile mevcut bir varlığa bağla). `linked` modunda `linked_source ∈ {commodity, binance, coingecko, tefas}` ve `linked_id` (örn. `commodity:XAG` = gümüş gr, `binance:ETH`, `coingecko:tether-gold`, `tefas:AFA`). Snapshot entegrasyonu `services/snapshot.py::_gather_manual_crypto_assets()` — `asset_type="crypto"`, `provider="manual:{exchange}"`. Manual/linked kayıtlar için fiyat asset'e enjekte edilir; auto kayıtlar ortak enrichment loop'unda yakalanır. Eksik fiyat durumunda snapshot health `issues` listesine eklenip popup'ta gösterilir.

**Asset catalog endpoint:** `GET /asset-catalog?q=...&source=...&limit=20` — manuel kripto formundaki autocomplete için 4 kaynaktan birleşik arama: commodity (statik 2: XAU/XAG), binance (USDT pariteli base symbol'ler — 5 dk cache), coingecko (24h cache'lenen `/coins/list`), tefas (1 saat cache'li aktif fon listesi). Substring match (TR+EN), source başına `_search_*` helper'larında parçalı.

**CoinGecko fallback fiyatlama:** `aggregator.fetch_combined_prices(symbols)` Binance USDT paritesi olmayan token'lar için CoinGecko `/simple/price` endpoint'ini kademeli kullanır. `/coins/list` (~17K coin) **24 saat in-memory cache**'lenir; `COINGECKO_SYMBOL_OVERRIDES` map'i ile çoklu eşleşmeler ezilir (ör. `ICPX → icrypex-token`). Free tier (~30 istek/dk) yeterli — sadece Binance'te 0 dönen + alias/stable olmayan semboller CoinGecko'ya gider. Snapshot ve `/portfolio/wallets` ve `/manual-crypto` endpoint'leri bu fonksiyonu kullanır.

**Avalanche P-Chain likit bakiye + cache:** `AvalanchePChainService.fetch()` önce **Glacier (Routescan) REST API** dener (`https://glacier-api.avax.network/v1/networks/mainnet/blockchains/p-chain/balances`), fail ederse `platform.getBalance` + `platform.getStake` JSON-RPC'ye fallback yapar (`P-` prefix'li adres + 429 backoff retry). Public Avalanche RPC sıkı rate-limit uygular (HTTP 429); Glacier daha gevşek olduğu için tercih edilir. Modül seviyesinde `_PCHAIN_CACHE` (10 dk TTL) + `_pchain_inflight` single-flight pattern (Bitcoin ile aynı). `unlockedUnstaked` → liquid; `lockedStaked + pendingStaked + unlockedStaked + lockedStakeable` → staked. `asset_type` staked > liquid ise `staked_crypto`.

**Soft-delete + hard-delete cron (COMP-004):** `DELETE /user/me` `users.deleted_at = now()` set eder. `_hard_delete_expired_users_job` her gün 04:00'de 30 gün geçmiş kayıtları fiziksel siler (FK CASCADE + audit_logs SET NULL ile anonim).

**audit_logs retention (COMP-022):** Tablo 365 gün retention; `_purge_old_audit_logs_job` her gün 04:30 eski PII'yi siler (KVKK m.7). Kullanıcı tarafından sayfalı erişim: `GET /audit-logs?limit=50&offset=0` (PERF-001 PaginatedResponse[T]).

**Tavsiye motoru (AI-003 + AI-005 + AI-007 + AI-008):** `advisor.py` portföy dağılımını, haftalık/aylık değişimleri ve risk profilini Claude API'ye gönderir. System prompt 1500-2000 token (Anthropic prompt cache aktif), SPK uyumlu disclaimer hem prompt'a injekte hem post-processing footer (`_ensure_disclaimer`). `/advice/generate` çağrı sırası: (1) `anthropic_consent_at IS NULL` → 403 KVKK m.9, (2) `credit_balance < 1` → 402 yetersiz kredi, (3) slowapi 5/saat, (4) Anthropic çağrısı, (5) atomik `credits_used += 1` düşüm.

**Pagination pattern (PERF-001):** Yeni list endpoint'leri `app/schemas/pagination.py::PaginatedResponse[T]` döner: `items + total_count + has_next + limit + offset`. Default limit=50, max 500. Şu an `/audit-logs` kullanıyor; `/expenses /incomes /wallets /planned-expenses` pagination Faz 4 TODO.

**Rate limit stratejisi (SEC-003 + SEC-005):** `slowapi` Redis backend (`settings.redis_url` set ise multi-replica güvenli; yoksa MemoryStorage + K8s `replicas: 1`). Pahalı/spam'a açık endpoint'ler için zorunlu: auth (10/dk login, 5/dk register), advice generate (5/saat), snapshot (6/saat), stocks/tefas preview (30/dk), data export (5/saat), email change (3/dk), anthropic consent (10/saat). Detay: `docs/03-api-referansi.md §1.4`.

**Address masking (BACK-013):** `app/core/masking.py::mask_address` (ilk 6 + son 4). `WalletOut.address` ve `WalletPositionOut.address` Pydantic `field_serializer` ile maskelenir — JSON response'ta xpub leak yok. DB'de Fernet şifreli (FAZ C1) + JSON'da masked (BACK-013) çift katmanlı koruma.

**Generic exception handler (BACK-008 + ARC-006):** `main.py`'a `IntegrityError → 409`, `SQLAlchemyError → 500 db_error`, `Exception → 500 internal_error` handler'ları. Hepsi `{detail, code, request_id}` sanitized format — internal SQL/exception trace frontend'e sızmaz, log'da tam trace.

**Exception detail sanitization (SEC-007):** `try/except` ile yakalanmış 5 yerde `detail=f"...{e}"` interpolation kaldırıldı → `logger.exception(...)` (full trace) + generic Türkçe kullanıcı mesajı. Etkilenen: `manual_crypto._fetch_prices_safe` (price + USD/TL), `manual_crypto.import_excel` (openpyxl), `portfolio.snapshot_preview`, `portfolio.create_snapshot`. `tefas.py:88` ValueError korundu (user-input echo "TEFAS'ta fon bulunamadı: <code>"; servisin tek raise noktası dokümante). Saldırgan DB URL/secret/SQL/stack trace görmemeli. BACK-008 generic handler tamamlayıcı (yakalanmayan'lar için son safety net).

**Production smoke test (DEPLOY-001):** `release.yml::smoke-test` job Playwright'tan ÖNCE 4-step curl gate çalıştırır (~5 sn): (1) frontend HTTPS up + cert validity, (2) `/health` JSON `{"status":"ok"}` (NOT `/api/v1/health` — health endpoint root'ta, prefix yok), (3) `POST /api/v1/auth/login` bogus creds → 401 (DB+endpoint+slowapi chain canlı), (4) HSTS + X-Frame + CSP + X-Content-Type-Options header'lar mevcut. Curl fail ise Playwright çalışmaz, deploy gate olur. Lokal smoke runner: `frontend/scripts/smoke.sh` + `npm run smoke` (BASE/API_BASE env override). 11 @smoke Playwright test (login + register + logout + a11y + i18n + security headers). Frontend Sentry browser SDK (`@sentry/nextjs`) ileride.

**i18n foundation (i18n-001):** Client-side cookie tabanlı TR/EN dil desteği. `app/_i18n/dictionaries/{tr,en}.json` (auth + common + legal + footer anahtarları), `app/_i18n/I18nProvider.tsx` React Context (cookie `kfinans-locale=tr|en`, `samesite=lax`, 1 yıl), `useTranslation()` hook → `t("auth.login")` → "Giriş Yap" / "Sign In", `LanguageSwitcher` toggle (dashboard layout top-right + login sayfası top-right; `aria-pressed` segmented). Eksik anahtarlar key'i geri döner (sessiz fallback). Dil değişiminde sayfa reload yok — Context push + `<html lang>` attribute güncellemesi (ekran okuyucu duyurur). **Sayfa bazlı `app/[lang]/...` routing kullanılmadı** — mevcut 17 dashboard sayfasını taşımayı gerektirir; cookie tabanlı yaklaşım foundation için yeterli. Yeni sayfa çevirisi: `"use client"` + `const { t } = useTranslation()` + dictionary JSON'a anahtar ekle. Şu an çevrili: login + dashboard layout. Geri kalan sayfalar TR-only (incremental).

**Observability — Sentry + OpenTelemetry (OBS-001):** `app/observability.py::init_sentry/init_otel` `main.py` lifespan startup'inda çağrılır. **Hepsi opt-in:** `settings.sentry_dsn` boş ise no-op, `settings.otel_endpoint` boş ise no-op (dev'de pasif). Sentry SDK FastAPI + SQLAlchemy integration'ları (exception capture + breadcrumb + perf monitoring); `send_default_pii=False` default (KVKK güvenli). OTel instrumentation: FastAPI handler + SQLAlchemy + asyncpg + httpx — `OTLPSpanExporter` Tempo/Jaeger/Honeycomb endpoint'ine HTTP POST. `traces_sample_rate` default %10. Release tagi `GIT_SHA` env (release.yml CMD'da injekte edilir). Production env: `SENTRY_DSN`, `SENTRY_ENV=production`, `OTEL_ENDPOINT=http://tempo:4318/v1/traces`. PERF-004 in-memory tracker hala çalışır; OTel ileride yerini alabilir.

**Confirm dialog — i18n + a11y (FE-013):** Native `window.confirm()` 13 yerde kaldırıldı → `app/_components/ConfirmDialog.tsx::ConfirmDialogProvider` (root layout'ta mount) + `useConfirm()` async hook. Çağrı pattern: `if (!(await confirm("Silinsin mi?", { destructive: true })))`. Dialog `role="alertdialog"` + `aria-modal` + `aria-labelledby/describedby` + `useFocusTrap` (A11Y-001 hook reuse) + Esc kapatma + initial focus confirm butonuna (`autoFocus`). `destructive` flag kırmızı/mavi buton seçer. i18n: `common.confirm/yes/cancel` dictionary'den. @smoke test: hesap silme akışı dialog açılır, Esc iptal eder.

**Frontend erişilebilirlik (A11Y-001):** WCAG 2.1 AA için temel temel eklemeler. `<html lang="tr">` (önce `en`'di), dashboard layout'ta sr-only "Ana içeriğe atla" skip-link (focus aldığında görünür, `#main-content` hedefi), `app/_hooks/useFocusTrap.ts` (Tab/Shift+Tab modal içinde döngü, Esc kapatma, açılışta ilk focusable element'e focus, kapanışta önceki element'e geri dönüş), `SnapshotIssuesModal` `role="dialog" aria-modal aria-labelledby aria-describedby` + focus trap, login formu `htmlFor`/`autoComplete=email|current-password` + hata mesajı `role="alert" aria-live="assertive"`. 11 dosyada icon-only `✕` butonlarına `aria-label="<isim> kaydını sil"` + `<span aria-hidden="true">✕</span>` + `focus-visible:ring-2`. 4 yeni Playwright @smoke test (`a11y.spec.ts`). Axe-core entegrasyonu ileride yapılabilir.

**Request timing middleware (PERF-004):** `app/core/middleware.py::RequestTimingMiddleware` her request için `time.perf_counter()` ile süre ölçer; `X-Response-Time: 35.7ms` header'ı ekler ve `>= settings.slow_request_threshold_ms` (default 500) requestler `WARNING SLOW_REQUEST` log'a yazılır. Per-route ring buffer (`app/core/perf_metrics.py`, deque maxlen=1000) endpoint template path'i (`POST /api/v1/auth/login`) ile gruplar — UUID/path-param leak yok, dict cardinality bounded. `GET /api/v1/metrics/performance` endpoint'i `X-Metrics-Token` header `settings.metrics_token` ile eşleşirse `{count, p50_ms, p95_ms, p99_ms, max_ms, slow_count}` snapshot döner; token boş veya yanlışsa 404 (varlık sızdırılmaz). Middleware en içte (ilk add edilir) — app handler süresini ölçer, X-Response-Time header sonraki middleware'lerden geçer. OBS-001 (Sentry/OTel) eklenince deprecate edilebilir.

## Geliştirme Kuralları

- Tüm dokümantasyon ve commit mesajları Türkçe; kod içi identifier ve yorumlar İngilizce
- Her veri kaynağı servisi `fetch()` metodunu implement eden soyut `BaseIntegration` sınıfından türer
- Secrets asla koda yazılmaz, sadece `.env` üzerinden `pydantic-settings` ile okunur
- **Pydantic v2 modern stiller (DEPS-001):** `model_config = ConfigDict(...)` (NOT `class Config:`); validation için `@field_validator + classmethod` (NOT `model_post_init`). Yeni schema'lar v1 stillerini kullanmamalıdır.
- **Test izolasyonu (TEST-004):** `tests/integration/conftest.py` autouse `_truncate_after_test` her test sonunda tüm tabloları TRUNCATE eder. Testler kümülatif değil; `client` fixture session-per-request commit'leri rollback olmaz ama TRUNCATE temizler.
- **Test fixture (TEST-002):** `tests/conftest.py::make_user(client, email=None)` ortak helper; her test dosyasında lokal `_make_user` yazma — import et. `age_confirmed=True` zorunlu (COMP-010).
- **Test sayıları:** 192 unit + 357 integration (FAZ H sonu — PERF-004 + OBS-001 dahil). CI coverage gate: line %60 + branch %50 + critical path (auth/security/masking) %90 (TEST-007).
- **Migration head:** `c0d1e2f3a4b5` (AI-005 anthropic_consent kolonları, 2026-05-10). Yeni migration `down_revision = "c0d1e2f3a4b5"`.
