# KFinans

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](./CODE_OF_CONDUCT.md)

> **Türkiye'ye özel kişisel yatırım ve finans takip uygulaması**
> 🌐 Production: [https://kfinans.app](https://kfinans.app) *(canlı — v0.1.0-rc16, Oracle K3s)*

KFinans, dağınık yatırım hesaplarınızı ve günlük finansal yaşamınızı tek ekranda toplar:
**TEFAS yatırım fonları**, **kripto borsaları** (Binance, iCrypex), **manuel kripto** (API'siz borsalar — BinanceTR, BTCTurk, Paribu vb.), **blockchain cüzdanlar** (10 zincir: Bitcoin, Ethereum, Sonic, Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin), **BES birikimleri**, **hisse senetleri** (BIST + ABD + UK, Yahoo Finance), **kıymetli madenler** (gram/BiGA/sikke), **nakit/banka hesapları**, **kredi kartı (ekstre + taksit)**, **harcama-gelir-bütçe-nakit akış takibi** ve **AI destekli yatırım tavsiyeleri** (Claude API).

Bir [Mayotek](https://mayotek.com) ürünüdür.

> ⚠️ **Kişisel finansal veri uyarısı:** Bu uygulama exchange API anahtarlarınızı, blockchain cüzdan adreslerinizi ve portföy bakiyelerinizi işler. Self-host eden kullanıcılar **kendi verilerinin yöneticisidir**. Production deploy yapacaksanız mutlaka [docs/07-guvenlik.md](./docs/07-guvenlik.md) ve [docs/08-uyumluluk-kvkk.md](./docs/08-uyumluluk-kvkk.md) dokümanlarını okuyun. SaaS sürümümüzü (`https://kfinans.app`) kullanırken işlenen veriler için Aydınlatma Metni ve KVKK haklarınızı [hesap ayarları](https://kfinans.app/legal) sayfasında bulabilirsiniz.

---

## Hızlı Başlangıç

```bash
# 1. Repo'yu klonla
git clone https://github.com/celikada/KFinans.git
cd KFinans

# 2. Ortam değişkenlerini hazırla
cp backend/.env.example backend/.env       # Anthropic, Resend, blockchain RPC anahtarlarını gir
cp frontend/.env.local.example frontend/.env.local

# 3. Docker Compose ile ayağa kaldır
docker compose up --build

# 4. Tarayıcıda aç
open http://localhost:3000
```

İlk kullanıcı: `/register` → e-posta doğrulama → `/dashboard`.

---

## Tech Stack

| Katman | Teknoloji |
|---|---|
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| **Frontend** | Next.js 16 (App Router) + TypeScript + Tailwind CSS |
| **Veritabanı** | PostgreSQL 16 |
| **Borsa** | CCXT (Binance, iCrypex, BinanceTR) |
| **Blockchain** | web3.py (Ethereum, Sonic SFC, Avalanche C-Chain) + httpx public API (Avalanche P-Chain, Bitcoin, Solana, Cardano, Algorand, Litecoin) + substrate-interface (Polkadot) — 10 zincir |
| **TEFAS** | httpx + resmi TEFAS JSON API |
| **Hisse senedi** | Yahoo Finance Chart API + TCMB USD/TRY |
| **Kıymetli maden** | Yahoo Finance (XAU=X / GC=F, XAG=X / SI=F) + TCMB |
| **MKK e-Yatırımcı** | xlrd 1.2.0 ile "Tüm Kıymetler" .xls direkt import |
| **AI tavsiye** | Anthropic Claude (advisor.py — kredi tüketimli) |
| **E-posta** | Resend SDK |
| **Auth** | JWT (python-jose) + refresh rotation + JWT blacklist + MFA (TOTP) + e-posta doğrulama |
| **Zamanlayıcı** | APScheduler (4 cron job: Pazar 23:00 snapshot, 03:00 token cleanup, 04:00 hard-delete, 04:30 audit purge) |
| **Şifreleme** | Fernet/MultiFernet (API key + wallet xpub DB'de şifreli) + bcrypt (şifre + recovery code) |
| **Observability** | Sentry + OpenTelemetry (opt-in) |
| **Container** | Docker Compose (dev) + Kubernetes / K3s (prod) |

---

## Proje Yapısı

```
KFinans/
├── backend/             # FastAPI uygulaması — bkz: backend/README.md
│   ├── app/
│   │   ├── api/v1/      # 23 endpoint router'ı (auth, mfa, user, portfolio, ...)
│   │   ├── services/    # Borsa, blockchain (10 zincir), TEFAS, snapshot, advisor, audit
│   │   ├── models/      # SQLAlchemy
│   │   ├── schemas/     # Pydantic
│   │   └── scheduler.py # APScheduler — 4 cron job (snapshot + token cleanup + hard-delete + audit purge)
│   ├── alembic/         # DB migrations (39 migration, head: e2f3a4b5c6d7)
│   └── tests/           # ~1180 test (pytest + respx mocks), coverage %95+
├── frontend/            # Next.js — bkz: frontend/README.md
│   ├── app/
│   │   ├── dashboard/   # 17 alt sayfa (tefas, stocks, wallets, crypto, manual-crypto, bes, ...)
│   │   ├── _components/ # Logos, MkkHint, PageHeader, ConfirmDialog, ...
│   │   ├── _i18n/       # TR/EN dil desteği (cookie tabanlı, I18nProvider)
│   │   └── legal/       # KVKK, gizlilik, şartlar, çerezler
│   └── lib/
├── docs/                # Tasarım, mimari, API, güvenlik, KVKK — bkz: docs/README.md
├── k8s/                 # Kubernetes manifest'leri (prod deploy)
├── docker-compose.yml   # Dev ortamı
└── docker-compose.prod.yml
```

---

## Özellikler

- **17 yatırım/finans modülü** dashboard'da: TEFAS, kripto, manuel kripto, hisse, cüzdan, BES, kıymetli maden, nakit, kredi kartı, harcama, planlı ödeme, gelir, bütçe, hedef, nakit akış, geçmiş, ayarlar
- **Kart gizleme** — kullanıcı kendi dashboard'ını özelleştirir
- **MKK Excel import** — "Tüm Kıymetler" .xls dosyasından TEFAS + hisse senetleri tek tıkla yüklenir, kurum bilgisi otomatik dolar
- **Maliyet bazı + Kâr/Zarar** — her holding için ortalama maliyet, otomatik gain/loss hesabı
- **Distributor (kurum) takibi** — aynı varlık farklı kurumlarda ayrı satırlarda
- **Otomatik snapshot** — Pazar 23:00 + manuel + import sonrası
- **AI tavsiye motoru** — Claude API portföy dağılımı + risk profiline göre haftalık öneri üretir
- **KVKK uyumlu** — açık rıza yönetimi, hesap silme (soft-delete), veri dışa aktarımı

---

## Geliştirici Komutları

```bash
# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
pytest                      # ~1180 test (coverage %95+)
ruff check . && ruff format .

# Frontend
cd frontend
npm install
npm run dev
npm test                    # Vitest + Playwright
npm run lint
```

---

## Dokümantasyon

Detaylı teknik dokümanlar için → [`docs/`](./docs/README.md):
1. Sistem Tasarım Dokümanı
2. Mimari + DB Şeması
3. API Referansı
4. Frontend Mimarisi
5. AI ve Finans Hesaplamaları
6. Kredi Sistemi (SaaS billing)
7. Güvenlik Mimarisi
8. KVKK Uyumluluğu
9. Altyapı, Deployment, Test
10. Yol Haritası 2026 (rekabet analizi + ürün stratejisi)

**Sürüm geçmişi:** [CHANGELOG.md](./CHANGELOG.md) — Faz bazli tarihsel
ozet (Added / Changed / Fixed / Security).
**Yasal süreç:** [docs/legal/incident-response-plan.md](./docs/legal/incident-response-plan.md)
— Veri ihlali müdahale planı (ISO 27035 esinli, KVKK m.12/5).

---

## Geri Bildirim — Bug, Feature, Soru

KFinans'ta bir sorun yaşadıysanız veya öneriniz varsa aşağıdaki kanallar:

| Kategori | Kanal | Yanıt süresi (hedef) |
|----------|-------|---------------------|
| 🐛 **Bug raporu** | [Yeni Issue → Bug Report](https://github.com/celikada/KFinans/issues/new?template=bug_report.yml) | Kritik: 48 saat / diğer: 1 hafta |
| 💡 **Yeni özellik isteği** | [Yeni Issue → Feature Request](https://github.com/celikada/KFinans/issues/new?template=feature_request.yml) | Triage: 1 hafta / yapılır mı kararı: 2 hafta |
| ❓ **Soru / yardım** | Önce [Discussions / Q&A](https://github.com/celikada/KFinans/discussions/categories/q-a); aciliyet varsa [Issue](https://github.com/celikada/KFinans/issues/new?template=question.yml) | Topluluk: hızlı / sürdürücü: 1 hafta |
| 💬 **Tartışma / fikir** | [Discussions / Ideas](https://github.com/celikada/KFinans/discussions/categories/ideas) | Asenkron — topluluk yanıt verir |
| 🎉 **Showcase** | [Discussions / Show & Tell](https://github.com/celikada/KFinans/discussions) | – |
| 🔐 **Güvenlik açığı** | **Public issue açmayın** — [SECURITY.md](./SECURITY.md) ya da [Private Vulnerability Report](https://github.com/celikada/KFinans/security/advisories/new) | 48 saat ack, 30 gün fix planı |

Issue açarken **template'leri doldurun** — yapılandırılmış raporlar 3-5 kat daha hızlı çözülür. Triage label'ları (`status:needs-triage` → `status:in-progress` → tamamlandı) ile durumu takip edebilirsiniz.

## Katkı

Katkı sağlamak istiyorsanız: [CONTRIBUTING.md](./CONTRIBUTING.md). Tüm katkıcılar [Davranış Kuralları](./CODE_OF_CONDUCT.md)'na uymakla yükümlüdür.

## Güvenlik Açığı Bildirimi

Lütfen güvenlik açıklarını **public issue olarak açmayın**. [SECURITY.md](./SECURITY.md) bildirim akışını izleyin.

## Lisans

[Apache License 2.0](./LICENSE) — Copyright © 2026 Mayotek.

Bu lisans size kodu kullanma, değiştirme, dağıtma, alt-lisanslama ve patent kullanım hakkı verir. Yalnızca lisans metnini ve copyright bildirimini saklayın.

## İletişim

- 📧 Genel: `celikada@gmail.com`
- 🔐 Güvenlik: [SECURITY.md](./SECURITY.md)
- 🐛 Bug / Özellik: [GitHub Issues](https://github.com/celikada/KFinans/issues)
