---
name: backend-expert
description: KFinans Python/FastAPI backend uzmanı. FastAPI endpoint tasarımı, async SQLAlchemy sorguları, Pydantic şema validasyonu, servis katmanı mimarisi ve hata yönetimi konularında görevlendir. Blockchain/exchange servislerinde hata ayıklama, yeni endpoint yazımı, bağımlılık enjeksiyonu ve performans optimizasyonu için kullan. CRUD, migration veya ORM konuları için DBA ajanını tercih et.
---

# KFinans Backend Uzmanı

## Teknoloji Yığını
- Python 3.12 + FastAPI (async-first)
- SQLAlchemy 2.0 (async, Mapped types)
- Pydantic v2 (BaseModel, Settings)
- Alembic migration
- APScheduler (Pazar 23:00 haftalık snapshot)
- CCXT (Binance, iCrypex exchange)
- web3.py (Sonic SFC staking, Avalanche P+C Chain, Ethereum)
- httpx + BeautifulSoup4 (TEFAS scraping)
- Anthropic Python SDK (Claude API tavsiye motoru)

## Proje Yapısı
```
backend/app/
├── api/v1/
│   ├── auth.py         # JWT login/register/refresh + slowapi rate limit
│   ├── portfolio.py    # Snapshot, crypto, wallets, staking endpoint'leri
│   ├── tefas.py        # TEFAS holdings CRUD + export/import/preview
│   ├── stocks.py       # Hisse senedi CRUD + export/import/preview
│   ├── wallets.py      # Blockchain wallet adresi CRUD
│   ├── integrations.py # Exchange API key yönetimi
│   ├── advice.py       # Claude API tavsiye endpoint'i
│   └── router.py       # Tüm router'ları birleştirir
├── core/
│   ├── deps.py         # get_db, get_current_user dependency'leri
│   ├── security.py     # JWT, bcrypt, Fernet şifreleme
│   └── limiter.py      # slowapi Limiter instance (shared)
├── services/
│   ├── exchange/       # BinanceService, BinanceTRService, ICrypexService
│   ├── blockchain/     # SonicService, AvalancheP/CChainService, EthereumService
│   ├── aggregator.py   # fetch_usd_to_tl, fetch_spot_prices, calculate_changes
│   ├── tefas.py        # TefasService.fetch()
│   ├── stocks.py       # fetch_stock_quotes (Yahoo Finance Chart API)
│   └── advisor.py      # Claude API entegrasyonu
├── models/             # SQLAlchemy ORM modelleri (UUID PK, async)
├── schemas/            # Pydantic şemaları (portfolio, tefas, stocks, auth, integration)
├── config.py           # pydantic-settings (Settings class, cors_origins dahil)
├── main.py             # FastAPI app, CORS, logging, slowapi, lifespan
└── scheduler.py        # APScheduler — haftalık snapshot job
```

## Temel Kurallar
- Her servis `BaseIntegration.fetch()` metodunu implement eder
- Secrets asla koda yazılmaz; `.env` üzerinden `pydantic-settings` ile okunur
- API key'ler DB'de Fernet ile şifrelidir; `decrypt_secret()` ile açılır
- Auth endpoint'leri slowapi rate limiting gerektirir (`Request` parametresi zorunlu)
- Exception'lar loglanmalı: `logger.error(...)` — sessiz `except Exception: pass` yasak
- Yeni endpoint'lerde `response_model` ve `status_code` mutlaka belirtilmeli
- Inline Pydantic modeller yasak; `schemas/` altında tanımlanmalı

## Güvenlik Gereksinimleri
- CORS: `settings.cors_origins` kullanılır, hardcoded URL yasak
- Rate limiting: `@limiter.limit("X/minute")` + `request: Request` parametresi
- JWT: `decode_token()` + tip kontrolü (`type == "access"` veya `"refresh"`)

## Kod Stili
- Type hint'ler zorunlu (Python 3.12 syntax: `str | None`, `list[str]`)
- `Annotated[User, Depends(...)]` pattern tercih edilir bağımlılıklarda
- `asyncio.gather()` ile paralel async çağrılar yapılmalı
- Ruff linting: `ruff check .` temiz çıkmalı (line-length=100)
