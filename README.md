# KFinans

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](./CODE_OF_CONDUCT.md)

> **Türkiye'ye özel kişisel yatırım ve finans takip uygulaması**
> 🌐 Production: [https://kfinans.app](https://kfinans.app) *(yakında)*

KFinans, dağınık yatırım hesaplarınızı ve günlük finansal yaşamınızı tek ekranda toplar:
**TEFAS yatırım fonları**, **kripto borsaları** (Binance, iCrypex), **blockchain cüzdanlar** (Sonic, Avalanche, Ethereum, Bitcoin, Solana, +5 zincir), **BES birikimleri**, **hisse senetleri** (BIST + ABD + UK, Yahoo Finance), **kıymetli madenler** (gram/BiGA/sikke), **harcama-gelir-bütçe takibi** ve **AI destekli yatırım tavsiyeleri** (Claude API).

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
| **Borsa** | CCXT (Binance, iCrypex) |
| **Blockchain** | web3.py (Sonic SFC, Avalanche C-Chain + P-Chain, Ethereum) |
| **TEFAS** | Resmi TEFAS export API |
| **Hisse senedi** | Yahoo Finance Chart API + TCMB USD/TRY |
| **Kıymetli maden** | Yahoo Finance (XAU=X / GC=F, XAG=X / SI=F) + TCMB |
| **MKK e-Yatırımcı** | xlrd ile "Tüm Kıymetler" .xls direkt import |
| **AI tavsiye** | Anthropic Claude (Sonnet 4.6) |
| **E-posta** | Resend SDK |
| **Auth** | JWT (python-jose) + JWT blacklist + e-posta doğrulama |
| **Zamanlayıcı** | APScheduler (Pazar 23:00 haftalık snapshot) |
| **Şifreleme** | Fernet (API key'ler DB'de şifreli) |
| **Container** | Docker Compose (dev) + Kubernetes (prod) |

---

## Proje Yapısı

```
KFinans/
├── backend/             # FastAPI uygulaması — bkz: backend/README.md
│   ├── app/
│   │   ├── api/v1/      # Endpoint router'ları
│   │   ├── services/    # Borsa, blockchain, TEFAS, snapshot, advisor
│   │   ├── models/      # SQLAlchemy
│   │   ├── schemas/     # Pydantic
│   │   └── scheduler.py # APScheduler haftalık snapshot
│   ├── alembic/         # DB migrations
│   └── tests/           # 175+ test (pytest + respx mocks)
├── frontend/            # Next.js — bkz: frontend/README.md
│   ├── app/
│   │   ├── dashboard/   # 11 dashboard kartı + alt sayfalar
│   │   ├── _components/ # KFinansLogo, MayotekLogo, MkkHint, PageHeader
│   │   └── legal/       # KVKK, gizlilik, şartlar, çerezler
│   └── lib/
├── docs/                # Tasarım, mimari, API, güvenlik, KVKK — bkz: docs/README.md
├── k8s/                 # Kubernetes manifest'leri (prod deploy)
├── docker-compose.yml   # Dev ortamı
└── docker-compose.prod.yml
```

---

## Özellikler

- **11 yatırım/finans kartı** dashboard'da: TEFAS, kripto, hisse, cüzdan, BES, harcama, planlı ödeme, gelir, hedef, kıymetli maden, bütçe
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
pytest                      # 175+ test
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
