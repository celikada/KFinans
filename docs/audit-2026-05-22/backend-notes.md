# Backend Audit Notları — 2026-05-22

Kapsam: `backend/app/` altındaki 21 router, 13 servis modülü (3 exchange + 10 blockchain), `core/` güvenlik katmanı, scheduler ve middleware zinciri. Odak: kod kalitesi, reusability, portability.

## ✓ Mevcut Pozitif

- **`BaseIntegration` + `BaseExchangeIntegration` + `BaseBlockchainIntegration`** soyut sınıf hiyerarşisi temiz. `AssetData` dataclass tüm kaynaklarda tek normalize formatı sağlıyor (`liquid_quantity / staked_quantity / pending_rewards / unit_price_usd|tl`). 13 servisin hepsi `fetch()` + `health_check()` implement ediyor — interface contract sıkı.
- **Exception handler katmanı (`main.py`)** üç seviyeli (`IntegrityError → 409`, `SQLAlchemyError → 500`, `Exception → 500`) ve hepsi `{detail, code, request_id}` formatında — information disclosure güvenliği iyi.
- **`MultiFernet` key rotation** (`core/security.py::_build_fernet`) audit fix'leriyle eklenmiş — zero-downtime rotation için pattern doğru: primary encrypt, secondaries decrypt-only. Migration prosedürü docstring'de adım adım yazılı.
- **`address_fingerprint` (SHA-256 lowercase)** Fernet şifreli adres için unique-constraint mekanizması zekice — plaintext WHERE imkânsızken çakışma engellenmiş.
- **Audit log altyapısı (`services/audit.py`)** `AuditAction` Enum + `log_audit()` best-effort try/except + 35+ tanımlı action — pattern tutarlı, log fail ana endpoint'i bozmuyor.
- **Scheduler güvenliği**: `SCHEDULER_ENABLED` env flag + `pg_try_advisory_lock` defence-in-depth multi-replica leader election.
- **PII masking helper'ları (`core/masking.py`)** modül-bağımsız: `mask_address`, `mask_email`, `hash_email`. Tek dosya, salt fonksiyon, hiçbir global state yok — yüksek reusability.
- **MFA (`api/v1/mfa.py`)** RFC 6238 uyumlu, recovery code bcrypt hash + one-time-use enforcement, pre_mfa_token 15 dk TTL. Akış 5 endpoint'te net.

## ⚠ Çelişti / Düzeltme Notları

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | **Yüksek** | Cache + single-flight pattern 5 dosyada birebir kopyalanmış (`bitcoin.py`, `solana.py`, `polkadot.py`, `litecoin.py`, `avalanche.py`) — her biri `_BALANCE_CACHE` + `_INFLIGHT` + `_cache_lock` global'leri tanımlıyor (≈40 satır/dosya × 5 = 200 satır duplikasyon) | Bakım: cache TTL/lock semantiği bir yerde değişirse 5 dosya senkronsuz kalabilir; test ayrı yazılması gerekiyor | `core/cache.py::AsyncTTLCache` helper sınıfı yaz — `await cache.get_or_compute(key, async_fn, ttl=600)`. Servisler `_cache = AsyncTTLCache()` ile kullansın |
| 2 | **Yüksek** | Public API URL'leri 15 dosyada hard-coded (`mempool.space`, `koios.rest`, `algonode.cloud`, `litecoinspace.org`, `glacier-api.avax.network`, `api.binance.com`, `query1.finance.yahoo.com`, vs.) | Portability: kendi proxy/cache layer'a geçiş, regional fallback veya test mock'lama zor | URL'leri `config.py::Settings`'e taşı (`bitcoin_api_url`, `cardano_api_url`...). Default'ları aynı kalsın; env override mümkün olsun |
| 3 | **Yüksek** | `services/advisor.py` Anthropic SDK'ya sıkı bağlı — `import anthropic` modül seviyesinde, `_client = AsyncAnthropic(...)`, 7 farklı `anthropic.*Error` exception | LLM provider değiştirmek (OpenAI fallback, Gemini, lokal Llama) tüm advisor.py'yi rewrite gerektirir | `services/ai/base.py::BaseLLMProvider` interface + `AnthropicProvider` impl. Exception mapping provider'a kapsüle olsun. Bkz. ai-expert agent koordine edilmeli |
| 4 | **Orta** | Pydantic v2 modern stil 4/20 schema dosyasında (`portfolio`, `integration`, `advice`, `mfa` v2; 10+ dosya `from_attributes=True` orchestra olmadan kullanıyor) | DEPS-001 kuralı (CLAUDE.md) ihlali; yeni schema yazan dev hangi stili kullanacak şüpheli | Tüm v1 stillerini `ConfigDict` + `@field_validator` ile migrate et. `bes.py`, `cash.py`, `commodity.py`, `expense.py`, vs. dahil |
| 5 | **Orta** | `EthereumService` ve `AvalancheCChainService` neredeyse aynı RPC fallback mantığını duplicate (`_FALLBACK_RPCS` listesi + for loop + `_w3` instance set) | Sonic / yeni EVM zinciri eklenirse 3. kez kopyalanacak | `services/blockchain/evm_base.py::EVMService` extract et — fallback RPC list constructor parametresi olsun. Sonic da bu pattern'e otursun |
| 6 | **Orta** | `BinanceService` ve `BinanceTRService` HMAC imza + `_sync_time` + `_get_flexible_earn` + `_get_locked_earn` ≈%80 ortak kod | İki yerde mantık divergence riski (gerçekten oldu: binancetr session_token ek path) | `services/exchange/binance_base.py::BinanceCompatibleService` extract; TR sadece `_BASE` override + session_token branch'i |
| 7 | **Orta** | Hard-coded blockchain magic constants servis dosyalarına gömülü: `SFC_ADDRESS = "0xFC00FACE..."` (sonic), `_STAKE_PROGRAM = "Stake1111..."` (solana), `LAMPORTS_PER_SOL`, `PLANCK_PER_DOT`, `LITOSHI_PER_LTC`, `SATOSHI_PER_BTC` | Tek dosyada toplanmayan magic değerler tekrar yazılırsa tutarsızlık | `services/blockchain/constants.py` veya her zincirin `chain_meta` modülü |
| 8 | **Orta** | `services/aggregator.py` global `_tcmb_cache: tuple | None` modül-state cache — test izolasyonu için reset gerekiyor; aynı pattern `commodity.py`'da da var | TEST-004 truncate'i Python state'i temizlemiyor; testler arası leak riski | Aynı `AsyncTTLCache` helper'ı (#1) kullan + test fixture'ta `clear()` |
| 9 | **Düşük** | `BaseIntegration` `health_check()` ABC'de zorunlu ama `BinanceService.health_check` API key gönderir; `BlockchainService.health_check` çoğunda `True` döner — semantic tutarsız | Health endpoint'i (varsa) yanıltıcı sinyaller üretebilir | Sözleşmeyi netleştir: "external service reachable" vs "credentials valid". İki ayrı metod (`is_reachable()`, `verify_credentials()`) |
| 10 | **Düşük** | `EthereumService.health_check` doğrudan `self.fetch()` çağırır — health probe Ethplorer rate-limit yer | Health probe pahalı; izleme bunu sık çağırırsa Ethplorer kotası tükenir | Sadece native balance fetch ile health doğrula, token tarama atla |
| 11 | **Düşük** | `PolkadotService` `substrate-interface` sync kütüphanesini `asyncio.to_thread` ile sarıyor — thread pool default 40 worker, busy snapshot job'da bottleneck olabilir | 100+ user paralel snapshot'ta thread starvation | `httpx` ile Substrate JSON-RPC doğrudan async çağrı (websocket yerine HTTP `state_getStorage`) |
| 12 | **Düşük** | `services/audit.py::_client_ip` sadece `request.client.host` okuyor — yorumda "trusted proxy via uvicorn --proxy-headers" diyor ama bu deployment-time config; Dockerfile/k8s manifest'te uygulanıyor mu unclear | Eğer `--proxy-headers` flag eksikse audit log'lar pod internal IP'sini yazar | k8s manifest'te uvicorn flag'ini explicit doğrula + integration test ekle |
| 13 | **Düşük** | `database.py::_ssl_mode == "prefer"` `CERT_NONE` ile self-signed kabul ediyor (`noqa: S5527/S4830`) — geçici; "ayrı PR" olarak bekliyor | Defence-in-depth olsa da production'da MITM koruması yok | CA bundle mount eden ayrı PR aç, `require` mode'a geç |
| 14 | **Düşük** | `services/snapshot.py` ve `aggregator.py` global cache state ile test izolasyonu bozulabilir; `tests/conftest.py`'da reset hook'u yok | Cumulative test fail'leri | autouse fixture: `_tcmb_cache = None`, `_BALANCE_CACHE.clear()` her test başında |

## Reusability Patterns

- **BaseIntegration: 10 blockchain + 3 exchange ortak ne kadar reuse ediliyor?**
  - Abstract layer (`AssetData`, `fetch()`, `health_check()`) %100 tutarlı — iyi.
  - **Ama** alt katmanda (cache, retry, rate-limit, RPC fallback) reuse çok zayıf. 5 zincirde cache pattern duplicate (#1); 2 EVM zincirinde fallback RPC duplicate (#5); 2 Binance servisinde HMAC + earn pagination duplicate (#6). Tahmini **%30-40 silinebilir kod** ortak helper'larla.
  - Servisler birbirinden bağımsız test edilebiliyor (artı), ama "yeni zincir ekleme" kolaylığı zayıf — Cosmos/NEAR/TON eklenirse yine ≈150 satır boilerplate yazılması gerekir.

- **Service layer abstraction (cache, rate_limit, retry pattern)**
  - Cache: 5 farklı tanım (her servis kendi globalları). Önerilen: `core/cache.py::AsyncTTLCache`.
  - Rate-limit: Servis seviyesinde yok — sadece slowapi (HTTP boundary). Dışarı çağrılar (mempool.space, ethplorer) için per-host throttle/concurrency kontrolü yok; rate-limit'e yakalanma riski.
  - Retry: Ad-hoc — solana 3 retry, avalanche 3 retry, ethplorer ayrı backoff. Standart `tenacity` veya basit decorator önerilir.

- **Schema/Model pattern Pydantic v2 modern stil ne kadar uygulanmış?**
  - 4 dosyada `ConfigDict` (portfolio, integration, advice, mfa).
  - 10+ dosyada eski stil `from_attributes=True` orchestra dışı.
  - DEPS-001 kuralı net ama uygulama yarım — incremental migration backlog'a alınmalı.

## Portability

- **Hard-coded URL'ler (#2)**: 15 dosyada `_BASE_URL = "https://..."` pattern. Anthropic SDK kendi URL'ini kullanıyor (env override mümkün), ama Resend, mempool.space, koios, algonode, litecoinspace, glacier, yahoo, tcmb, binance, ethplorer, coingecko hepsi gömülü. Reverse-proxy / self-hosted node geçişi tüm dosyaları değiştirir. Settings'e taşı.

- **LLM provider abstraction (#3)**: Anthropic'e direkt bağımlı. Fallback (OpenAI/Gemini) için provider abstraction lazım — özellikle Anthropic outage'ta `/advice/generate` 503 döner ama kredi düşme/consent kontrolü iş kuralları aynı. Provider switch business logic'i etkilememeli.

- **DB-agnostic level (PostgreSQL-specific advisory lock kullanımı)**: `scheduler.py::_try_acquire_lock` ve `_release_lock` `pg_try_advisory_lock` çağırıyor — PostgreSQL özel. Tek deploy hedefi Postgres olduğu için kabul edilebilir; **ama** alternatif olarak Redis `SETNX` veya DB-agnostic `leader_elections` table pattern düşünülebilir. Eğer SQLite ile local dev hedeflenirse (şu an asyncpg-only) bu kırılır. Mevcut config DB-agnostic yazılmadığı için tutarlı (`asyncpg` zaten Postgres-only). **Risk düşük** — sadece dokümante et.

- **`pg_try_advisory_xact_lock` yorumunda yazılı ama kullanılan `pg_try_advisory_lock` (session-scoped)** — yorum-kod tutarsızlığı küçük; yorumu güncelle ya da xact_lock'a geç (transaction-scoped daha güvenli).

- **Connect args SSL config**: `database.py` `prefer`/`require`/`disable` enum'u Postgres'e özel (`asyncpg` ssl param). Diğer driver'larda farklı API. Yine asyncpg-only kabul edilebilir.

---

Toplam: 14 not, 12 reusability/portability gözlem.
