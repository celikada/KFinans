# KFinans Backend

FastAPI tabanlı async Python backend. Tüm finansal veri kaynaklarını (TEFAS, Binance, iCrypex, Yahoo Finance, blockchain, TCMB, MKK e-Yatırımcı) toplar, Claude API ile yatırım tavsiyesi üretir.

→ Genel proje açıklaması için [üst seviye README](../README.md).
→ Detaylı API referansı için [`docs/03-api-referansi.md`](../docs/03-api-referansi.md).

---

## Kurulum

```bash
cd backend

# Bağımlılıklar (dev araçlar dahil)
pip install -e ".[dev]"

# Ortam değişkenleri
cp .env.example .env
# .env dosyasını düzenle: DATABASE_URL, SECRET_KEY, FERNET_KEY,
# ANTHROPIC_API_KEY, RESEND_API_KEY, INFURA_API_KEY, vb.

# Veritabanı migration
alembic upgrade head

# Geliştirme sunucusu
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API dokümantasyonu: http://localhost:8000/docs (Swagger UI) · http://localhost:8000/redoc

---

## Proje Yapısı

```
backend/
├── app/
│   ├── api/v1/          # FastAPI router'ları (23 router) + main.py'de /health
│   │   ├── auth.py      # /auth/login (MFA union), register, verify-email, logout, refresh, forgot/reset-password
│   │   ├── mfa.py       # /mfa/setup, enable, verify, disable (TOTP)
│   │   ├── user.py      # /user/me, profile, password, account, email change, data-export, anthropic-consent
│   │   ├── portfolio.py # /portfolio snapshot, history, changes, breakdown, crypto, wallets, staking
│   │   ├── tefas.py     # TEFAS holdings + MKK import
│   │   ├── stocks.py    # Hisse senedi + MKK import
│   │   ├── wallets.py   # Blockchain cüzdanlar + maskeli/şifreli export
│   │   ├── integrations.py # Exchange API key (Fernet) + şifreli export/import
│   │   ├── manual_crypto.py # API'siz borsalar için manuel kripto
│   │   ├── bes.py       # Bireysel emeklilik
│   │   ├── commodity.py # Altın & gümüş (gram/BiGA/sikke)
│   │   ├── expenses.py  # Harcamalar + Excel I/O
│   │   ├── income.py    # Gelirler + periyodik gelir realize
│   │   ├── planned_expenses.py # Planlı ödemeler
│   │   ├── cash.py      # Nakit / banka hesabı
│   │   ├── cash_flow.py # 12 aylık nakit akış projeksiyonu + rapor
│   │   ├── credit_cards.py # Kredi kartı + ekstre + taksit (nested)
│   │   ├── budget.py    # Bütçe limitleri + karşılaştırma
│   │   ├── goal.py      # Finansal özgürlük hedefi
│   │   ├── asset_catalog.py # Manuel kripto autocomplete
│   │   ├── advice.py    # Claude AI tavsiye (kredi tüketir)
│   │   ├── audit_logs.py # Audit log (pagination)
│   │   ├── metrics.py   # Performans metrikleri (token korumalı)
│   │   └── router.py    # Tüm router'ları birleştirir
│   ├── services/
│   │   ├── exchange/    # CCXT — Binance, iCrypex
│   │   ├── blockchain/  # web3.py — Sonic, Avalanche, Ethereum
│   │   ├── tefas.py     # TEFAS resmi export API
│   │   ├── stocks.py    # Yahoo Finance Chart API
│   │   ├── commodity.py # XAU/XAG fiyat + 5dk cache
│   │   ├── aggregator.py # TL normalizasyon + döviz kuru
│   │   ├── snapshot.py  # Tüm kaynaklardan snapshot üretir
│   │   ├── advisor.py   # Anthropic SDK + prompt engineering
│   │   └── email.py     # Resend SDK
│   ├── models/          # SQLAlchemy
│   ├── schemas/         # Pydantic v2
│   ├── core/            # deps (get_db, get_current_user), security (Fernet, JWT, bcrypt), limiter, middleware, masking
│   ├── database.py      # async engine + AsyncSessionLocal (session factory)
│   ├── scheduler.py     # APScheduler — 4 cron (Pazar 23:00 snapshot, 03:00 token cleanup, 04:00 hard-delete, 04:30 audit purge)
│   ├── config.py        # pydantic-settings
│   └── main.py          # FastAPI app + middleware + CORS
├── alembic/versions/    # Migration zinciri
├── tests/
│   ├── unit/            # Servis ve şema testleri
│   └── integration/     # Endpoint testleri (httpx + respx)
└── pyproject.toml
```

---

## Test

```bash
pytest                                       # tüm testler
pytest tests/unit/test_advisor.py            # tek dosya
pytest -k "test_aggregator"                  # isim filtresi
pytest --cov=app --cov-report=html           # coverage raporu
```

Test mantığı:
- **Unit:** `services/`, `schemas/`, hesaplama mantığı (mock'lanmış HTTP çağrıları)
- **Integration:** Endpoint testleri (gerçek DB + httpx test client + respx ile dış API mock)
- Coverage: backend ~%95.8 gerçekleşen; SonarQube `new_coverage` gate eşiği %80 (BLOCKING)

---

## Mimari Kararlar

- **Async by default:** Tüm DB işlemleri SQLAlchemy AsyncSession; HTTP istemcisi httpx async.
- **API key güvenliği:** Borsa anahtarları DB'de Fernet ile şifrelidir; `.env`'deki `FERNET_KEY` ile açılır.
- **Snapshot sistemi:** APScheduler her Pazar 23:00 tüm aktif kullanıcılar için `compute_and_save_snapshot` çalıştırır. Manuel "Snapshot al" butonu aynı fonksiyonu çağırır. Aynı gün içinde idempotent (eski silinir, yenisi oluşur).
- **Maliyet bazı:** `stock_holdings.avg_cost_tl` ve `tefas_holdings.avg_cost_tl` (nullable Numeric 18,6). Boş = "maliyet bilinmiyor", kâr/zarar atlanır.
- **Distributor (kurum):** TEFAS ve hisse holdings'te `distributor` kolonu — aynı kodu farklı kurumlardan ayrı satır olarak izleme.
- **MKK import:** `xlrd==1.2.0` ile eski .xls binary parse edilir. Header'ı "Üye" sütunundan otomatik tespit. TEFAS için `Kıymet Sınıfı = Fon`, hisse için `HS + Ek Tanım = A` filtresi.
- **Fault tolerance:** Yahoo Finance gold/silver fail ederse fiyat 0 dönülür, sayfa açılmaya devam eder, frontend uyarı banner gösterir. TCMB USD/TRY kritik (fail ederse hata).

---

## Önemli Komutlar

```bash
# Yeni migration oluştur
alembic revision --autogenerate -m "açıklama"

# Migration uygula / geri al
alembic upgrade head
alembic downgrade -1

# Lint + format (zorunlu, CI gate'i)
ruff check .
ruff format .

# Manuel snapshot tetikle (debug)
docker compose exec backend python -c "
import asyncio
from app.services.snapshot import compute_and_save_snapshot
from app.database import AsyncSessionLocal
async def run(uid):
    async with AsyncSessionLocal() as db:
        await compute_and_save_snapshot(uid, db)
asyncio.run(run('USER-UUID-HERE'))
"
```

---

## .env Değişkenleri

| Değişken | Açıklama |
|---|---|
| `DATABASE_URL` | postgres+asyncpg://user:pass@host:5432/db |
| `SECRET_KEY` | JWT imza anahtarı (32+ byte rastgele) |
| `FERNET_KEY` | API key şifreleme (32 byte base64) |
| `ANTHROPIC_API_KEY` | Claude API anahtarı |
| `RESEND_API_KEY` | E-posta servisi |
| `EMAIL_FROM` | Gönderici adresi |
| `FRONTEND_URL` | E-posta içindeki link prefix |
| `INFURA_API_KEY` | Ethereum RPC |
| `SONIC_RPC_URL` | Sonic chain RPC |
| `AVALANCHE_C_RPC_URL` | Avalanche C-Chain |
| `AVALANCHE_P_API_URL` | Avalanche P-Chain (httpx) |
| `VERIFY_TOKEN_EXPIRE_HOURS` | E-posta doğrulama linki süresi (varsayılan 24) |
