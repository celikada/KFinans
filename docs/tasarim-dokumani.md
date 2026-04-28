# KFinans — Sistem Tasarım Dokümanı

**Versiyon:** 1.1  
**Tarih:** 2026-04-27  
**Durum:** Tasarım aşaması

---

## 1. Genel Bakış

KFinans, kişisel finansı tek ekranda yöneten iki fazlı bir uygulamadır.

| Faz | Kapsam | Durum |
|-----|--------|-------|
| Faz 1 | Yatırım takibi, haftalık değişim, AI tavsiye | Öncelikli |
| Faz 2 | Harcama takibi, kategori analizi, bütçe | Planlı |

---

## 2. Faz 1 — Yatırım Takibi

### 2.1 Veri Kaynakları

İki farklı entegrasyon türü vardır: **Exchange** (API key ile) ve **Blockchain** (public adres ile).

#### Exchange Entegrasyonları

| Kaynak | Yöntem | Kütüphane | Zorluk |
|--------|--------|-----------|--------|
| Binance | REST API (API key + secret) | CCXT | Düşük |
| iCrypex | REST API (API key + secret) | CCXT | Düşük |
| TEFAS | Web scraping / HTML parse | httpx + BS4 | Orta |
| BES | Manuel giriş (Faz 1) / Scraping (Faz 2) | — | Düşük (manuel) |

#### Blockchain Entegrasyonları (Ledger + DeFi)

Ledger bir donanım cüzdanı olduğundan kendi API'si yoktur. Varlıklar ilgili blockchain üzerinde yaşar; **public cüzdan adresi** yeterlidir — özel anahtar asla sisteme girmez.

| Kaynak | Zincir | Yöntem | Kütüphane | Zorluk |
|--------|--------|--------|-----------|--------|
| Sonic Labs | Sonic (EVM) | RPC + SFC staking contract | web3.py | Orta |
| Core.app | Avalanche P-Chain | Avalanche REST API | httpx | Orta |
| Core.app | Avalanche C-Chain | EVM RPC | web3.py | Düşük |
| Ledger / Genel | Ethereum | EVM RPC + Etherscan API | web3.py + httpx | Düşük |

**Sonic Staking Detayı:**
- Sonic SFC (Special Fee Contract) üzerinden S token stake
- `getStake(delegator, validatorId)` → stake miktarı
- `pendingRewards(delegator, validatorId)` → birikmiş ödül
- RPC: `https://rpc.soniclabs.com`

**Avalanche Staking Detayı:**
- P-Chain staking `platform.getStake` API ile sorgulanır
- Endpoint: `POST https://api.avax.network/ext/bc/P`
- P-Chain adresi (P-avax1...) ve C-Chain adresi (0x...) ayrıdır
- C-Chain bakiyesi web3.py ile standart EVM sorgusu

### 2.2 Temel Özellikler

- Her kaynaktan portföy verisi çekme (exchange + blockchain)
- Stake edilmiş varlıkları liquid bakiyeden ayrı gösterme
- Bekleyen staking ödüllerini (pending rewards) ayrıca takip etme
- Tüm varlıkları TL'ye normalize etme (anlık kur: Binance veya TCMB)
- Her Pazar 23:00'de otomatik haftalık snapshot alma
- Hafta-üstü-hafta (WoW) ve ay-üstü-ay (MoM) değişim hesaplama
- Portföy dağılımı (kripto / staked kripto / fon / BES yüzdesi)
- Claude API ile orta (3-12 ay) ve uzun (1-3 yıl) vade tavsiye üretimi

---

## 3. Faz 2 — Harcama Takibi

### 3.1 Temel Özellikler

- Manuel harcama girişi (tutar, kategori, tarih, not)
- Özelleştirilebilir kategori yönetimi (kira, market, ulaşım vb.)
- Aylık/yıllık harcama özeti
- Kategori bazlı kırılım ve trend analizi
- Bütçe limiti tanımlama ve limit aşım uyarısı
- Claude API ile harcama alışkanlığı analizi ve tasarruf önerileri

### 3.2 İlerleyen Alt Fazlar

- Banka ekstresi import (CSV/Excel parse)
- Tekrarlayan ödeme tespiti (abonelikler)
- Harcama/yatırım dengesi analizi (her iki fazı birleştirir)

---

## 4. Sistem Mimarisi

```
┌──────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│                                                      │
│  ── Faz 1 Ekranları ──────────────────────────────  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Portföy  │  │ Haftalık │  │ Staking Paneli   │   │
│  │Dashboard │  │ Değişim  │  │ (S / AVAX ödül)  │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────┐    │
│  │         Yatırım Tavsiye Paneli               │    │
│  │   (orta vade / uzun vade — Claude çıktısı)   │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ── Faz 2 Ekranları ──────────────────────────────  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Harcama  │  │ Kategori │  │  Bütçe Takibi    │   │
│  │ Girişi   │  │ Yönetimi │  │  (limit/durum)   │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────┐    │
│  │       Harcama Analiz Dashboard'u             │    │
│  │  Aylık trend / Kategori pasta grafik /       │    │
│  │  Claude tasarruf önerileri                   │    │
│  └──────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────┐    │
│  │    Yatırım ↔ Harcama Denge Ekranı (2c)       │    │
│  │  Toplam gelir tahmini / tasarruf oranı /     │    │
│  │  yatırıma aktarılabilir tutar                │    │
│  └──────────────────────────────────────────────┘    │
└───────────────────────┬──────────────────────────────┘
                        │ HTTPS / REST
┌───────────────────────▼──────────────────────────────┐
│              FastAPI Backend (Modüler)               │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │                  API Layer                   │   │
│  │  /api/v1/portfolio   /api/v1/wallets         │   │
│  │  /api/v1/advice      /api/v1/expenses        │   │
│  └────────────────────┬─────────────────────────┘   │
│                       │                              │
│  ┌────────────────────▼─────────────────────────┐   │
│  │               Service Layer                  │   │
│  │                                              │   │
│  │  ── Exchange Servisleri ──────────────────   │   │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────┐    │   │
│  │  │ Binance │  │ iCrypex │  │  TEFAS   │    │   │
│  │  │ (CCXT)  │  │ (CCXT)  │  │(scraping)│    │   │
│  │  └────┬────┘  └────┬────┘  └────┬─────┘    │   │
│  │       │            │            │           │   │
│  │  ── Blockchain Servisleri ────────────────  │   │
│  │  ┌──────────┐  ┌──────────────────────┐    │   │
│  │  │  Sonic   │  │      Avalanche       │    │   │
│  │  │ Service  │  │      Service         │    │   │
│  │  │(web3.py) │  │(P-Chain + C-Chain)   │    │   │
│  │  │SFC stake │  │platform.getStake     │    │   │
│  │  └────┬─────┘  └──────────┬───────────┘    │   │
│  │       │                   │                 │   │
│  │       └─────────┬─────────┘                 │   │
│  │                 │                            │   │
│  │        ┌────────▼────────┐                  │   │
│  │        │   Aggregator    │                  │   │
│  │        │    Service      │                  │   │
│  │        │ TL normalize    │                  │   │
│  │        │ stake ayrımı    │                  │   │
│  │        └────────┬────────┘                  │   │
│  │                 │                            │   │
│  │       ┌─────────▼──────┐                    │   │
│  │       │ Advisor Service│                    │   │
│  │       │  (Claude API)  │                    │   │
│  │       └────────────────┘                    │   │
│  │                                              │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │         Expense Service (Faz 2)      │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  APScheduler — Pazar 23:00 haftalık snapshot │   │
│  └──────────────────────────────────────────────┘   │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│                    PostgreSQL                        │
└──────────────────────────────────────────────────────┘
```

**Neden modüler monolit?**
Kişisel uygulama ölçeğinde mikroservis karmaşıklığı gereksizdir. Modüler yapı ileride servis ayırımını kolaylaştırır ama tek process olarak çalışır.

---

## 5. Veritabanı Şeması

### 5.1 Kullanıcı

```sql
users
  id            UUID PK
  email         TEXT UNIQUE
  password_hash TEXT
  risk_profile  ENUM('conservative','balanced','aggressive')
  created_at    TIMESTAMPTZ
```

### 5.2 Entegrasyon Kimlik Bilgileri (Exchange)

```sql
-- Binance, iCrypex gibi API key gerektiren kaynaklar
integrations
  id               UUID PK
  user_id          UUID FK → users
  provider         ENUM('binance','icrypex','tefas','bes')
  encrypted_key    TEXT        -- Fernet ile şifreli
  encrypted_secret TEXT        -- Fernet ile şifreli
  is_active        BOOLEAN
  last_synced_at   TIMESTAMPTZ
  created_at       TIMESTAMPTZ
```

### 5.3 Blockchain Cüzdan Adresleri (Ledger / DeFi)

```sql
-- Public adresler — özel anahtar asla saklanmaz
wallet_addresses
  id         UUID PK
  user_id    UUID FK → users
  chain      ENUM('ethereum','sonic','avalanche_c','avalanche_p')
  address    TEXT        -- 0x... (EVM) veya P-avax1... (Avalanche P-Chain)
  label      TEXT        -- "Ledger Ana Cüzdan", "Ledger 2. Cüzdan" vb.
  is_active  BOOLEAN
  created_at TIMESTAMPTZ
  UNIQUE(user_id, chain, address)
```

### 5.4 Portföy Snapshot

```sql
-- Haftalık portföy anlık görüntüsü
portfolio_snapshots
  id              UUID PK
  user_id         UUID FK → users
  snapshot_date   DATE
  total_value_tl  NUMERIC(18,2)
  created_at      TIMESTAMPTZ
  UNIQUE(user_id, snapshot_date)

-- Snapshot içindeki her varlık pozisyonu
asset_positions
  id                  UUID PK
  snapshot_id         UUID FK → portfolio_snapshots
  source_type         ENUM('exchange','blockchain')
  provider            TEXT        -- 'binance','icrypex','sonic','avalanche','tefas','bes'
  asset_type          ENUM('crypto','staked_crypto','fund','pension','cash')
  symbol              TEXT        -- 'BTC', 'S', 'AVAX', 'YFAS.MF'
  name                TEXT        -- "Bitcoin", "Sonic", "Avalanche"
  liquid_quantity     NUMERIC(28,8)   -- Serbest miktar
  staked_quantity     NUMERIC(28,8)   -- Stake edilmiş miktar
  pending_rewards     NUMERIC(28,8)   -- Birikmiş staking ödülü
  unit_price_tl       NUMERIC(18,4)
  total_value_tl      NUMERIC(18,2)   -- (liquid + staked + rewards) × fiyat
  weight_pct          NUMERIC(5,2)
  wallet_address_id   UUID FK → wallet_addresses  -- blockchain için
```

### 5.5 Yatırım Tavsiyeleri

```sql
investment_advice
  id                UUID PK
  user_id           UUID FK → users
  snapshot_id       UUID FK → portfolio_snapshots
  horizon           ENUM('medium','long')
  content           TEXT
  prompt_tokens     INT
  completion_tokens INT
  generated_at      TIMESTAMPTZ
```

### 5.6 Harcamalar (Faz 2)

```sql
expense_categories
  id         UUID PK
  user_id    UUID FK → users
  name       TEXT
  color      TEXT              -- Hex (#FF5733)
  budget_tl  NUMERIC(12,2)
  is_default BOOLEAN

expenses
  id           UUID PK
  user_id      UUID FK → users
  category_id  UUID FK → expense_categories
  amount       NUMERIC(12,2)
  currency     TEXT DEFAULT 'TRY'
  amount_tl    NUMERIC(12,2)
  description  TEXT
  expense_date DATE
  source       ENUM('manual','bank_import')
  is_recurring BOOLEAN DEFAULT FALSE
  created_at   TIMESTAMPTZ

expense_summaries
  id           UUID PK
  user_id      UUID FK → users
  period_start DATE
  period_end   DATE
  total_tl     NUMERIC(12,2)
  breakdown    JSONB
  ai_analysis  TEXT
  generated_at TIMESTAMPTZ
```

---

## 6. API Tasarımı

### 6.1 Auth
```
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
```

### 6.2 Exchange Entegrasyonları
```
GET    /api/v1/integrations
POST   /api/v1/integrations/{provider}
DELETE /api/v1/integrations/{provider}
POST   /api/v1/integrations/sync
```

### 6.3 Blockchain Cüzdanlar
```
GET    /api/v1/wallets                  -- Kayıtlı adresler
POST   /api/v1/wallets                  -- Adres ekle {chain, address, label}
DELETE /api/v1/wallets/{id}             -- Adres kaldır
POST   /api/v1/wallets/sync             -- Manuel zincir sorgusu
```

### 6.4 Portföy
```
GET    /api/v1/portfolio                -- Güncel portföy (son snapshot)
GET    /api/v1/portfolio/history        -- Haftalık tarihsel veriler
GET    /api/v1/portfolio/changes        -- WoW / MoM değişimler
GET    /api/v1/portfolio/breakdown      -- Varlık sınıfı + staking dağılımı
GET    /api/v1/portfolio/staking        -- Tüm staking pozisyonları + ödüller
```

### 6.5 Tavsiye
```
GET    /api/v1/advice
POST   /api/v1/advice/generate
```

### 6.6 Harcamalar (Faz 2)
```
GET    /api/v1/expenses
POST   /api/v1/expenses
PUT    /api/v1/expenses/{id}
DELETE /api/v1/expenses/{id}
POST   /api/v1/expenses/import

GET    /api/v1/expenses/categories
POST   /api/v1/expenses/categories

GET    /api/v1/expenses/analysis
POST   /api/v1/expenses/analysis/generate
```

---

## 7. Blockchain Servis Detayları

### 7.1 Sonic Service

```python
# Akış
# 1. web3.py ile Sonic RPC'ye bağlan
# 2. SFC contract'ını yükle (ABI + adres)
# 3. Kullanıcının tüm validator'larını sorgula
# 4. Her validator için getStake() + pendingRewards() çağır
# 5. Liquid S bakiyesini eth_getBalance ile al

RPC_URL      = "https://rpc.soniclabs.com"
# SFC contract adresi Sonic dokümantasyonundan doğrulanmalı
```

### 7.2 Avalanche Service

```python
# P-Chain staking (AVAX delegasyon/validasyon)
POST https://api.avax.network/ext/bc/P
{
  "jsonrpc": "2.0",
  "method": "platform.getStake",
  "params": {"addresses": ["P-avax1..."], "encoding": "hex"},
  "id": 1
}
# Yanıt: staked (nAVAX), stakedOutputs

# C-Chain bakiye (liquid AVAX)
# web3.py — RPC: https://api.avax.network/ext/bc/C/rpc
```

### 7.3 Desteklenen Zincirler (Ledger için)

| Zincir | RPC | Sorgu Yöntemi |
|--------|-----|---------------|
| Ethereum | Infura/Alchemy | web3.py — eth_getBalance |
| Sonic | rpc.soniclabs.com | web3.py + SFC contract |
| Avalanche C | api.avax.network/ext/bc/C/rpc | web3.py |
| Avalanche P | api.avax.network/ext/bc/P | httpx (REST) |

---

## 8. AI Tavsiye Motoru

### 8.1 Portföy Tavsiyesi Prompt Yapısı

```
Sistem: Deneyimli bir portföy danışmanısın.
        Türk yatırımcısı için gerçekçi, uygulanabilir tavsiyeler üretiyorsun.

Kullanıcı bağlamı:
- Risk profili: {risk_profile}
- Portföy toplam değeri: {total_value_tl} TL
- Dağılım: Kripto %{crypto_pct} (stake %{staked_pct}), Fon %{fund_pct}, BES %{bes_pct}
- Staking pozisyonları: S {s_staked} adet ({s_apy}% APY), AVAX {avax_staked} adet ({avax_apy}% APY)
- Birikmiş staking ödülleri: {pending_rewards_tl} TL
- Haftalık değişim: {wow_change_pct}%
- Aylık değişim: {mom_change_pct}%
- En iyi performer: {top_asset}
- En kötü performer: {worst_asset}

[{horizon} vade için tavsiye üret]
```

### 8.2 Claude API Ayarları

- Model: `claude-sonnet-4-6`
- Prompt caching: sistem prompt cache'lenir
- Max tokens: 1024
- Yanıt formatı: Yapılandırılmış Markdown

---

## 9. Güvenlik

| Konu | Çözüm |
|------|-------|
| Exchange API key | Fernet şifreleme, master key `.env`'de |
| Blockchain adres | Public key — şifrelemeye gerek yok |
| Özel anahtar | **Asla sisteme girmez** |
| Kullanıcı şifresi | bcrypt hash |
| Oturum | JWT (access 15dk, refresh 7 gün) |
| HTTPS | Nginx reverse proxy (prod) |

---

## 10. Geliştirme Fazları

### Faz 1a — Temel Altyapı
- [ ] FastAPI proje iskeleti
- [ ] PostgreSQL + Alembic
- [ ] JWT auth
- [ ] `BaseIntegration` soyut sınıfı (exchange + blockchain için ayrı base)

### Faz 1b — Exchange Entegrasyonları
- [ ] Binance (CCXT)
- [ ] iCrypex (CCXT)
- [ ] TEFAS (scraping)
- [ ] BES manuel giriş

### Faz 1c — Blockchain Entegrasyonları
- [ ] `wallet_addresses` tablosu + endpoint
- [ ] Sonic Service (web3.py + SFC)
- [ ] Avalanche Service (P-Chain + C-Chain)
- [ ] Ethereum bakiye sorgusu

### Faz 1d — Portföy & Tavsiye
- [ ] Aggregator (TL normalize, staking ayrımı)
- [ ] APScheduler haftalık snapshot
- [ ] WoW / MoM değişim hesaplama
- [ ] Staking dashboard verileri
- [ ] Claude API tavsiye

### Faz 1e — Frontend (Yatırım)
- [ ] Next.js dashboard — portföy özet kartları
- [ ] Staking pozisyon kartları (S stake, AVAX stake, pending rewards)
- [ ] Haftalık değişim grafikleri (Recharts — line chart)
- [ ] Varlık dağılımı (pasta grafik: kripto / staked / fon / BES)
- [ ] Yatırım tavsiye paneli (orta + uzun vade, Claude çıktısı)

### Faz 2a — Harcama Backend
- [ ] Harcama modelleri + CRUD endpointler
- [ ] Kategori yönetimi (varsayılan kategorilerle başlar)
- [ ] Aylık özet hesaplama servisi

### Faz 2a — Harcama Frontend
- [ ] Harcama giriş formu (tutar, kategori, tarih, not)
- [ ] Harcama listesi + filtreleme (tarih aralığı, kategori)
- [ ] Kategori yönetim ekranı (renk, bütçe limiti)

### Faz 2b — Analiz Backend
- [ ] Bütçe limit kontrol + uyarı mekanizması
- [ ] Claude harcama analizi entegrasyonu

### Faz 2b — Analiz Frontend
- [ ] Harcama analiz dashboard'u
  - Aylık toplam + geçen ay karşılaştırması
  - Kategori bazlı pasta/bar grafik (Recharts)
  - Aylık trend çizgi grafik
- [ ] Bütçe durum göstergeleri (progress bar — limit/harcanan)
- [ ] Claude tasarruf önerileri paneli

### Faz 2c — Gelişmiş Backend
- [ ] Banka ekstresi CSV import + otomatik kategori eşleştirme
- [ ] Tekrarlayan ödeme tespiti algoritması

### Faz 2c — Gelişmiş Frontend
- [ ] CSV import ekranı (sürükle-bırak)
- [ ] Tekrarlayan ödemeler listesi
- [ ] Yatırım ↔ Harcama denge ekranı
  - Aylık net tasarruf = gelir − harcama
  - Yatırıma aktarılabilir tutar önerisi
  - Portföy büyüme simülasyonu

---

## 11. Teknoloji Bağımlılıkları

```toml
[project.dependencies]
fastapi = ">=0.115"
uvicorn = {extras = ["standard"]}
sqlalchemy = {extras = ["asyncio"]}
alembic = "*"
asyncpg = "*"
pydantic-settings = "*"
python-jose = "*"
passlib = {extras = ["bcrypt"]}
cryptography = "*"         # Fernet (exchange API key şifreleme)
ccxt = "*"                 # Binance, iCrypex
web3 = "*"                 # Sonic, Avalanche C-Chain, Ethereum
httpx = "*"                # Avalanche P-Chain API, TEFAS scraping
beautifulsoup4 = "*"
apscheduler = "*"
anthropic = "*"

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "httpx", "ruff"]
```
