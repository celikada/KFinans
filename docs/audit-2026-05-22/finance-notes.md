# Finans Audit Notları — 2026-05-22

Kapsam: `backend/app/services/aggregator.py`, `snapshot.py`, `commodity.py`, `stocks.py`,
`tefas.py`, `exchange/*`, `blockchain/*`, `api/v1/{stocks,cash,goal,manual_crypto}.py`,
`models/portfolio.py`, `schemas/portfolio.py`.

## Mevcut Pozitif

- **Decimal hijyeni baştan tutarlı.** `Decimal(str(float_value))` kullanımı yaygın; `float` üzerinden
  binary precision kaybı kontrol altında. ORM kolonları `Numeric(28,8)` (qty), `Numeric(28,10)`
  (unit_price_tl — FIN-018 ile SHIB/PEPE mikro fiyatlar için genişletildi), `Numeric(18,2)` (toplam TL),
  `Numeric(5,2)` (weight_pct). Mikro-cap krip token'ların 1e-10 hassasiyeti destekleniyor.
- **GBp → GBP → USD → TL zinciri doğru.** `api/v1/stocks.py::convert_to_tl` `price/100 * gbp_usd * usd_tl`
  uyguluyor (CLAUDE.md'nin "GBp/100 = USD varsayım hatalı" notu eskimiş; düzeltilmiş).
- **Multi-currency cash desteği (FIN-007).** `_gather_cash_assets` TCMB rates dict'inden EUR/CHF/JPY/...
  ayrı kurlarını okuyor; eksik kur durumunda kullanıcıya `currency_rate_missing` health issue düşüyor —
  sessiz yanlış değer yerine UI banner.
- **Snapshot tarihi `Europe/Istanbul` lokal.** Backend container UTC olsa bile snapshot kullanıcının yerel
  gününe yazılıyor — gece 00-03 ad-hoc snapshot'lar "dün"e düşmüyor.
- **`usd_try_rate` snapshot anında saklanıyor.** History sayfası TL/USD toggle'ı + `_last_known_usd_price`
  fallback'i bu sayede tutarlı (FIN-005). Kur sonradan değişse de eski USD eğimi bozulmuyor.
- **Stale fiyat görünmez kayıp önleme (FIN-004 + FIN-005).** Yahoo `regularMarketTime > 30h` → `is_stale=True`,
  spot fiyat 0 dönerse önceki snapshot'tan son bilinen USD fiyatı + warning. Halted/delisted hisseler ve
  Binance'ten kaybolan token'lar portföyü sessizce sıfırlamıyor.
- **Stablecoin + ETH-peg alias listesi.** `SYMBOL_PRICE_ALIASES` (stETH/wstETH/cbETH/rETH/sAVAX/WBTC) +
  `USD_STABLE_SYMBOLS` (USDT/USDC/DAI/FRAX/BUSD/TUSD). Peg'li token'lar Binance USDT paritesi olmasa bile
  doğru fiyatlanıyor.
- **CoinGecko fallback + ID cache (24h).** Binance USDT paritesi olmayan token (ICPX vb.) için CoinGecko
  `/simple/price`; `/coins/list` 24h cache → rate limit ekonomik.
- **Çift sayım kuralı kredi kartı.** `credit_card_id IS NOT NULL AND is_paid=true` filtrelemesi
  expenses/budget/forecast endpoint'lerinde uygulanıyor — kart dönem borcu ile ödenmiş expense aynı parayı
  iki kere saymıyor.
- **TCMB tek-cağrı + 5dk cache.** `_fetch_tcmb_rates` global memo; aynı snapshot içinde 3+ kez ağ çağrısı yok.

## Çelişti / Düzeltme Notları

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | P1 | `aggregator.py` 4 sorumluluk yüklü (TCMB XML parse + exchangerate-api + Binance spot + CoinGecko fallback + asset position mapper + breakdown hesabı + change calculator). Dosya 396 satır, 7 farklı concern. | Yeni döviz/exchange ekleme noktası belirsiz; test'te mock noktası şişiyor. | `services/pricing/{tcmb,binance,coingecko,fx}.py` ayrı modüller; `aggregator.py` sadece `to_asset_position` + breakdown + change kalmalı. |
| 2 | P1 | TCMB cache **process-global memo** (`_tcmb_cache` module var). Multi-replica K8s'de her pod ayrı cache; cache hit oranı düşük + 5dk içinde TCMB'ye replica sayısı kadar istek. | Rate-limit riski düşük (TCMB toleranslı) ama mimari kararsızlık; aynı 5dk içinde 2 pod farklı kur değeri görebilir → snapshot'lar arası dalgalanma. | Redis tabanlı shared cache (`settings.redis_url` zaten var, slowapi için kullanılıyor). |
| 3 | P1 | `fetch_combined_prices()` her snapshot'ta tüm Binance fiyat tablosunu (`/api/v3/ticker/price` ~2500 sembol, ~250KB) full fetch ediyor. Her wallet/exchange için ayrı çağrı potansiyeli var. | Snapshot süresi + bandwidth; multi-replica deploy'da 5 user paralel snapshot = 5 × 250KB. | `_BINANCE_PRICE_CACHE` (30sn TTL) ekle; aynı snapshot'taki tüm pozisyonlar tek fetch paylaşsın. |
| 4 | P1 | `calculate_changes()` snapshot indexing varsayımı sığ. `snapshots[1] = "geçen hafta"`, `snapshots[4] = "geçen ay"` ama kullanıcı haftaiçi manuel snapshot alırsa sıralama bozulur (4'üncü = "4 snapshot önce" değil "yaklaşık 4 hafta önce"). | "Aylık değişim" yanlış (örn. her gün manuel snapshot atıldıysa `snapshots[4]` = 4 gün önce). | `snapshot_date - INTERVAL '7 days'` / `'30 days'` ile SQL'de en yakın snapshot'ı seç (closest-by-date). |
| 5 | P0 | `Decimal` global precision/rounding mode hiç set edilmemiş (`getcontext()` default 28 hane, `ROUND_HALF_EVEN`/banker). `quantize(Decimal("0.01"))` çağrılarında banker's rounding muhasebe için sürpriz: `0.025 → 0.02` (`.03` değil). | TL toplamlar kullanıcının ondalık beklentisiyle çelişebilir (özellikle ufak miktarlı kripto pozisyonlarda kümülatif fark). | `decimal.getcontext().rounding = ROUND_HALF_UP` global set `main.py` startup'ında (en azından finans toplamlarında); ya da quantize çağrılarında explicit `rounding=` parametresi. |
| 6 | P1 | `to_asset_position()` `unit_price_tl` decimal'i sınırsız precision (qty × price → 28+10 = 38 hane) ile `Numeric(28,10)` kolonuna yazıyor; SQL silently truncate edebilir veya `OverflowError` riskiyle çalışıyor. | Pepe/Shiba × 10^9 qty + 10^-10 price = uç durumda 28 haneye yaklaşır; saklı snapshot bozulabilir. | `to_asset_position` içinde `value_tl = (total_qty * price_tl).quantize(Decimal("0.01"))`, `price_tl.quantize(Decimal("0.0000000001"))` explicit. |
| 7 | P1 | `tefas.py::_fetch_prices()` `today = date.today()` (UTC backend'de) — snapshot kullanıcı saatinde olsa bile TEFAS tarih penceresi Türkiye 03:00 öncesi yanlış. | Pencere 7 günlük olduğu için pratikte hata sızmıyor, ama mantık tutarsız. | `date.today()` → `datetime.now(ZoneInfo("Europe/Istanbul")).date()`. |
| 8 | P2 | Stablecoin "depeg" varsayım yok. USDT/USDC/DAI/FRAX `Decimal("1")` sabit. UST/Iron benzeri çöküş olursa portföy yanlış değer gösterir; uyarı verilmez. | Düşük olasılık, yüksek etki. | `fetch_combined_prices`'a stablecoin'leri de dahil et; CoinGecko'dan gerçek fiyatı çek; |delta| > %2 ise health issue ("USDC depeg uyarısı"). |
| 9 | P2 | `_STALE_THRESHOLD_SECONDS = 30 * 3600` (30 saat) hafta sonu için yeterli ama 3 günlük resmi tatil (örn. Kurban Bayramı arifesi + 4 gün) > 72 saat → tüm hisseleri "stale" işaretler ve health_issues şişer. | UI'de yanlış pozitif rozet kalabalığı. | İş günü farkı + market state birlikte değerlendir: `marketState != "REGULAR"` AND `business_days_since(market_time) > 1`. |
| 10 | P2 | `fetch_metal_prices()` Yahoo XAU=X/GC=F ve TCMB USD/TRY birleşiyor. Yahoo'dan dönen XAU=X fiyatı (örn. cuma kapanış) ile pazartesi sabah TCMB kuru birleşince **iki farklı zamanın değeri çarpılıyor**. | Hafta sonu altın TL gram = stale_friday_usd × monday_tcmb; küçük ama dokümante edilmeli. | `health_issues` içine `commodity_price_age` info düşür (Yahoo `regularMarketTime` farkı > X saat ise). |
| 11 | P2 | `BinanceService` `_STABLECOIN_USD` içinde `"TRY": Decimal("0")` var — `_get_spot_balances` TRY bakiyesini ele almıyor (`if unit_price == 0 and symbol not in _STABLECOIN_USD: continue` ile atlanıyor). `TRY` stablecoin listesinde olduğu için **atlanmıyor**, fiyat 0 olduğu için snapshot'a 0 değerle giriyor. | Kullanıcının Binance global TRY bakiyesi (varsa) portföyde 0 görünür. | TRY bakiyesi için doğrudan `unit_price_usd = 1/usd_tl` ata; ya da Binance TRY'yi snapshot'ta cash gibi normalize et. |
| 12 | P2 | `pending_rewards` `to_asset_position` ve `total_tl` hesabında `liquid + staked + pending` olarak toplanıyor ama `extract_staking_positions` ayrıca `rewards_value_tl` döndürüyor. Frontend'de "staking ödülleri" ayrı kart olarak gösteriliyorsa **çift gösterim**. | UI'de "Toplam Portföy" + "Bekleyen Ödüller" kartları toplandığında kullanıcı yanlış toplam hesaplar. | Frontend'de "Bekleyen Ödüller" yalnızca informational göster; UI'da "ana toplama dahildir" mikro-not eklensin. |
| 13 | P2 | `lookup_usd_price()` case-sensitive `prices.get(symbol)`; AssetData `symbol` upper/lower karışık geliyor (CCXT ICRYPEX symbol upper, Sonic SFC lower). Alias map `STETH` + `stETH` ikisini tutuyor — kod kokuyor. | Yeni alias eklenince ikisi de yazılması gerekiyor; biri unutulursa fiyat 0. | `lookup_usd_price` içinde `symbol.upper()` normalize et; alias map tek case ile yeterli olur. |
| 14 | P2 | `convert_to_tl()` non-TRY/non-GBp tüm para birimleri için `price * usd_tl` (USD varsayım). EUR'lu Almanya hisseleri (örn. SAP.DE EUR fiyatı) yanlış. | Avrupa hisseleri portföye eklenirse EUR/USD farkı kadar bias. | `q.currency` switch'i EUR/CHF/JPY için TCMB'den kuru çek; `_gather_cash_assets` paterni hisse için de geçerli. |
| 15 | P3 | `fetch_combined_prices` Binance fail'ında tüm semboller missing'e geçmiyor — `binance.get(s) <= 0` filtrelemesi `RuntimeError`'da exception olarak yayılır (try/except yok). | Binance public API 503 → snapshot iptal (kullanıcıya 500). | `fetch_spot_prices` try/except + boş dict döner; fallback CoinGecko tüm sembolleri denesin. |

## Reusability / Portability

- **Yeni exchange ekleme effort = düşük-orta.** `BaseExchangeIntegration(api_key, api_secret)` + `fetch()` +
  `health_check()` implement et, `Integration.provider` switch'inde `_gather_crypto_assets`'a satır ekle.
  Tahmini: ~150 LOC. BinanceTR `encrypted_extra` (session token) sayesinde 3. credential field'ı destekliyor.
- **Yeni blockchain ekleme effort = düşük.** `BaseBlockchainIntegration(address, wallet_address_id)` +
  `_gather_wallet_assets`'a chain switch satırı + `WalletAddress.chain` enum genişlet. Algorand/Polkadot/Litecoin
  pattern'i takip et.
- **Multi-currency support = TR-merkezli.** Tüm hesaplama TL'ye dönüyor; ORM kolonları `total_value_tl`,
  `usd_try_rate`. Diaspora kullanıcısı için "ana para birimi USD/EUR" istenirse:
  - `users.base_currency` (default "TRY") kolon eklemek gerekir;
  - `PortfolioSnapshot.total_value_*` çoklu kolon ya da JSONB `{TRY, USD, EUR}` saklamak;
  - Frontend tüm formatter'ların `formatTL` → `formatMoney(amount, currency)` migrate etmek.
  - Şu an UI'da TL sembolü hardcoded → ~100 yer değişir. **Tahmini effort: 2-3 hafta.**
- **Goal currency zaten 4 birim (TRY/USD/EUR/GBP).** Pattern doğru — base currency yaklaşımı için referans noktası.
- **TCMB kuru EUR/CHF/JPY/AUD/CAD/SEK/DKK/NOK/SAR/BGN/RON/RUB/IRR/CNY/PKR/QAR/KRW/AZN/AED için zaten var.**
  Cash multi-currency çalışır — sadece API exposure (cash dropdown'ı bu 18 currency'yi listelesin).

## Hesaplama Doğruluğu

- **Decimal precision.** Yeterli; SHIB/PEPE × milyar qty senaryosu için `Numeric(28,10)` ölçüsünde testler yok
  (round-trip 1e9 × 1e-10 = doğru mu?). Test eklenmesi gerek.
- **Rounding mode.** Global ayarsız (banker's). Muhasebede `ROUND_HALF_UP` beklenir; mevcut "0.005 → 0.00" davranışı
  vergi raporlamaya hazır değil.
- **Round-trip testleri.**
  - `_last_known_usd_price`: `unit_price_tl / usd_try_rate` → tekrar `* usd_try_rate` → orijinal `unit_price_tl`'e dönmeli (±%0.01); test yok.
  - `to_asset_position`: `value_tl / total_value_tl * 100` → weight; tüm weight'ler toplamı 100.00 ±0.05 olmalı. Bunu doğrulayan integration test yok (sadece `tests/services/test_aggregator.py` toy fixture).
  - Cost basis: `gain_loss_pct = gain_loss / cost_basis * 100`; cost_basis = 0 durumu `None` ile handle edildi ama negatif avg_cost (kullanıcı yanlış girerse schema validator -1 → None çeviriyor, OK).
- **Edge case coverage.**
  - ✅ Snapshot 0 asset (empty portfolio): `total_tl=0`, weight_pct division-by-zero korumalı.
  - ✅ Stale Yahoo fiyat (fallback chain).
  - ⚠ **Hyperinflation senaryosu yok.** TL'nin 1 yılda 5× düştüğü dönemde `Numeric(18,2)` total_value_tl
    99,999,999,999,999.99 TL'de overflow (∼100 trilyon TL). Bugün için 1M kullanıcılı SaaS'ta high-net-worth
    user'ın 50M TL portföyü taşırma yapmaz, ama 10 yıllık enflasyonda yaklaşır. `Numeric(24,2)` daha güvenli.
  - ⚠ **Stablecoin depeg** unprotected (Not #8).
  - ⚠ **Weekend price drift.** Cuma kapanış USD fiyatı × pazartesi sabah TCMB kuru = karışık değer (Not #10).
  - ⚠ **Negatif portföy** mümkün mü? `total_value_tl` `Numeric(18,2)` signed; teorik olarak negatif (borç >
    varlık) ama snapshot servisi sadece varlık topluyor, kredi kartı borcu snapshot dışında. Doküman olarak
    not düşülmeli ("snapshot net worth değil, gross asset value").
  - ⚠ **Kur unavailable** durumunda cash USD/TRY ile yaklaşık çevriliyor (snapshot.py:196-207). EUR için
    "yaklaşık USD" varsayımı dolarda %5+ yanlış olabilir; uyarı veriliyor ama hesap dahil. **Alternatif:**
    hesap dahil etmemek + UI'de "değer hesaplanamadı" rozeti.
