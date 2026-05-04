# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proje Hakkında

KFinans, kişisel yatırım portföyünü tek ekranda toplayan bir uygulamadır. Binance ve iCrypex kripto hesapları, TEFAS yatırım fonları, hisse senedi (Yahoo Finance), kıymetli madenler (altın/gümüş), BES birikimleri ve blockchain cüzdanları (Sonic, Avalanche, Ethereum, Bitcoin) tek ekranda toplanır. Manuel harcama, gelir, planlı ödeme ve bütçe takibi modülleri Faz 3 ile eklendi. Haftalık snapshot servisi değişimleri hesaplar; Claude API aracılığıyla orta/uzun vadeli yatırım tavsiyeleri (Faz 3) sunulacaktır.

## Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend API | Python 3.12 + FastAPI |
| Exchange entegrasyonu | CCXT (Binance, iCrypex) |
| Blockchain entegrasyonu | web3.py (Sonic SFC, Avalanche C-Chain, Ethereum) |
| Avalanche P-Chain | httpx + Avalanche REST API |
| Bitcoin | httpx + mempool.space public API (no key) + bip-utils (xpub HD derivation) |
| TEFAS | httpx + JSON API |
| Hisse senedi | Yahoo Finance Chart API (httpx) |
| Kıymetli madenler | TCMB USD/TRY + Yahoo Finance XAU=X / XAG=X (GC=F / SI=F fallback) |
| MKK Excel import | xlrd 1.2.0 (eski .xls binary) |
| BES | Manuel giriş + Excel |
| Zamanlayıcı | APScheduler |
| Veritabanı | PostgreSQL + SQLAlchemy (async) + Alembic |
| AI tavsiye | Anthropic Python SDK (Claude API) |
| Frontend | Next.js 16 (App Router, Turbopack) + React 19 + Tailwind CSS v4 |
| Auth | JWT (python-jose) + slowapi rate limiting |
| Güvenlik | Fernet (API key) + bcrypt (şifre) + JWT blacklist (revoked_tokens) |

## Proje Yapısı

```
KFinans/
├── backend/
│   ├── app/
│   │   ├── api/v1/                # FastAPI router'ları (auth, user, portfolio, tefas,
│   │   │                          # stocks, bes, commodity, wallets, integrations,
│   │   │                          # expenses, planned_expenses, income, budget, goal,
│   │   │                          # advice)
│   │   ├── services/
│   │   │   ├── exchange/          # CCXT tabanlı (Binance, iCrypex, BinanceTR)
│   │   │   ├── blockchain/        # Sonic SFC, Avalanche P/C, Ethereum (web3.py) + Bitcoin (mempool.space)
│   │   │   ├── tefas.py
│   │   │   ├── stocks.py
│   │   │   ├── commodity.py       # TCMB + Yahoo XAU/XAG fallback chain + 5 dk cache
│   │   │   ├── aggregator.py      # TL normalize, USD/TRY, breakdown
│   │   │   ├── snapshot.py        # compute_and_save_snapshot() — paralel toplama
│   │   │   ├── email.py           # Resend SDK — verify_email
│   │   │   └── advisor.py         # Claude API (Faz 3'te aktive olacak)
│   │   ├── models/                # SQLAlchemy ORM
│   │   ├── schemas/               # Pydantic
│   │   ├── core/                  # security, deps, limiter
│   │   ├── scheduler.py           # APScheduler — Pazar 23:00 haftalık snapshot
│   │   └── main.py
│   ├── alembic/versions/          # 21 migration
│   ├── tests/{unit,integration}/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/                      # Next.js 16 (App Router, proxy.ts auth yönlendirme)
│   ├── app/_components/{Logos,MkkHint,PageHeader}.tsx
│   ├── app/dashboard/{tefas,stocks,wallets,crypto,bes,expenses,planned,
│   │                  income,budget,commodities,goal,settings,history}/
│   └── lib/{api,format}.ts
├── docs/                          # 9 sıralı belge (01-tasarim ... 09-altyapi-test)
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

**Scheduler:** APScheduler her Pazar 23:00'de çalışır, haftanın son değerlerini `portfolio_snapshots` tablosuna yazar. Haftalık değişim bu tablo üzerinden hesaplanır. **MKK Excel import sonrası** snapshot best-effort olarak ayrıca tetiklenir (try/except — fail olsa bile import korunur).

**API key güvenliği:** Binance/iCrypex anahtarları DB'de `cryptography` kütüphanesi ile Fernet şifrelemeli saklanır, `.env`'deki master key ile açılır.

**BES:** Manuel giriş + Excel import/export. 4 metric (yatırılan ana para + getirisi, devlet katkısı + getirisi). Snapshot servisi `_gather_bes_assets()` ile `asset_type="pension"` olarak entegre eder.

**Fault-tolerance pattern:** Dış servisler **kritik** ve **best-effort** olarak ayrılır. TCMB USD/TRY kritik (fail → 503); GBP/USD opsiyonel (fail → 0 + log warning). Yahoo Finance metal sembolleri için fallback chain (XAU=X→GC=F, XAG=X→SI=F); ikisi de fail ise 0 dön + UI uyarı banner. Cache TTL Yahoo fail durumunda 5 dk → 30 sn'ye düşer (geçici 404 hızla telafi edilir).

**MKK e-Yatırımcı Excel import:** `xlrd 1.2.0` ile eski .xls binary parse. Header satırı "Üye" sütunundan otomatik tespit. Sınıfa göre filtre: TEFAS için `Kıymet Sınıfı=Fon`, hisse için `Kıymet Sınıfı=HS AND Ek Tanım=A`. BIST kodları otomatik `.IS` suffix ile Yahoo Finance ticker'ına çevrilir. Mevcut kayıtlar replace-all silinir.

**Distributor (aracı kurum) alanı:** TEFAS + Stocks holding'lerinde aynı varlığı (örn. ZJI fonu) farklı kurumlardan (Ziraat + Foneria) ayrı satır olarak izlemek için `distributor` (VARCHAR 50). MKK Üye sütunu otomatik bu alana yazılır.

**Maliyet bazı (avg_cost_tl):** TEFAS + Stocks `avg_cost_tl` (Numeric 18,6 nullable) — TRY/adet ortalama maliyet. Schema validator: 0 veya negatif → None (kullanıcı bilmiyorsa boş bırakabilir). Preview/list'te `cost_basis_tl`, `gain_loss_tl`, `gain_loss_pct` hesaplanır.

**Soft-delete:** `DELETE /user/me` `users.deleted_at = now()` set eder; hard-delete cron job (30 gün sonra fiziksel silme) Faz 3 TODO.

**Tavsiye motoru:** `advisor.py` portföy dağılımını, haftalık/aylık değişimleri ve kullanıcının risk profilini Claude'a yapılandırılmış prompt olarak gönderir; yanıtı parse edip DB'ye kaydeder. Faz 3'te kredi tüketimli olarak aktive olacak.

## Geliştirme Kuralları

- Tüm dokümantasyon ve commit mesajları Türkçe
- Kod içi identifier ve yorumlar İngilizce
- Her veri kaynağı servisi `fetch()` metodunu implement eden soyut `BaseIntegration` sınıfından türer
- Secrets asla koda yazılmaz, sadece `.env` üzerinden `pydantic-settings` ile okunur
