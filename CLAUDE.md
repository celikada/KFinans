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
| Avalanche P-Chain | httpx + Avalanche REST API |
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
│   │   │                          # manual_crypto, advice)
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
│   │   │   └── advisor.py         # Claude API (Faz 3'te aktive olacak)
│   │   ├── models/                # SQLAlchemy ORM (manual_crypto.py dahil)
│   │   ├── schemas/               # Pydantic (manual_crypto.py dahil)
│   │   ├── core/                  # security, deps, limiter
│   │   ├── scheduler.py           # APScheduler — Pazar 23:00 haftalık snapshot
│   │   └── main.py
│   ├── alembic/versions/          # 22 migration (f5a6b7c8d9e0 = manual_crypto_holdings)
│   ├── tests/{unit,integration}/  # tests/integration/test_manual_crypto_api.py (12 test)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/                      # Next.js 16 (App Router, proxy.ts auth yönlendirme)
│   ├── app/_components/{Logos,MkkHint,PageHeader}.tsx
│   ├── app/dashboard/{tefas,stocks,wallets,crypto,manual-crypto,bes,expenses,planned,
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

**Snapshot timezone:** `services/snapshot.py` `snapshot_date` belirlerken `datetime.now(ZoneInfo("Europe/Istanbul")).date()` kullanır (UTC tabanlı `date.today()` değil). Backend Docker container UTC'de çalıştığı için Türkiye saatine göre 00:00–03:00 arası alınan ad-hoc snapshot'lar bir önceki güne yazılıyordu — düzeltildi. Scheduler zaten `Europe/Istanbul` ile çalışıyordu; manuel tetikleme ile tutarlı.

**Snapshot silme:** `DELETE /portfolio/snapshot/{snapshot_date}` (ISO date path param) yanlış kaydedilmiş snapshot'ları temizler; cascade ile `asset_positions` de silinir, `current_user.id` filtresi IDOR koruması sağlar.

**Wallet pricing tutarlılığı:** `GET /portfolio/wallets` `total_value_tl` hesaplarken `liquid + staked + pending_rewards` toplar (snapshot servisiyle aynı formül). Sonic SFC validator rewards ve Avalanche P-Chain pending rewards her zaman dahildir; dashboard "Toplam Portföy" ile snapshot tutarı arasında fark oluşmaz.

**API key güvenliği:** Binance/iCrypex anahtarları DB'de `cryptography` kütüphanesi ile Fernet şifrelemeli saklanır, `.env`'deki master key ile açılır.

**BES:** Manuel giriş + Excel import/export. 4 metric (yatırılan ana para + getirisi, devlet katkısı + getirisi). Snapshot servisi `_gather_bes_assets()` ile `asset_type="pension"` olarak entegre eder.

**Fault-tolerance pattern:** Dış servisler **kritik** ve **best-effort** olarak ayrılır. TCMB USD/TRY kritik (fail → 503); GBP/USD opsiyonel (fail → 0 + log warning). Yahoo Finance metal sembolleri için fallback chain (XAU=X→GC=F, XAG=X→SI=F); ikisi de fail ise 0 dön + UI uyarı banner. Cache TTL Yahoo fail durumunda 5 dk → 30 sn'ye düşer (geçici 404 hızla telafi edilir).

**Multi-RPC fallback (EVM zincirler):** Ethereum ve Avalanche C-Chain `settings.{ethereum,avalanche_c}_rpc_url` → publicnode → merkle → 1rpc → ankr → drpc sırasıyla denenir; upstream patladığında self-heal sağlar. Servisler ilk başarılı RPC'yi seçer.

**Bitcoin xpub cache + single-flight:** `bitcoin.py` modül seviyesinde `_BALANCE_CACHE` (10 dk TTL) ve `_INFLIGHT` dict + `asyncio.Future` tutar. Dashboard yenileme rate limit'e takılmasın diye paralel cache miss'lerde tek tarama paylaşılır; tüm metal 0 dönerse TTL 30 sn'ye düşer (geçici 404 hızla recovery).

**Ethereum ERC-20 token discovery (Ethplorer):** Ethereum mainnet için `evm_tokens.py::fetch_ethereum_tokens_via_ethplorer()` `api.ethplorer.io` free tier (key='freekey', ~50 istek/gün) ile kullanıcının tüm ERC-20 token bakiyelerini dinamik bulur. **Spam filter:** domain TLD'leri (.io/.com/.finance), Cherokee/Math Alphanumeric Unicode spoofing, "Visit/claim rewards" pattern'leri ve >1e12 miktar token'lar `_looks_like_spam()` ile atılır. Avalanche C-Chain için curated `AVALANCHE_C_TOKENS` (sAVAX, USDT.e, USDC.e) — sequential `balanceOf` (Infura/RPC rate limit), 3 retry + 0.5 sn backoff.

**422 Validation log handler:** `main.py` `RequestValidationError` exception handler 422 hata detayını (`exc.errors()`) log'a yazar; frontend'e mevcut formatta dönüş — debug ipucu.

**MKK e-Yatırımcı Excel import:** `xlrd 1.2.0` ile eski .xls binary parse. Header satırı "Üye" sütunundan otomatik tespit. Sınıfa göre filtre: TEFAS için `Kıymet Sınıfı=Fon`, hisse için `Kıymet Sınıfı=HS AND Ek Tanım=A`. BIST kodları otomatik `.IS` suffix ile Yahoo Finance ticker'ına çevrilir. Mevcut kayıtlar replace-all silinir.

**Distributor (aracı kurum) alanı:** TEFAS + Stocks holding'lerinde aynı varlığı (örn. ZJI fonu) farklı kurumlardan (Ziraat + Foneria) ayrı satır olarak izlemek için `distributor` (VARCHAR 50). MKK Üye sütunu otomatik bu alana yazılır.

**Maliyet bazı (avg_cost_tl):** TEFAS + Stocks `avg_cost_tl` (Numeric 18,6 nullable) — TRY/adet ortalama maliyet. Schema validator: 0 veya negatif → None (kullanıcı bilmiyorsa boş bırakabilir). Preview/list'te `cost_basis_tl`, `gain_loss_tl`, `gain_loss_pct` hesaplanır.

**Manuel kripto (API'siz borsalar):** API erişimi olmayan borsalar (BinanceTR, iCrypex, BTCTurk, Paribu, Bybit, KuCoin, Bitget vb.) için kullanıcının manuel kayıt yapabildiği `manual_crypto_holdings` tablosu. Endpoint prefix `/manual-crypto`; CRUD + Excel import/export + anlık fiyatla zenginleştirilmiş listeleme. Fiyatlama `aggregator.fetch_spot_prices()` (Binance USDT) + `fetch_usd_to_tl()` (TCMB) ile yapılır; Binance'te bulunmayan semboller `unknown_symbols` listesinde döner ve TL değer 0 olur. Snapshot entegrasyonu `services/snapshot.py::_gather_manual_crypto_assets()` — `asset_type="crypto"`, `provider="manual:{exchange}"` (örn. `manual:icrypex`). Fiyat enjekte edilmez; `compute_and_save_snapshot()` içindeki ortak fiyat enrichment loop'u (`SYMBOL_PRICE_ALIASES` dahil) bu kayıtları da yakalar — zincir/exchange kayıtlarıyla aynı pipeline.

**Avalanche P-Chain likit bakiye:** `AvalanchePChainService.fetch()` daha önce sadece `platform.getStake` çağırıyordu, bu yüzden likit (unlocked) bakiye gözükmüyordu. Şimdi `platform.getBalance` + `platform.getStake` paralel çağrılıyor; adres `P-` prefix'i ile gönderiliyor (`avax1...` → `P-avax1...`). `unlockeds` (yeni API: assetID→amount mapping) veya `unlocked` (eski API tekil) → `liquid_quantity`; `lockedStakeables` + `staked` → `staked_quantity`. `asset_type` staked > liquid ise `staked_crypto`, değilse `crypto` olarak set edilir.

**Soft-delete:** `DELETE /user/me` `users.deleted_at = now()` set eder; hard-delete cron job (30 gün sonra fiziksel silme) Faz 3 TODO.

**Tavsiye motoru:** `advisor.py` portföy dağılımını, haftalık/aylık değişimleri ve kullanıcının risk profilini Claude'a yapılandırılmış prompt olarak gönderir; yanıtı parse edip DB'ye kaydeder. Faz 3'te kredi tüketimli olarak aktive olacak.

## Geliştirme Kuralları

- Tüm dokümantasyon ve commit mesajları Türkçe
- Kod içi identifier ve yorumlar İngilizce
- Her veri kaynağı servisi `fetch()` metodunu implement eden soyut `BaseIntegration` sınıfından türer
- Secrets asla koda yazılmaz, sadece `.env` üzerinden `pydantic-settings` ile okunur
