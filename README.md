# KFinans

> **Türkiye'ye özel kişisel yatırım ve finans takip uygulaması**

KFinans, dağınık yatırım hesaplarınızı ve günlük finansal yaşamınızı tek ekranda toplar:
**TEFAS yatırım fonları**, **kripto borsaları** (Binance, iCrypex), **blockchain cüzdanlar** (Sonic, Avalanche, Ethereum), **BES birikimleri**, **hisse senetleri** (BIST + ABD + UK, Yahoo Finance), **kıymetli madenler** (gram/BiGA/sikke), **harcama-gelir-bütçe takibi** ve **AI destekli yatırım tavsiyeleri** (Claude API).

Bir [Mayotek](https://mayotek.com) ürünüdür.

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

---

## Lisans

Tüm hakları saklıdır © Mayotek.

## İletişim

celikada@gmail.com
