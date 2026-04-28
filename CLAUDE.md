# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje Hakkında

KFinans, kişisel yatırım portföyünü tek ekranda toplayan bir uygulamadır. Binance ve iCrypex kripto hesapları, TEFAS yatırım fonları ve BES birikimleri API/scraping ile otomatik çekilir; haftalık değişimler hesaplanır ve Claude API aracılığıyla orta/uzun vadeli yatırım tavsiyeleri sunulur.

## Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend API | Python 3.12 + FastAPI |
| Exchange entegrasyonu | CCXT (Binance, iCrypex) |
| Blockchain entegrasyonu | web3.py (Sonic SFC, Avalanche C-Chain, Ethereum) |
| Avalanche P-Chain | httpx + Avalanche REST API |
| TEFAS scraping | httpx + BeautifulSoup4 |
| BES | Manuel giriş (ilerleyen fazda scraping) |
| Zamanlayıcı | APScheduler |
| Veritabanı | PostgreSQL + SQLAlchemy (async) + Alembic |
| AI tavsiye | Anthropic Python SDK (Claude API) |
| Frontend | Next.js |
| Auth | JWT (python-jose) |

## Proje Yapısı

```
KFinans/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI router'ları (v1/)
│   │   ├── services/
│   │   │   ├── exchange/       # CCXT tabanlı (Binance, iCrypex)
│   │   │   ├── blockchain/     # web3.py tabanlı
│   │   │   │   ├── sonic.py        # SFC staking contract
│   │   │   │   ├── avalanche.py    # P-Chain + C-Chain
│   │   │   │   └── ethereum.py
│   │   │   ├── tefas.py
│   │   │   ├── bes.py
│   │   │   ├── aggregator.py   # Portföy birleştirme + TL normalize + staking ayrımı
│   │   │   └── advisor.py      # Claude API entegrasyonu
│   │   ├── models/       # SQLAlchemy modelleri
│   │   ├── schemas/      # Pydantic şemaları
│   │   ├── scheduler.py  # APScheduler — Pazar 23:00 haftalık snapshot
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
└── frontend/             # Next.js
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

**Scheduler:** APScheduler her Pazar 23:00'de çalışır, haftanın son değerlerini `portfolio_snapshots` tablosuna yazar. Haftalık değişim bu tablo üzerinden hesaplanır.

**API key güvenliği:** Binance/iCrypex anahtarları DB'de `cryptography` kütüphanesi ile Fernet şifrelemeli saklanır, `.env`'deki master key ile açılır.

**BES — ilk faz:** Manuel giriş endpointi + tablo. Scraping planlanırken `bes.py` soyut bir base class olarak yazılır.

**Tavsiye motoru:** `advisor.py` portföy dağılımını, haftalık/aylık değişimleri ve kullanıcının risk profilini Claude'a yapılandırılmış prompt olarak gönderir; yanıtı parse edip DB'ye kaydeder.

## Geliştirme Kuralları

- Tüm dokümantasyon ve commit mesajları Türkçe
- Kod içi identifier ve yorumlar İngilizce
- Her veri kaynağı servisi `fetch()` metodunu implement eden soyut `BaseIntegration` sınıfından türer
- Secrets asla koda yazılmaz, sadece `.env` üzerinden `pydantic-settings` ile okunur
