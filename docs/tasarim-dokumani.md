# KFinans — Sistem Tasarım Dokümanı

**Versiyon:** 3.1
**Tarih:** 2026-04-30
**Durum:** Aktif geliştirme — Faz 1 tamamlandı, Faz 2 başlıyor
**Üretici:** Mayotek

---

## Doküman Yapısı

Bu doküman bir **kapı dokümanı**dır — projenin genel vizyonunu, fazlarını ve detaylı dokümanlara yönlendirmeleri içerir. Her teknik konunun derinlemesine açıklaması ilgili alt dokümandadır.

| Doküman | İçerik | Sahip Ajan |
|---------|--------|------------|
| [mimari.md](./mimari.md) | Sistem mimarisi, modüler monolit yapı, veritabanı şeması, indeks stratejisi | architect + dba |
| [api-referansi.md](./api-referansi.md) | Tüm REST endpoint'leri, request/response örnekleri, hata kodları | backend-expert |
| [frontend.md](./frontend.md) | Next.js App Router yapısı, component sınırları, state, API client | frontend-expert |
| [altyapi-test.md](./altyapi-test.md) | Docker Compose, Kubernetes, CI/CD, test stratejisi ve coverage hedefleri | devops + test-expert |
| [guvenlik.md](./guvenlik.md) | Auth akışı, JWT, Fernet şifreleme, rate limiting, OWASP kontrol listesi | security-expert |
| [uyumluluk-kvkk.md](./uyumluluk-kvkk.md) | KVKK, GDPR, SPK lisans sınırı, gizlilik politikası, kullanıcı hakları | compliance-expert |
| [ai-ve-finans.md](./ai-ve-finans.md) | Claude API entegrasyonu, prompt tasarımı, portföy hesaplama formülleri | ai-expert + finance-expert |
| [kredi-sistemi.md](./kredi-sistemi.md) | Kredi paketleri, iyzico ödeme akışı, kredi tüketim kuralları | architect + finance-expert |

---

## 1. Platform Vizyonu

KFinans, kişisel finansı tek ekranda yöneten **çok kiracılı (multi-tenant) SaaS platformudur**. Hedef pazar: Türkiye bireysel yatırımcısı. Erişim kanalları: web (Next.js) ve mobil (Flutter — Faz 3). Temel takip ücretsiz; AI tavsiye, kripto/blockchain otomatik senkronizasyon ve gelişmiş analiz **kredi sistemi** ile ücretlendirilir.

### 1.1 Üretici ve Marka
- **Üretici Firma:** Mayotek (kurucu: celikada@gmail.com)
- **Ürün:** KFinans
- **Logolar:** `frontend/public/images/kfinans-logo.png`, `mayotek-logo.png`

### 1.2 Faz Planı

| Faz | Kapsam | Durum |
|-----|--------|-------|
| **Faz 1** | Yatırım takibi (TEFAS, kripto, blockchain, hisse senedi), Excel import/export, dashboard | ✅ Aktif |
| **Faz 2** | Kullanıcı kaydı, e-posta doğrulama, BES manuel giriş, haftalık snapshot grafiği | 🔄 Sıradaki |
| **Faz 3** | Kredi sistemi + iyzico, AI tavsiye motoru aktivasyonu, harcama takibi | Planlı |
| **Faz 4** | Flutter mobile app, Play Store yayın, Apple sertifikasyonu | Planlı |

---

## 2. İş Modeli

### 2.1 Kullanıcı Tipleri ve Fiyatlandırma

| Tip | Erişim | Fiyat |
|-----|--------|-------|
| **Ücretsiz** | TEFAS takibi, manuel varlık, temel portföy görünümü, Excel import/export | — |
| **Kredi Paketi** | AI tavsiye, kripto entegrasyonu, blockchain sorgu, gelişmiş analiz | Kredi başına |

### 2.2 Kredi Tüketim Kuralları

| İşlem | Maliyet |
|-------|---------|
| AI portföy tavsiyesi (orta vade) | 5 kredi |
| AI portföy tavsiyesi (uzun vade) | 10 kredi |
| Kripto senkronizasyonu (Binance/iCrypex/BinanceTR) | 1 kredi/çekim |
| Blockchain bakiye sorgusu | 1 kredi/sorgu |
| Gelişmiş harcama analizi (Faz 3) | 3 kredi |

> Detaylı tüketim mantığı, ödeme akışı ve idempotency: [kredi-sistemi.md](./kredi-sistemi.md)

### 2.3 Kredi Paketleri

| Paket | Kredi | Fiyat |
|-------|-------|-------|
| Başlangıç | 50 | 29 ₺ |
| Standart | 150 | 69 ₺ |
| Profesyonel | 500 | 199 ₺ |

Ödeme: **iyzico** (sandbox + production). Stripe çoklu para birimi için Faz 4'te değerlendirilecek.

---

## 3. Teknoloji Yığını

### 3.1 Backend
- Python 3.12 + FastAPI (async-first)
- PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg driver) + Alembic
- APScheduler (Pazar 23:00 haftalık snapshot)
- Anthropic Python SDK (Claude API tavsiye motoru)
- CCXT (Binance, iCrypex), web3.py (Sonic, Avalanche, Ethereum), httpx (TEFAS, Yahoo Finance)
- slowapi (rate limiting), Fernet (API key encryption), bcrypt (şifre hash), python-jose (JWT)

### 3.2 Frontend
- Next.js 16.2.4 (App Router, Turbopack), React 19, TypeScript (strict mode), Tailwind CSS v4
- `proxy.ts` (Next.js 16 yeni adlandırma — `middleware.ts` deprecated)

### 3.3 Mobile (Faz 4)
- Flutter, http, flutter_secure_storage, riverpod

### 3.4 Altyapı
- Docker + Docker Compose (geliştirme — bilinçli teknik borç)
- Kubernetes (production hedef; namespace: `kfinans`)
- Tilt veya Skaffold (production'a geçişte dev loop için)
- GitHub Actions (CI/CD), GHCR (container registry)
- Helm (bitnami/postgresql), nginx-ingress, cert-manager

---

## 4. Veri Kaynakları

| Tür | Kaynak | Yöntem |
|-----|--------|--------|
| TEFAS fonu | TEFAS API | httpx + JSON (`fonkod/sonPortfoyDegeri/sonPayAdedi`) |
| Hisse (BIST/ABD/UK) | Yahoo Finance | httpx (`v8/finance/chart/{ticker}`) — auth gerekmez |
| Kripto Spot | Binance, iCrypex | CCXT |
| Kripto TR Earn | Binance TR | session token (cid cookie) — geçici çözüm |
| Sonic | EVM (RPC) | web3.py + SFC staking contract (Semaphore(20)) |
| Avalanche P-Chain | platform.getStake | httpx (REST API) |
| Avalanche C-Chain | EVM (RPC) | web3.py |
| Ethereum | EVM (RPC) | web3.py + Etherscan |
| BES | Manuel giriş (Faz 2) | — |

> Blockchain entegrasyonlarında **özel anahtar asla sisteme girmez** — yalnızca public adres saklanır.
> Detaylı entegrasyon mantığı: [mimari.md](./mimari.md#7-veri-kaynaklari-ve-servisler)

---

## 5. Mimari Özeti

KFinans **modüler monolit** mimarisi kullanır:
- Tek FastAPI uygulaması (3 Kubernetes Deployment: backend, frontend, postgres)
- Servis ayrımı kod içinde (`api/v1/*`, `services/*`)
- Mikroservise geçişe gerek yok — mevcut ölçek ve trafik için aşırı karmaşıklık

```
İstemci (Web / Mobile)
    │
    ▼ HTTPS / REST
Kubernetes Ingress (nginx)
    │
    ├──► backend Deployment (FastAPI + uvicorn, replicas: 2)
    │         │
    │         ▼
    │    PostgreSQL StatefulSet (bitnami/postgresql)
    │
    └──► frontend Deployment (Next.js standalone, replicas: 2)
```

> Tam mimari, modül sınırları ve veri akışı: [mimari.md](./mimari.md)

---

## 6. Geliştirme Kuralları

- **Doküman dili:** Türkçe (commit mesajları dahil)
- **Kod dili:** İngilizce (identifier, comment, log)
- **Secrets:** Asla koda yazılmaz; `.env` üzerinden `pydantic-settings` ile okunur
- **Migration:** Tüm DB değişiklikleri Alembic üzerinden
- **PR akışı:** `feature/*` → `develop` → `release/*` → `main` (korumalı)
- **CI:** Test + lint geçmeden merge yapılamaz

> Git Flow detayları: [altyapi-test.md](./altyapi-test.md#git-flow)

---

## 7. Güncel Durum (2026-04-30)

### ✅ Faz 1 Tamamlandı
- Backend iskeleti, JWT auth, slowapi rate limiting (login 10/dk, register 5/dk, refresh 30/dk), `/health` endpoint
- TEFAS, kripto (Binance/BinanceTR/iCrypex), blockchain (Sonic/Avalanche/Ethereum), hisse (Yahoo Finance)
- Excel import/export tüm varlık türleri için
- Frontend dashboard, login, kripto/wallets/stocks sayfaları
- Docker Compose dev ortamı (Kubernetes port-forward watchdog kaldırıldı)
- CI/CD: 4 ayrı workflow — `ci-backend`, `ci-frontend`, `e2e`, `security`
- **Test paketi: 89 backend + 3 frontend Vitest + 5 Playwright E2E senaryosu**
  - Unit: security (22), aggregator (22), GBp dönüşümü (7), TEFAS (6)
  - Integration: auth (7), portfolio (8), IDOR (7), integrations (5), wallets (5)
  - E2E: login redirect, dashboard akışı (Playwright)
- 11 domain expert ajanı (`.claude/agents/`) — backend, frontend, dba, devops, security, test, architect, finance, doc, ai, compliance
- 9 odaklı doküman (`docs/`)
- Migration durumu güncel: `users` lifecycle kolonları (email_verified, verify_token, deleted_at, credit_balance), `investment_advice.credits_used`, performans index'leri

### 🐛 Faz 1'de Düzeltilen Bug'lar
- **GBp dönüşüm hatası** — UK hisseleri için GBP/USD kuru zinciri (`api/v1/stocks.py::convert_to_tl`)
- **Duplicate wallet 500 → 409** — `IntegrityError` doğru HTTP koduyla yakalanıyor
- **Pydantic v2 uyumsuzluk** — `class Config` → `model_config` (kısmi)
- **Service katmanı logger eksikliği** — 9 servise module-level `logger` eklendi

### 🔄 Faz 2 Sıradaki Öncelikler
- Kullanıcı kayıt frontend sayfası + e-posta doğrulama akışı (Resend/SES)
- Haftalık snapshot job'ının implement edilmesi (`scheduler.py` boş)
- TCMB API USD/TRY fallback (sabit kur yerine)
- BES manuel giriş ekranı
- Kubernetes manifest'leri (`k8s/` klasörü hâlâ boş)
- KVKK metinleri (gizlilik politikası, aydınlatma, açık rıza)
- Test coverage %30 → %50 hedefi

### 📋 Faz 3 Planlananlar
- Kredi sistemi tam implementasyonu + iyzico sandbox
- KVKK endpoint'leri (`/me/data-export`, `/me/account` soft delete)
- `audit_logs` tablosu
- Cache katmanı (Redis) — USD/TRY, TEFAS, Yahoo
- Background job kuyruğu (Celery/RQ)

> Detaylı yol haritası ve TODO'lar her alt dokümanın sonundadır.
