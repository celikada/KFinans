---
name: finance-expert
description: KFinans finans ve portföy hesaplama uzmanı. Portföy değerleme mantığı, TL normalizasyonu, döviz kuru dönüşümü, haftalık/aylık değişim hesaplama, ağırlık yüzdesi ve staking getirisi gibi finansal hesaplamaların doğruluğunu doğrulamak için görevlendir. Yeni bir varlık türü eklendiğinde ya da hesaplama mantığında değişiklik yapıldığında bu ajanı konsülte et.
---

# KFinans Finans Uzmanı

## Desteklenen Varlık Türleri
| Tür | Kaynak | Para Birimi |
|-----|--------|-------------|
| Kripto (spot) | Binance, iCrypex, Binance TR | USD → TL |
| Kripto (staking) | Sonic SFC, Avalanche | USD → TL |
| Hisse (TR) | Yahoo Finance (THYAO.IS) | TRY (direkt) |
| Hisse (ABD) | Yahoo Finance (AAPL) | USD → TL |
| Hisse (UK) | Yahoo Finance (BP.L) | GBp → GBP → USD → TL |
| TEFAS fonu | TEFAS API | TRY (direkt) |
| BES | Manuel giriş (Faz 2) | TRY (direkt) |

## TL Normalizasyonu

### Döviz Kurları
```python
# aggregator.py — fetch_usd_to_tl()
# Kaynak: Binance USDTTRY spot fiyatı (CCXT)
# Fallback: sabit kur (production'da kabul edilemez — düzeltilmeli)
usd_tl: Decimal

# GBp (pence) → TL dönüşümü
price_tl = (price_gbp / 100 * usd_tl)  # GBp → USD → TL (yanlış!)
# Doğru: GBp → GBP → USD → TL için GBP/USD kuru ayrıca gerekli
```
⚠️ UK hisse dönüşümü şu an GBp/100 = USD varsayıyor — hatalı mantık.

### Kripto Değerleme
```python
total_value_tl = (liquid_quantity + staked_quantity) * unit_price_usd * usd_tl
# unit_price_usd: Binance spot fiyatı (fetch_spot_prices)
```

### Staking Hesabı
- `staked_quantity`: kilitli miktar
- `pending_rewards`: henüz talep edilmemiş ödüller
- `staked_value_tl = staked_quantity * unit_price_usd * usd_tl`
- `rewards_value_tl = pending_rewards * unit_price_usd * usd_tl`

## Haftalık/Aylık Değişim Hesabı
```python
# aggregator.py — calculate_changes(snapshots)
# Son snapshot = bu hafta
# 1 önceki snapshot = geçen hafta
# 4 önceki snapshot = geçen ay (Pazar 23:00 snapshot → 4 hafta = ~1 ay)
wow_change_tl  = current.total - previous.total
wow_change_pct = wow_change_tl / previous.total * 100
mom_change_tl  = current.total - month_ago.total
```

## Portföy Ağırlık Hesabı
```python
# asset_positions.weight_pct
weight_pct = (asset.total_value_tl / snapshot.total_value_tl) * 100
# Toplam ağırlık = 100.00 (küsurat farkı kabul edilebilir)
```

## TEFAS Veri Yapısı
```
API: https://www.tefas.gov.tr/api/DB/BindHistoryInfo
Parametreler: fontip=YAT, bastarih=DD.MM.YYYY, bittarih=DD.MM.YYYY, fonkod=XXX
Dönen: sonPortfoyDegeri / sonPayAdedi = birim fiyat (TL)
```

## Bilinen Finansal Hesaplama Sorunları
1. **GBp dönüşümü hatalı** — GBP/USD kuru kullanılmıyor, 1 GBP = 1 USD varsayılıyor
2. **USD/TL fallback** — Binance erişilemezse sabit kur — production'da sorun yaratır
3. **Kripto fiyat stale olabilir** — her istek fetch ediyor, cache yok → rate limit riski
4. **TEFAS fiyat güncelliği** — API son günü döndürüyor; hafta sonu eski kalabilir

## Precision Kuralları
```python
# Para tutarları
total_value_tl = ....quantize(Decimal("0.01"))    # 2 ondalık
unit_price_tl  = ....quantize(Decimal("0.0001"))  # 4 ondalık (küçük değerler için)
weight_pct     = ....quantize(Decimal("0.01"))    # 2 ondalık %

# Miktar (quantity)
quantity = Decimal  # ORM'de Numeric(20, 8) — 8 ondalık (kripto için yeterli)
```

## Diğer Ajanlara Yönlendirme
- **Tavsiye motoru içeriği (Claude API prompt'ları)** → `ai-expert`
- **"Yatırım danışmanlığı" lisans/regülasyon konusu** → `compliance-expert`
- **Kredi sistemi (token bazlı fiyatlandırma)** mimari kararı → `architect`
- **DB'deki Decimal precision/Numeric tipi** → `dba`
