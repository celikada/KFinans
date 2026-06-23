# TEFAS erişim sorunu — kök neden + dayanıklılık (2026-06-13)

> **⚠️ Not (2026-06-23):** Bu incident yazıldığında barındırma **Oracle Cloud** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, k3s v1.35, IP `91.99.123.163`). Aşağıdaki "Oracle pod/backend/IP" ifadeleri tarihsel; güncel kurulumda aynı dayanıklılık (son-iyi cache + single-flight + canlı portföy cache) geçerlidir. "Alternatifler" bölümündeki TR-proxy ifadeleri host-bağımsızdır (artık Hetzner backend için geçerli).

## Belirti
Production (kfinans.app) v0.8.4'te dashboard'da TEFAS fon kartı "yükleniyor"da
takılıyordu. Backend logu:

```
POST /api/v1/portfolio/tefas/preview duration_ms=20398 → 500
Traceback ... app/services/tefas.py:_fetch_prices ... httpx.ConnectTimeout
```

## Kök neden — GEÇİCİ kesinti (doğrulandı)
2026-06-13 sabahı (07:45–08:08) `https://www.tefas.gov.tr/api/fund-returns/export`
adresine **TCP bağlantısı kurulamıyordu** (`ConnectTimeout`, 8 kez). O an hem
Oracle K3s pod'undan hem bağımsız bir TR ağından (geliştirici makinesi) test edildi
ve **ikisi de** başarısızdı (`http=000 connect=0.000000s`) → sorun KFinans/Oracle
değil, **TEFAS sunucu tarafı**ydı.

**Aynı gün toparlandı:** prod backend logunda 19:21'de
`POST .../api/fund-returns/export "HTTP/1.1 200 OK"` (1.9s) — Oracle pod'u TEFAS'a
yeniden erişti. Ertesi gün (06-14) hem Oracle hem TR makineden 200 OK.

**Sonuç:** Kalıcı IP-block DEĞİL, **geçici TEFAS kesintisi**. Gov siteleri ara sıra
böyle kesinti/yoğunluk yaşar; tekrarlaması beklenir. (Yahoo/Glacier/CoinGecko aynı
pod'dan kesinti boyunca erişilebiliyordu — genel egress sağlıklıydı.)

## Uygulanan dayanıklılık (bu sürüm)
`backend/app/services/tefas.py`:
- **Son-başarılı fiyat cache'i** (`AsyncTTLCache`, TTL `settings.tefas_cache_ttl_sec`
  = 1 saat) + modül-seviyesi `_TEFAS_LAST_GOOD`. TEFAS erişilemediğinde boş dict
  yerine **son bilinen fiyatlar** döner (issue ile işaretli) → fon değeri ekranda
  kalır, dashboard takılmaz.
- HTTP timeout 20s → `settings.tefas_timeout` (8s) — hata hızlı yakalanır.
- Single-flight: dashboard'ın paralel TEFAS çağrıları tek upstream isteği paylaşır.

Ayrıca **canlı portföy cache'i** (`live_portfolio_cache`) sayesinde TEFAS verisi
arka planda hesaplanır; kullanıcı isteği TEFAS'a senkron bağımlı değildir.

## Alternatifler (eğer kesinti KALICI hale gelirse)
Geçici kesinti için ek bir şey yapmaya gerek yok — yukarıdaki dayanıklılık veriyi
ekranda tutar, TEFAS düzelince otomatik tazelenir. Ama TEFAS prod sunucu IP'sini
(Hetzner) **kalıcı** bloklamaya başlarsa (loglarda sürekli ConnectTimeout), seçenekler:

1. **TR-tarafı egress proxy (önerilen):** Self-hosted altyapı (GitLab/runner,
   `192.168.3.x`) bir TR ISP'sinde ve TEFAS'a erişebiliyor. Prod backend (Hetzner), TEFAS
   isteklerini bu ağdaki küçük bir HTTP proxy üzerinden geçirir (resmi veri, en
   güvenilir). Gereken: self-hosted kutuya prod backend'den erişilebilir bir reverse
   tünel/ingress (kutu NAT arkasında). `settings`'e opsiyonel `tefas_proxy_url`
   eklenip `httpx.AsyncClient(proxies=...)` ile bağlanır.
2. **Manuel NAV girişi fallback:** Uygulama zaten manuel birim fiyat destekliyor
   (manual_crypto + cost basis); TEFAS fonları için kullanıcının günlük NAV'ı elle
   girebileceği bir alan eklenebilir. Düşük teknoloji ama %100 güvenilir.
3. **Üçüncü-parti agregatörler** (fonbul/fintables/fonradar): kırılgan + ToS riski
   — önerilmez.
4. Aynı host'taki eski endpoint'ler (`BindHistoryInfo` vb.): host bloklanınca aynı
   şekilde erişilemez; ayrıca artık 404 dönüyor — işe yaramaz.

Karar: **şimdilik aksiyon gerekmez** (geçiciydi, düzeldi). Loglarda TEFAS başarı
oranı izlenir; kalıcılaşırsa (1) numaralı proxy + (2) manuel fallback uygulanır.
