# CHANGELOG

Tüm önemli değişiklikler bu dosyada tarihsel olarak kaydedilir.
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) /
Versiyon: [Semantic Versioning](https://semver.org/lang/tr/spec/v2.0.0.html).

---

## [0.10.0] - 2026-06-16

### Eklenenler

- **Abonelik PDF fatura yükleme:** ESGAZ / Vodafone / TTNET faturalarını PDF olarak yükleyince
  kurum otomatik tanınır, alanlar (abone no, tutar, fatura/son ödeme tarihi, dönem, sonraki
  fatura/son ödeme tarihi) ayıklanır. **Abonelik yoksa otomatik oluşturulur**, **varsa** (abone no
  normalize eşleşmesi) ilgili aboneliğe dönem faturası girilir (issued). Sonraki fatura/son ödeme
  tarihi aboneliğe yazılır → "fatura gir" hatırlatması daha isabetli. Kredi kartı ekstresi
  import'uyla aynı pluggable + fail-safe desen (`services/bill_import/`): tanınmayan kurum / format
  değişmiş / **taranmış görüntü-PDF (metin katmanı yok)** → 422 "elle girin"; asla tahmini veri yazılmaz.
  Önizleme (`/subscriptions/import-bill/preview`) düzenlenebilir + onay (`commit`). Sayı formatı
  otomatik (Vodafone EN `1,077.00`, diğerleri TR `1.339,25`).
- **Abonelik başlangıç tarihi (`start_date`):** Aboneliğe başlangıç tarihi eklendi; bütçe yalnız o
  tarihten itibaren nakit-akışı forecast'ında + özetlerde sayılır (geçmiş aylar hariç).
- **Bütçe planlı gider gibi görünür:** Aktif abonelik bütçeleri Giderler → Periyodik sekmesinde
  salt-okunur "🔁 abonelik" satırları olarak listelenir (düzenleme Abonelikler sekmesinde).

Yeni migration `c5d6e7f8a9b0` (start_date + next_bill/due_date + bill_no). Audit `subscription.bill.import`.
(Not: Osmangazi/Zorlu Elektrik gibi taranmış görüntü faturalar için AI-vision parser sonraki faza
bırakıldı — şimdilik elle giriş.)

---

## [0.9.0] - 2026-06-16

### Eklenenler

- **Abonelikler modülü (fatura/utility takip):** Elektrik/doğalgaz/internet/telefon
  faturalarının **abone no** ile manuel takibi — Giderler altında yeni "Abonelikler" sekmesi.
  İlk kapsam 5 kurum (ESGAZ, Zorlu Enerji, Osmangazi Elektrik, TTNET, Vodafone; katalog
  genişletilebilir). **3 durumlu yaşam döngüsü:** budget (aylık tahmini/bütçe değeri) →
  issued (fatura geldi, gerçek tutar, ödenmemiş) → paid (ödendi, gerçek gider oluşur).
  - **Ödeme şekli çift sayım:** ödeme nakit/banka ise gider toplamına girer; kredi kartı ise
    oluşan gider kaydına `credit_card_id` set edilip mevcut çift-sayım kuralıyla toplamdan
    çıkarılır (kart ekstresinde sayılır); ödenmemiş faturalar cash-flow forecast'ında kalır.
  - **Cash flow + dashboard:** abonelik forecast'ı aylık projeksiyona + Giderler kartı yıl sonu
    beklentisine eklenir.
  - **Hatırlatmalar:** son ödeme yaklaşan fatura için giriş popup + push (09:00) + e-posta (09:05);
    ayrıca "kesim günü geçti, fatura gir" hatırlatması.
  - Yeni tablolar `subscriptions` + `subscription_bills` (migration `b4c5d6e7f8a9`); yeni router
    `/subscriptions`; audit `subscription.add/update/delete` + `subscription.bill.issue/pay/unpay`.

---

## [0.8.15] - 2026-06-16

### Güvenlik

- **starlette CVE-2026-54283 (HIGH) → Trivy image gate fix:** v0.8.14 tag pipeline'ı
  `trivy-image-scan` aşamasında kırmızıydı; backend imajındaki transitif `starlette 1.3.0`
  HIGH zafiyet (`request.form()` boyut/sayı limitleri sessizce yok sayılıyor) taşıyordu.
  `pyproject.toml`'a açık `starlette>=1.3.1` alt sınırı eklendi (fastapi 0.136.3 ile uyumlu,
  import doğrulandı). Trivy gate'i yeşile döner → v0.8.14'teki "Giderler" kart birleşmesi +
  bellek limiti 2Gi fix'i nihayet deploy edilebilir.

---

## [0.8.14] - 2026-06-16

### Düzeltmeler

- **Backend OOMKilled → login kesintisi (bellek limiti 1Gi→2Gi):** Live cache + login-tetikli
  arka plan refresh (6 paralel bölüm + BTC xpub taraması, her biri ayrı session/httpx/web3
  client) bellek tepesini ~850Mi-1Gi'ye çıkarıyordu → 1Gi limitinde pod OOMKilled olup
  restart ediyor, o pencerede login erişilemiyordu. Limit 2Gi'ye (request 512Mi→768Mi)
  çıkarıldı (Oracle Ampere 24GB node'da %18 kullanım, ek maliyet yok). `k8s/backend.yaml`.

### Değişiklikler

- **Dashboard "Giderler" tek kartı (gelir simetrisi):** Ayrı "Harcamalar" + "Planlı Ödemeler"
  kartları tek **Giderler** kartında birleşti — gelir kartı gibi anlık (bu ay gerçekleşen)
  toplam + footer'da yıl sonu planlı beklenti. Tıklayınca `/dashboard/expenses` (2 sekme).
  Ayarlardaki öksüz "Planlı Harcamalar" görünürlük toggle'ı kaldırıldı.


### Eklenenler / Değişiklikler

- **Planlı harcamalar artık düzenlenebilir:** Kira, ev aidatı gibi planlı/periyodik
  harcamalar bir kez girildikten sonra düzenlenebiliyor (gelirlerdeki periyodik gelir
  deseni). `PlannedForm` edit modu (`existing` → `PUT /planned-expenses/{id}`) +
  `PlannedList`'te "Düzenle" butonu.
- **Harcamalar + Planlı Harcamalar tek sayfada (gelir simetrisi):** `/dashboard/expenses`
  artık 2 sekme: **Gerçekleşen** (anlık harcamalar + kategori disk grafiği) ve
  **Periyodik** (kira/aidat planlı harcamalar + düzenleme + dönemler). `/dashboard/planned`
  → `?tab=periyodik`'e kalıcı redirect (eski linkler kırılmaz). Dashboard "Planlı Ödemeler"
  kartı periyodik sekmesine yönlenir.
- **Planlı sayfasında grafik değişti:** Nakit-akış tahmini (`YearlyForecast`) yerine
  planlı harcamaların **kategori bazlı disk/donut grafiği** (`PlannedCategoryPieChart`,
  harcamalar sayfasıyla aynı stil) — daha okunur dağılım gösterimi.


### Düzeltmeler

- **Snapshot bayat cache'te 45 sn timeout'a takılıyordu:** Snapshot preview + create
  yalnız cache TAZE ise (≤15 dk) cache'ten üretiyordu; bayatsa eski full re-fetch
  yoluna (~45 sn) düşüp frontend 30 sn timeout'una takılıyordu → onay modal'ı
  açılmıyor/snapshot kaydedilemiyordu. Artık cache VARSA (bayat olsa bile) ondan
  üretilir — snapshot = "ekranda görünen durum" (dashboard cache'i zaten "son
  güncelleme" göstergesiyle gösterir; taze isteyen önce Yenile yapar). Cache HİÇ
  yoksa compute fallback.
- **Snapshot uyarıları (sarı ünlem) geri geldi:** Cache-tabanlı snapshot yalnız
  "çekilemeyen kaynak" (warn) notlarını saklıyordu; info/warn veri-kalitesi notları
  (hisse `stale_price`, manuel kripto `info_linked`/`no_price`, emtia erişilemez)
  kayboluyordu → yeni snapshot'larda geçmiş listesindeki sarı ünlem çıkmıyordu.
  Bu notlar artık cache refresh'inde section + DB verisinden TÜRETİLİR (yeniden
  çekim yok) ve `health_issues`'a yazılır → snapshot preview onay modal'ında gösterilir
  + snapshot kaydında saklanır + geçmişte sarı ünlemle görüntülenir (eski davranış).


### Düzeltmeler

- **Snapshot BES + Nakit'i 0 kaydediyordu:** Cache'ten üretilen snapshot yalnız
  live cache'in 6 ağır bölümünü (cüzdan/kripto/TEFAS/hisse/emtia/manuel-kripto)
  içeriyordu; BES (emeklilik) + Nakit live cache'te yok (hafif/DB kartları,
  dashboard'da ayrı çekilir) → snapshot'a hiç girmiyordu. `save_snapshot_from_cache`
  + `preview_snapshot_from_cache` artık ortak `_full_snapshot_assets` helper'ı ile
  BES + Nakit'i DB'den ekler (dış API yok; cash için TCMB kuru 5 dk cache'li) ve
  toplamı tüm asset'lerden yeniden hesaplar (preview ile save tutarlı). Regresyon
  testi eklendi.
- **Geçmiş grafiği X ekseni zaman-ölçekli:** Snapshot trend grafiği eşit-aralıklı
  kategori ekseni kullanıyordu (her snapshot arası 1 birim); düzensiz tarih aralıkları
  (ör. 5→7 Haz = 2 gün) eşit görünüyordu. X ekseni artık `type=number scale=time` →
  noktalar gerçek tarih aralıklarıyla orantılı dağılır (eksik günler boşluk olarak
  doğru genişlikte görünür).


### Düzeltmeler

- **Bitcoin GERÇEK kök neden — mempool.space Oracle'dan erişilemiyor:** BTC scan
  prod'da **0 HTTP isteği yapıp 45 sn timeout** veriyordu. Oracle VM'den test:
  `mempool.space` → `connect=0, http=000` (TCP SYN-drop; Cloudflare datacenter IP
  bloğu — TEFAS ile aynı desen). httpx istekler bağlanamadan asılıyor, hatalar
  DEBUG'da görünmüyordu. **Çözüm:** BTC artık Esplora API'sini host-fallback ile
  çağırır (`blockstream.info` primary — Oracle'dan erişilebilir; `mempool.emzy.de`
  + `mempool.space` fallback). Aynı `/api/address/{addr}` + `chain_stats` şeması →
  veri formatı değişmedi. (Litecoin `litecoinspace.org` benzer risk taşıyor →
  follow-up.)

## [0.8.9] - 2026-06-14

### Düzeltmeler

- **AsyncTTLCache zehirlenmiş inflight future (kritik — BTC kalıcı takılması):**
  Single-flight cache'in owner coroutine'i CANCEL edildiğinde (ör. cüzdan per-wallet
  45 sn timeout'u BTC taramasını keserken), cleanup `async with self._lock` (await)
  içinde yapılıyordu; cancellation sırasında lock-await yeniden `CancelledError`
  fırlatıp `_inflight.pop`'u atlatabiliyordu → ölü future dict'te kalıyor (TTL yok →
  pod restart'a kadar kalıcı). Sonraki HER tarama bu ölü future'ı sonsuz bekliyor →
  **0 HTTP isteği + sürekli 45 sn timeout** ("Bitcoin güncellenemedi" çözülemiyordu).
  Cleanup artık await'siz `finally` bloğunda (dict.pop atomik) → owner cancel edilse
  bile inflight temizlenir, sonraki çağrı taze başlar. Tüm blockchain single-flight
  servislerini korur (BTC/Avalanche-P/Solana/Litecoin/Polkadot). Regresyon testi eklendi.

## [0.8.8] - 2026-06-14

### Düzeltmeler

- **Snapshot onay modal'ı açılmıyordu / snapshot kaydolmuyordu (kritik):** "Snapshot al"
  ön-izlemesi tüm kaynakları YENİDEN çekiyordu (~45 sn) ve frontend'in 30 sn request
  timeout'una takılıp iptal oluyordu → onay modal'ı hiç açılmıyor, snapshot kaydedilemiyordu.
  Snapshot preview + create artık **taze live cache'ten** üretilir (yeniden dış çağrı YOK,
  anında). Snapshot = "şu an görüntülenen durumun" kaydı. Çekilemeyen kaynaklar (BTC vb.)
  modal'da issue olarak gösterilir; kullanıcı "yine de kaydet" diyebilir.
- **Bitcoin xpub taraması hızlandırıldı:** Adres taraması artık **bounded-parallel** (pencere
  = gap_limit, en fazla 5 eşzamanlı sorgu) — eskiden adres-adres sıralıydı (+0.3s sleep) ve
  45 sn'yi aşıp "Bitcoin çekilemedi" veriyordu. BTC bakiye cache TTL 10→30 dk (ilk başarılı
  taramadan sonra tekrar tarama seyrekleşir).

### İyileştirmeler

- **Ortak bounded-parallel fan-out helper'ı (`services/concurrency.py::gather_bounded`):**
  Sıralı kalan dış-çağrı döngüleri tek bir reusable pattern ile paralelleştirildi (her servis
  rate-limit'ine uygun `limit` verir — sınırsız paralel 429 fırtınası yaratır). Uygulandığı
  yerler: BTC xpub adres taraması, çoklu borsa (crypto), ERC-20 token (Avalanche), Yahoo hisse
  ticker'ları. NOT: cüzdan zincirleri + bölümler ZATEN paralel; TEFAS tek toplu çağrı.


### Düzeltmeler

- **TEFAS + Hisse kartları boş (kontrat uyuşmazlığı):** `compute_tefas_positions` ve
  `compute_stock_positions` düz LİSTE (`list[...PositionOut]`) dönüyordu; frontend ise
  tüm bölümleri `sections.X.positions` (yani `{positions: [...]}` nesnesi) olarak okuyor.
  Liste'nin `.positions`'ı olmadığından bu iki kart boş görünüyordu (backend veriyi 200 OK
  ile çekmesine rağmen). Live cache artık liste dönen bölümleri `{"positions": [...]}` ile
  normalize eder. Regresyon testi eklendi.

## [0.8.6] - 2026-06-14

v0.8.5 canlı portföy cache'inde prod'da çıkan hataların hotfix'i.

### Düzeltmeler

- **Canlı cache concurrency bug (kritik):** `refresh_live_cache` 6 bölümü (cüzdan/
  kripto/TEFAS/hisse/emtia/manuel kripto) AYNI DB session'ında eşzamanlı çalıştırıyordu
  → SQLAlchemy "another operation is in progress" (ilk bölüm kazanır, diğer 5 patlar) →
  dashboard'da kartlar boş geliyordu. Her bölüme artık AYRI session verilir (paralellik
  korunur). v0.8.4'te snapshot.py'de düzeltilen aynı hata.
- **Cüzdan eksik toplam:** per-wallet timeout 25→45 sn, toplam 60→90 sn. BTC/LTC xpub
  taraması + multi-RPC fallback döngüsü (avalanche_c/ethereum/sonic) 25 sn'yi aşıp
  düşüyordu → toplam eksik görünüyordu. Cömert sınır (arka plan refresh kullanıcıyı
  bloke etmez; zincirler paralel → toplam ≈ en yavaş zincir).
- **Frontend poll bütçesi 10→20** (60 sn): ~45 sn süren arka plan refresh'i yakalar.

### Eklenenler

- **Kısmi-hata bildirimi:** Bazı cüzdan zincirleri veya bölümler çekilemediğinde
  dashboard'da uyarı banner'ı ("Bazı veriler güncellenemedi: Bitcoin, Ethereum… —
  görünen toplam eksik olabilir, Yenile ile tekrar deneyin"). Sessiz düşük-toplam yerine
  kullanıcı hangi kaynağın eksik olduğunu görür.

## [0.8.5] - 2026-06-14

Dashboard'da blockchain cüzdan + TEFAS fon kartlarının "yükleniyor"da takılması
giderildi (production loglarıyla teşhis: `GET /portfolio/wallets` 373 sn,
TEFAS export geçici `ConnectTimeout`, frontend'de request timeout yokluğu).

### Düzeltmeler

- **Cüzdan dış-çağrı dayanıklılığı:** web3 (Ethereum/Sonic/Avalanche-C) RPC
  isteklerine timeout + bounded multi-RPC fallback eklendi; cüzdan fetch'ine
  per-wallet (25 sn) + toplam (60 sn) deadline. Bir ölü/yavaş RPC artık tüm
  dashboard'u kilitleyemez. ETH varsayılan RPC `eth.llamarpc.com` (521 down) →
  `publicnode`.
- **TEFAS dayanıklılığı:** son-başarılı fiyat cache'i (TEFAS erişilemese bile fon
  değeri ekranda kalır) + HTTP timeout 20→8 sn + single-flight. TEFAS erişim
  kesintisi geçiciydi (aynı gün düzeldi); kalıcılaşırsa alternatifler
  `docs/operations/tefas-erisim-notu.md`'de.
- **Frontend request timeout:** api client'a `AbortController` timeout (30 sn) —
  backend gecikse bile spinner sonsuz dönmez.

### Eklenenler

- **Sunucu-tarafı canlı portföy cache'i (`live_portfolio_cache`):** Ağır/dış-API
  verisi (cüzdan/kripto/TEFAS/hisse/emtia/manuel kripto) her dashboard açılışında
  değil, arka planda hesaplanıp cache'lenir. `GET /portfolio/live` hızlı DB
  okumasıyla döner (stale-while-revalidate); `POST /portfolio/refresh` "Yenile"
  butonu; login/MFA sonrası bayatsa arka planda tetik. Snapshot taze cache varsa
  yeniden dış çağrı yapmadan üretilir.
- **Dashboard "Yenile" butonu + "Son güncelleme" göstergesi** (ana sayfa + cüzdan/
  TEFAS/kripto/hisse/emtia/manuel-kripto detay sayfaları).

## [0.8.4] - 2026-06-13

9 paralel uzman ajan denetimi (backend/frontend/dba/security/devops/test/finance/ai/architect)
sonucu P0+P1 düzeltme turu (3 tematik MR: !49 backend, !50 frontend, !51 devops).

### Düzeltmeler

- **KK döviz para birimi (kritik):** Ekstre/taksit `currency` hiçbir yazma yolunda
  set edilmiyordu — TRY-dışı kartın ekstresi cash flow'da TRY varsayılıp ~kur-kat
  yanlış sayılıyordu, UI da tutarı `₺` ile gösteriyordu. Şemalara `currency` eklendi;
  create/update/upsert + import commit kartın para birimini ekstre+taksitlere
  devrediyor. Frontend kart detayı (ekstre/taksit/limit/önizleme) `fmtCurrency` ile
  kalemin kendi para biriminde gösteriyor.
- **Hard-delete cron (KVKK):** `credit_transactions` RESTRICT'ine takılıp TÜM
  batch'i sessizce düşürüyordu — ledger'lı kullanıcılar hariç tutuluyor + uyarı.
- **Snapshot concurrency:** Aynı AsyncSession'da 8 paralel `db.execute`
  ("another operation is in progress" riski) → sıralı await.
- **Parser hata yolu:** `InvalidOperation` yakalanmıyordu (fail-safe 422 yerine 500);
  ham PDF metni hata mesajına sızıyordu → sabit kullanıcı mesajı.
- **Web Push SSRF:** endpoint host allowlist'i eklendi (yalnız bilinen push
  servisleri; iç ağa sunucu-taraflı POST engellendi).
- **convert_forecast:** display kuru eksikse değer SIFIRLANIYORDU (kart toplamı 0
  görünebilirdi) → TL fallback. **Wallet sil:** geçersiz UUID → 500 yerine 404.
- **Crypto sayfası:** getIntegrations fetch hatası sessizce yutuluyordu → kullanıcıya
  hata gösteriliyor.

### CI/CD

- pip + npm cache (pipeline'lar arası, ~2-4 dk kazanç) + **Kaniko layer cache**
  (tag build süresi belirgin düşer) + backend Dockerfile `apt-get upgrade`
  (OS CVE birikimi → Trivy gate koruması).

---

## [0.8.3] - 2026-06-11

### Düzeltmeler

- **Ekstre PDF import — pdfplumber `(cid:N)` token'larına dayanıklılık (kritik).**
  v0.8.1'deki glyph-toleransı, harness'in PDF okumasına göre yazılmıştı (Türkçe
  harfler tamamen düşüyordu). Gerçek prod'da **pdfplumber** Türkçe-özel harfleri
  `(cid:N)` token'larına çeviriyor ("Son Ödeme Tarihi" → "Son (cid:0)deme Tarihi",
  "Mayıs" → "May(cid:0)s"). `\S{0,2}` 7-karakterlik `(cid:0)`'ı kapsayamadığı için
  Enpara dahil ekstreler **hâlâ "format tanınmadı" hatası** veriyordu. Düzeltmeler:
  - `tr_tolerant` tek-harf deseni artık `(cid:N)` token'ını da tanır (korunmuş /
    düşmüş / cid üç biçim); boşluklar `\s{1,3}` (çoklu boşluk toleransı).
  - Türkçe ay-adı tarihleri (`_TR_DATE_RE` + `parse_turkish_date` +
    `search_labeled_date`) cid token'lı ay adını çözer ("May(cid:0)s" → Mayıs).
  - Enpara `Son ödeme` / `Kart numarası`, Ziraat/Yapı Kredi taksit markerları
    (`İşlemin`/`işlemin`) tr_tolerant'a taşındı.
  - **Gerçek PDF'lerle doğrulandı:** Enpara, Ziraat (taksitli), QNB (Mayıs cid),
    Garanti — hepsi doğru parse ediliyor. cid regresyon testleri eklendi.

---

## [0.8.2] - 2026-06-11

### Güvenlik

- **Frontend image OpenSSL CVE yaması (Trivy HIGH/CRITICAL gate).** `node:20-alpine`
  base image'inin pinlediği Alpine sürümünde biriken **CVE-2026-45447** (libcrypto3 /
  libssl3 3.5.6-r0 → 3.5.7-r0, 2× HIGH) nedeniyle v0.8.1 tag pipeline'ı `trivy-image-scan`
  aşamasında durdu (deploy'a geçemedi). `frontend/Dockerfile` runner stage'ine
  `apk upgrade --no-cache` eklendi (OS paketleri yamandı); mevcut user-create + npm
  kaldırma adımlarıyla tek RUN katmanında birleştirildi (docker:S7031). Yalnız
  paketleme/güvenlik değişikliği — uygulama davranışı v0.8.1 ile aynı.

---

## [0.8.1] - 2026-06-11

### Düzeltmeler

- **Ekstre PDF import — Türkçe karakter (glyph) kaybına dayanıklılık.** Bazı banka
  ekstrelerinin PDF metin katmanı font cmap eksiği nedeniyle Türkçe-özel harfleri
  düşürüyordu ("Son **Ö**deme Tarihi" → "Son deme Tarihi", "Numara**sı**" →
  "Numaras", "Dön**em**" benzeri). Parser etiketleri bu harfleri birebir aradığı
  için ekstre "okunamadı / format tanınmadı" hatası veriyordu (ör. Enpara).
  Ortak `tr_tolerant()` yardımcısı eklendi: Türkçe-özel harf içeren tüm zorunlu-alan
  etiketleri (son ödeme tarihi, dönem borcu / hesap özeti borcu, kart numarası) artık
  hem sağlam hem glyph-düşmüş metinde eşleşir. **8 bankanın hepsi** (Ziraat, Enpara,
  Yapı Kredi, VakıfBank, QNB, Garanti, İş Bankası) + ortak `search_labeled_date`
  güncellendi. Türkçe ay adlarının glyph-düşmüş biçimleri de tanınır
  (Mayıs→Mays, Şubat→ubat, Ağustos→Austos, Eylül→Eyll, Kasım→Kasm, Aralık→Aralk).
  Tüm tuzak korumaları (Sonraki/Önceki dönem, Toplam limit) glyph-düşmüş metinde de
  korunur. Regex'ler bounded (`\S{0,2}`) → ReDoS-safe.

### İyileştirmeler

- **Kredi kartı hatırlatma popup'ı → ekstre ekleme akışı.** "Ekstre yükle" butonu
  kullanıcıyı kart detay sayfasına yönlendiriyordu ama orada PDF yükleme alanı yoktu
  (yalnız elle giriş vardı). Artık kart detay sayfasına da **PDF ekstre içe aktarma**
  paneli eklendi; popup'tan gelen kullanıcı hem PDF yükleyebilir hem elle girebilir.
  Buton metni "Ekstre yükle" → **"Ekstre ekle"** olarak güncellendi (her iki seçeneği
  kapsar).
- **Manuel kripto — pozisyon düzenleme.** Manuel kripto pozisyonları artık satır
  başındaki "düzenle" ile forma yüklenip güncellenebilir (önceden yalnız ekleme/silme
  vardı).

---

## [0.8.0] - 2026-06-07

### Eklenenler

- **4 yeni banka ekstresi (PDF) parser'ı** — kredi kartı ekstresi otomatik içe
  aktarma artık **8 banka** destekliyor:
  - **Yapı Kredi (World/Platinum):** TR sayı, Türkçe ay-adı tarih
    ("5 Haziran 2026"), "X TL'lik işlemin k / n taksidi" satırı (satıcı adı bir
    önceki işlem satırından). VakıfBank ile "Worldcard" marka çakışması:
    parser sırasında VakıfBank'tan önce gelir, Yapı Kredi'ye özgü imzayla eşleşir.
  - **QNB (QNB Fix):** EN sayı ("85,275.04"), sayısal hesap kesim + Türkçe ay-adı
    son ödeme, satır-sonu "k/n" taksit sütunu; iade (negatif) satırları atlanır.
  - **Garanti BBVA (Bonus):** TR sayı, Türkçe ay-adı tarih, iki-noktasız etiketler
    ("Hesap Kesim Tarihi 01 Haziran 2026"); taksit biçimi değişken → best-effort
    + her zaman kontrol uyarısı.
  - **İş Bankası (Maximum):** TR sayı, sayısal tarih, "Hesap Özeti Borcu" etiketi,
    bitişik "k/ntaksidi(toplam)" taksit biçimi.
- Ortak yardımcılar: `parse_turkish_date` (Türkçe ay adları → tarih) +
  `search_labeled_date` ("Bir Sonraki/Önceki ... dönem" tuzaklarını atlayan etiketli
  tarih arama). Tüm parser'larda **son dilim (k≥n) ve iade satırları** taksit
  listesine alınmaz (çift-sayım/0-kalan gürültüsü önlenir).

Fail-safe ilke korunur: tanınmayan banka → 422, eşleşip alan bulunamazsa → 422;
asla tahmini veri yazılmaz. Migration YOK (yalnız parser + test).

---

## [0.7.0] - 2026-06-06

### Değişenler

- **Tarihsel-kur bazlı çoklu para birimi raporlama (IAS 21):** Görüntüleme para
  birimi dönüşümündeki "round-trip çarpıtması" giderildi. Önceden tüm toplamlar
  TL'de sabitlenip **güncel kurla** seçili birime çevriliyordu; bu, kayıtlarını
  döviz cinsinden tutan kullanıcıda kur değişince tutarı yanlış (örn. olduğundan
  az) gösteriyordu. Artık:
  - **Gerçekleşmiş** gelir/gider kayıtları **işlem tarihindeki kurla** çevrilir
    (tarihsel TCMB kuru); kayıt birimi = görüntü birimi olduğunda **tam tutar**
    (çarpıtma sıfır), TRY görünümünde mevcut davranış birebir korunur.
  - **Tahminler** (periyodik gelir, planlı gider, kredi kartı) güncel kurla.
  - Çapraz görünümler (ör. USD kayıt → EUR) işlem-tarihi çapraz kuruyla.
  - Dönüşüm backend'e, kayıt-bazlı taşındı; frontend round-trip kaldırıldı.
    Mevcut `amount_tl` değişmedi (veri migration'ı YOK). Dashboard "Toplam
    Portföy" (yatırım, canlı) güncel kurda kalır; finans değerleri tarihsel-aware.

### Eklenenler

- **Tarihsel kur altyapısı:** `daily_rates` tablosu (TCMB tarih-bazlı kur cache,
  dinamik forward-fill — hafta sonu/tatil son iş gününe) + `historical_rates`
  servisi + günlük cron (16:00, 7. job). İlgili endpoint'ler `?display=` parametresi
  + `*_display` alanları döner (geriye uyumlu; `display=TRY` → eski davranış).

### Düzeltmeler

- Kredi kartı `currency` alanı oluşturma/güncellemede DB'ye yazılmıyordu — düzeltildi.

---

## [0.6.0] - 2026-06-06

### Eklenenler

- **E-posta ödeme hatırlatması (opt-in):** Push'a alternatif, tarayıcı/Google
  bağımsız garanti kanal. Ayarlar'dan açılır; her gün 09:05'te ödemesi ≤5 gün
  kalan/gecikmiş kredi kartı ekstreleri için doğrulanmış e-postaya hatırlatma
  gönderilir (Resend). Yalnızca opt-in + e-postası doğrulanmış kullanıcılara.
- **Sürüm gösterimi:** Ayarlar sayfasının altında kurulu uygulama sürümü
  (`vX.Y.Z`) gösterilir — hangi sürümün canlı olduğunu görmek için.

### Düzeltmeler

- **"USD karşılığı göster" yeniden çalışıyor:** Görüntüleme para birimi özelliği
  (v0.3.1) eklenince dashboard kartları `TLValue` yerine `Money` bileşenine
  geçmişti; bu yüzden "USD karşılığı göster" toggle'ı çalışmıyordu. USD karşılığı
  alt-satırı artık `Money` bileşeninde: toggle açıkken ve görüntüleme birimi USD
  değilken, değerin altında güncel kurla `≈ $X` gösterilir.

---

## [0.5.1] - 2026-06-06

### Düzeltmeler

- **Web Push hata mesajları:** Bildirim açma başarısız olduğunda gerçek hata
  artık konsola loglanır; `AbortError` (tarayıcının push servisi devre dışı, ör.
  Brave'de Google push kapalı) için kullanıcıya eyleme dönük açıklama gösterilir.
  Test bildirimi gönderiminde abonelik bulunamazsa (sent=0) yanıltıcı "gönderildi"
  yerine net mesaj verilir.
- **Service worker navigasyon hatası:** Catch-all `NetworkOnly` kuralı sayfa
  gezinmelerini (document) yakalayıp çevrimdışıyken `no-response` üretiyordu;
  navigasyonlar artık SW'yi atlar (tarayıcı yönetir).

### Altyapı

- **VAPID anahtarları SealedSecret'a alındı** (GitOps): prod VAPID artık
  `k8s/sealed-secrets.yaml`'dan gelir; canlı patch'in ileride düşme riski kapandı.

---

## [0.5.0] - 2026-06-05

### Eklenenler

- **Telefon bildirimleri (Web Push):** Kullanıcı Ayarlar'dan "Telefon Bildirimleri"ni
  açarak push aboneliği oluşturur; uygulama kapalıyken bile ödeme hatırlatması alır.
  **Mağaza gerekmez** — standart Web Push API + VAPID (App Store/Play Store yok).
  Android Chrome'da tam; iOS'ta yalnız "Ana ekrana eklenmiş" PWA + iOS 16.4+. Her gün
  09:00'da (Europe/Istanbul) ödemesi ≤5 gün kalan/gecikmiş kredi kartı ekstreleri için
  tek özet bildirim gönderilir. Backend: `push_subscriptions` tablosu + `/push/*`
  endpoint'leri (`vapid-public-key`, `subscribe`, `unsubscribe`, `test`) + `pywebpush`
  + günlük cron. Frontend: Ayarlar toggle'ı + service worker `push`/`notificationclick`
  handler'ları + iOS uyarısı. Süresi dolmuş abonelikler (404/410) otomatik temizlenir.
  Bildirim yalnızca izin veren kullanıcıya gider; VAPID anahtarı yoksa servis no-op.

---

## [0.4.1] - 2026-06-05

### Eklenenler

- **Nakit akışı ay detayı:** Nakit akışı sayfasında bir aya (tablo satırı veya
  grafik) tıklanınca, o ayın gelir/gider TOPLAMINI oluşturan kalemler tek tek
  listelenir (popup): gerçekleşen gelir/gider, kredi kartı ekstreleri ve tahmini
  kalemler (periyodik gelir, planlı gider, **kredi kartı taksitleri**). Taksit
  kalemleri "kalan/toplam dilim + ilk vade" bilgisiyle gösterilir — taksit
  projeksiyonu şeffaflaşır. Toplamlar yıllık nakit akışı tablosuyla bire bir
  tutar (aynı çift-sayım/pending/taksit kuralları). `GET /cash-flow/{year}/{month}/detail`.

### Değişenler

- **Kredi kartı hatırlatma popup'ı artık günde 1 kez:** Her dashboard açılışında
  değil, günde en fazla bir kez gösterilir (localStorage). Ödeme yaklaşıyor eşiği
  7 → **5 gün** (son ödeme tarihine ≤5 gün kalan veya gecikmiş ödemeler).
- **Taksit adı temizliği (tüm bankalar + manuel):** İçe aktarılan/saklanan taksit
  açıklamasından dilim göstergeleri ("(1/4)" eki, "01.Tak", "2. Taksit",
  "Sonradan Taksit") çıkarılır; geriye temiz satıcı adı kalır (ör. "01/06
  IYZICO/HOYA TURKEY 01.Tak İSTANBUL (1/4)" → "01/06 IYZICO/HOYA TURKEY İSTANBUL").
  Kayıt zaten kalan dilimleri temsil ettiği için bu işaretler yanıltıcıydı.

### Düzeltmeler

- **Ay detayı popup'ı saydam görünüyordu** → opak beyaz kart + koyu backdrop.
- **`npm run dev` restart döngüsü:** PWA (Serwist) webpack config'i Next 16
  Turbopack ile çakışıp `next dev`'i bozuyordu; `turbopack: {}` ile giderildi
  (dev Turbopack'te hızlı kalır, prod build `--webpack` etkilenmez).

---

## [0.4.0] - 2026-06-05

### Eklenenler

- **Kurulabilir PWA (mobil uygulama temeli):** Frontend artık Progressive Web App.
  Kullanıcı telefonda (Android Chrome / iOS Safari) "Ana ekrana ekle" ile uygulamayı
  yükleyebilir; standalone (tarayıcı çubuğu olmadan) tam ekran açılır. `@serwist/next`
  ile service worker, web app manifest (`/manifest.webmanifest`), uygulama ikonları
  (192/512/maskable/apple-touch) ve çevrimdışı fallback sayfası (`/offline`) eklendi.
  **Finansal veri güvenliği:** API yanıtları (`/api/*` portföy/bakiye) **asla**
  service worker cache'ine alınmaz (`NetworkOnly`) — yalnızca statik asset ve uygulama
  kabuğu cache'lenir; bayat finansal veri gösterilmez. CSP'ye yalnızca `worker-src 'self'`
  + `manifest-src 'self'` eklendi (wildcard yok). Tek kod tabanı — ayrı native proje yok.

---

## [0.3.7] - 2026-06-05

### Düzeltmeler

- **Kredi kartı taksit çift sayımı:** Ekstre import'unda taksitli alışverişin
  o ekstrede görünen dilimi zaten ekstre toplamında olduğu için ayrıca taksit
  projeksiyonu olarak da sayılıyordu (çift sayım); ayrıca her ay yeni ekstre
  yüklendiğinde aynı alışveriş yeni satır olarak ekleniyordu. Artık taksit kaydı
  yalnızca **gelecek** dilimleri temsil eder; her yeni ekstre yüklemesinde ilgili
  ay realize olduğundan plan ilerletilir (o ayın projeksiyonu kaldırılır). Nakit
  akışı ve toplam borç hesapları buna göre düzeltildi.

---

## [0.3.6] - 2026-06-05

### Eklenenler

- **Kredi kartı hatırlatma popup'ından "Ödendi" işaretleme:** Girişteki ödeme
  hatırlatma satırından, ilgili ekstreyi tek tıkla ödendi olarak işaretleme
  (satır listeden düşer).

---

## [0.3.5] - 2026-06-05

### Eklenenler

- **Kredi kartı hatırlatma popup'ı (girişte):** Hesap kesim tarihi gelmiş ama o
  dönemin ekstresi yüklenmemiş kartlar için "ekstre yükle" hatırlatması; ayrıca
  son ödeme tarihi yaklaşan (7 gün) veya geçmiş, henüz ödenmemiş ekstreler için
  ödeme hatırlatması.
- **Google Takvim'e ekleme (opsiyonel):** Ödeme hatırlatmalarında, son ödeme
  tarihini tek tıkla Google Takvim'e etkinlik olarak ekleme bağlantısı (hesap
  bağlama/yetki gerekmez — ön-doldurulmuş takvim ekranı açılır).

---

## [0.3.4] - 2026-06-05

### Eklenenler

- **Periyodik gelir dönem yönetimi:** Planlı giderlerdeki gibi, periyodik
  gelirlerde de "Dönemler" ekranından her dönemi gerçekleşti/gerçekleşmeyecek
  işaretleme ve yanlış işareti geri alma (realize → income silinir, skip → geri
  alınır).

---

## [0.3.3] - 2026-06-05

### Düzeltmeler

- **Nakit akışı bu ay:** Ödeme günü ay içinde ileride olan (henüz gerçekleşemeyen)
  periyodik kira/aidat gibi giderler nakit akışında ne gerçek ne tahmini gider
  olarak görünmüyordu (arada kayboluyordu). Artık "tahmini gider" olarak sayılır;
  gelir tarafı da simetrik.

---

## [0.3.2] - 2026-06-05

### Eklenenler

- **Sürüm bildirimi otomasyonu:** Yeni sürüm deploy edildikten sonra, opt-in
  kullanıcılara bu CHANGELOG'tan ilgili sürümün notlarının e-posta ile
  gönderilmesi yarı-otomatik hâle geldi (deploy hattında manuel onaylı adım).

---

## [0.3.1] - 2026-06-05

### Eklenenler

- **Görüntüleme para birimi:** Ayarlar'dan seçilen para birimi artık tüm
  toplamları (dashboard kartları, grafikler, finans sayfaları) o birimde
  gösterir; güncel TCMB kuruyla çevrilir. Tek tek gelir/gider kayıtları kendi
  giriş para biriminde kalır (maaş TRY → TRY, kira USD → USD).
- **Planlı harcama dönem yönetimi:** Yanlış işaretlenen "gerçekleşti /
  gerçekleşmeyecek" dönemleri geri alma (dönem listesi + tek tıkla geri al).
- **Ayarlarda varsayılan/görüntüleme para birimi** seçici.
- **Dashboard kart-bazlı "güncelleniyor" göstergesi** — başka ekrandan dönüşte
  hangi kartın verisi yenileniyor görünür.

### Düzeltmeler

- Bekleyen periyodik kayıt popup'ındaki etiketler Türkçeleştirildi.

---

## [0.3.0] - 2026-06-04

### Eklenenler

- **Çoklu para birimi omurgası:** Gelir, gider, planlı ödeme, periyodik gelir,
  bütçe ve kredi kartı kayıtları TRY/USD/EUR/GBP/CHF/JPY girilebilir. Kayıtta
  varsayılan para birimi gelir; toplamlar TCMB kuruyla TL'ye çevrilip toplanır.
  Gerçekleşmiş kayıtlar işlem-anı kuruyla sabitlenir, tahminler güncel kurla
  hesaplanır.

### Güvenlik

- Kredi kartı ekstresi parser regex'leri ReDoS'a karşı sınırlandırıldı.

---

## [0.2.0] - 2026-06-04

### Eklenenler

- **Sürüm bildirimleri (release notes maili):** Prod'a yeni sürüm çıkınca opt-in
  kullanıcılara bu CHANGELOG'tan ilgili sürümün notlarını e-posta ile gönderir.
  Kayıt sırasında açık rıza (varsayılan KAPALI, önceden işaretli değil); mail
  içindeki bağlantıdan veya Ayarlar sayfasından abonelikten çıkılabilir. Sadece
  e-postası doğrulanmış ve opt-in olan kullanıcılara gönderilir.
- **Kredi kartı ekstresi (PDF) içe aktarma:** Banka ekstresi yüklenip kart, ekstre
  ve taksitler otomatik doldurulur (Ziraat, Enpara, VakıfBank, Akbank/Axess).
  Tanınmayan veya biçimi değişmiş ekstrelerde tahmini veri yazılmaz, kullanıcı
  uyarılır.
- **Periyodik gelir/gider gerçekleşme akışı:** Düzenli kayıtların belirli bir ay
  için gerçek kayıt üretmesi, giriş popup'ı ile bekleyen dönemlerin onaylanması
  ve dönem bazlı atlama (skip).
- **Kredi (ledger) altyapısı:** `credit_transactions` defteri ve harcama AI
  analizi endpoint'i (3 kredi).

### Değişenler

- **Çift sayım kuralı:** Kredi kartından yapılmış ve ödenmiş harcamalar, kart
  borcuyla zaten sayıldığı için ham gider toplamlarından hariç tutulur.

### Güvenlik

- `users.is_admin` rol flag'i (sürüm bildirimi gönderme yetkisi için).

---

## [Unreleased] — develop branch

### Kod Kalitesi + CI Sertleştirme (2026-06-01)

SonarQube quality gate'i gerçek BLOCKING kapıya çevirme oturumu; coverage
ölçüm kök nedeni düzeltildi, ~800 test eklendi, bir production bug giderildi
ve `v0.1.0-rc10` Oracle K3s'e deploy edildi.

#### Changed — CI/CD + kalite

- **SonarQube gate artık BLOCKING:** `.gitlab-ci.yml` `sonarqube-scan` job'ında
  `-Dsonar.qualitygate.wait=true` + `allow_failure` kaldırıldı. Gate kırmızı
  olursa scanner exit≠0 → pipeline durur. Self-hosted host
  `http://sonar.192.168.3.191.nip.io`, **projectKey=`KFinans`** (SonarCloud.io
  DEĞİL; `sonar-project.properties` değerleri CLI ile override edilir). Gate 4/4
  yeşil: `new_violations=0`, `new_security_hotspots_reviewed=100%`,
  `new_coverage≈%96.3`, duplications OK.
- **Coverage greenlet config (kök neden fix):** `pyproject.toml
  [tool.coverage.run] concurrency = ["greenlet", "thread"]` eklendi. Async
  FastAPI handler'ları SQLAlchemy async (greenlet) bağlamında çalıştığı için
  coverage.py API katmanını "çalışmadı" sayıyordu → ölçülen kapsam yapay
  %57.89'du. Fix sonrası gerçek kapsam görünür oldu.
- **26 SonarQube violation kapatıldı:** 21 refactor + 5 gerekçeli `NOSONAR`.
- **Branch hijyeni:** GitHub (`celikada/KFinans`) salt-okunur mirror — yalnızca
  `develop`/`main`/tag push edilir; feature branch'ler sadece GitLab'a gider.
  GitHub'da `develop`+`main` protected.

#### Added — Test kapsamı

- **~800 yeni test:** blockchain + exchange servisleri, snapshot/aggregator,
  API endpoint katmanı ve frontend (vitest — `lib/api` %100, login/security
  sayfaları %98-100). Backend coverage **%57.89 → %95.83**. Mevcut sayılar:
  ~1180 backend pass + 202 frontend pass.

#### Fixed — Hata düzeltmeleri

- **Wallets export 500 (production bug):** `GET /portfolio/wallets/export`
  Content-Disposition header'ındaki `ı` (U+0131) karakteri latin-1 encode
  edilemiyordu (`UnicodeEncodeError` → 500). Dosya adı ASCII'ye çekildi.
- **2 flaky test (tarih/timezone bağımlı):** income realize testleri ay dönümü
  ve UTC/Istanbul kayması nedeniyle bazı tarihlerde kırılıyordu →
  `Europe/Istanbul` tz + dinamik dönem hesabı ile deterministik hale getirildi.

#### Deploy

- **`v0.1.0-rc10` Oracle K3s'e deploy edildi** (GitLab CI deploy stage, elle).
  Smoke testler yeşil, production sağlıklı.

> **Not:** GitHub flag #4360519 hâlâ aktif (2026-06-01 doğrulandı: workflow
> görünür + Actions enabled ama 0 run). Kalıcı mitigasyon: GitLab-primary CI +
> self-hosted SonarQube.

### FAZ H — Production Öncesi Sertleştirme (2026-05-06 → 2026-05-10)

FAZ G audit'i 240 bulgu raporladı; FAZ H'de 50+ issue kapatıldı (17 critical
kod + 33 high + ek doc/test). Production deploy önünde kod-tarafı blocker
kalmadı; 3 critical KVKK kullanıcı aksiyonu (#11/#12/#13) bekliyor.

#### Added — Yeni özellikler / endpoint'ler

- **AI tavsiye motoru SPK uyumlu** (#8 AI-003 + #10 AI-008): system prompt
  ~1500-2000 tokene çıkarıldı (Anthropic prompt cache aktif), zorunlu
  disclaimer footer + post-processing safety net.
- **Anthropic özel açık rıza** (#9 AI-005): `users.anthropic_consent_at` +
  `_version`. POST/DELETE `/user/anthropic-consent`. `/advice/generate`
  LLM çağrısından önce 403 gate (KVKK m.9).
- **AI kredi tüketim mantığı** (#41 AI-007): `ADVICE_COST=1` sabit, 402
  yetersiz kredi, slowapi 5/hour, atomik düşüm + `credits_used` kaydı.
- **Anthropic prompt cache metrikleri** (AI-002): `investment_advice.cache_read_tokens`
  + `cache_creation_tokens` kolonları, log'a metrik yazımı.
- **Advisor audit log** (AI-004): `ADVICE_GENERATE` action — KVKK m.12 üçlü
  taraf veri aktarımı izleme.
- **Password reset endpoint'leri** (#27 SEC-001): OWASP Forgot Password
  Cheat Sheet uyumlu `/auth/forgot-password` + `/auth/reset-password`,
  1 saat TTL, token rotation, generic 202 (kullanıcı enumeration engeli),
  lockout state clear. 8 yeni test.
- **Account lockout** (#28 SEC-002): `users.failed_login_count` +
  `locked_until`. 10 deneme = 15 dk kilit (OWASP ASVS V2.2.1). 423 Locked +
  Retry-After header.
- **Veri taşınabilirliği** (#42 COMP-003): `GET /user/data-export` JSON dump
  16+ tablo (KVKK m.11/d, GDPR Art.20). Audit `DATA_EXPORT`.
- **Açık rıza geri çekme** (#44 COMP-006): `overseas_consent_at`,
  `terms_accepted_at`, `kvkk_read_at` timestamp kolonları (KVKK m.5/1
  ispat yükü). `DELETE /user/consent/overseas`.
- **E-posta değiştirme** (#48 COMP-029): `email_change_new` + `email_change_token`
  (1 saat TTL). `POST /user/email/request` + `GET /user/email/confirm`
  (KVKK m.11/d düzeltme hakkı).
- **18+ yaş doğrulama** (#46 COMP-010): `RegisterRequest.age_confirmed`
  zorunlu (KVKK Kurul kararı 2018/482, TMK m.16). Frontend register'a
  zorunlu checkbox.
- **30 gün hard-delete cron** (#43 COMP-004): `_hard_delete_expired_users_job`
  her gün 04:00 (KVKK m.7). FK CASCADE + `audit_logs.user_id ON DELETE SET NULL`.
- **audit_logs retention cron** (#67 COMP-022): her gün 04:30, 365 gün TTL
  (KVKK m.7). PII fiziksel silme.
- **Veri ihlali müdahale planı** (#49 COMP-021): `docs/legal/incident-response-plan.md`
  ISO 27035 esinli, KVKK m.12/5 + GDPR Art.33 uyumlu. T+0..T+1 hafta timeline,
  KVKK Kurul + kullanıcı + basın şablonları, yıllık tatbikat (Ocak ayı).
- **Yahoo stale price detection** (#61 FIN-004): `StockQuote.is_stale` +
  `market_state`. `regularMarketTime > 30 saat` veya `chartPreviousClose`
  fallback halinde uyarı + UI rozet.
- **Cash flow özet kartı** (kullanıcı isteği): Dashboard header'a Toplam
  Portföy yanına bu ay + gelecek ay net (gelir − gider) Finans (Net Bakiye)
  kartı. Pozitif yeşil, negatif kırmızı.
- **Yükleniyor spinner**: Toplam Portföy başlığı yanında kripto + cüzdan
  loading durumunda spinner.
- **CHANGELOG.md** (#68 DOC-010): Bu dosya.
- **File upload magic-byte + size limit** (#83 SEC-009): 10 Excel import
  endpoint (BES + commodity + income + expenses + manual_crypto + wallets
  + stocks MKK + stocks manuel + tefas MKK + tefas manuel) artık ortak
  `app/core/upload_validation.py::validate_excel_upload()` kullanır.
  3 katmanlı: extension (case-insensitive), boyut (`settings.max_upload_size_mb`
  default 5MB → 413), magic byte (`.xlsx`=ZIP `PK\x03\x04`, `.xls`=OLE2
  `\xD0\xCF\x11...`). Polyglot saldırısı engellendi (evil.xlsx PDF payload).
  10 unit + 100 regression test.
- **Confirm dialog (a11y + i18n)** (#82 FE-013): Native `window.confirm()`
  13 yerde kaldırıldı → `ConfirmDialogProvider` + `useConfirm()` async hook.
  Dialog: `role="alertdialog"`, `aria-modal`, `aria-labelledby/describedby`,
  `useFocusTrap` (A11Y-001 hook reuse), Esc kapatma, `autoFocus` confirm
  butonuna. `destructive` flag kırmızı/mavi buton seçer. i18n: `common.*`
  dictionary'den. Bir yeni @smoke test (alertdialog Esc).
- **Exception detail sanitization** (#81 SEC-007): 5 endpoint'te
  `detail=f"...{e}"` ham exception interpolation kaldırıldı.
  `logger.exception(...)` full trace ops log'a; client'a generic Türkçe
  mesaj. Etkilenen: manual_crypto (price + USD/TL + Excel import),
  portfolio (snapshot preview + create). tefas.py:88 ValueError korundu
  (user-input echo, dokumante). 4 yeni integration test (DB URL/SQL/
  secret leak'i regression önler). BACK-008 generic handler tamamlayıcı.
- **i18n turn 1 dashboard + register tam çeviri** (#80 i18n-002 kısmi):
  17 dashboard sayfa PageHeader title (`t("pages.xxx")`), dashboard ana
  sayfa kart başlıkları + ipuçları (10+ kart), Finans grubu (Net Bakiye,
  ay isimleri), Portföy grubu (Geçmiş, Snapshot al), register sayfası
  tam çeviri (14+ string), history sayfası header, LanguageSwitcher
  auth sayfalarında. Dictionary genişletmesi: pages + months + categories
  + auth.* (register-spesifik 14+ key). Geriye form içi etiketler +
  tablo başlıkları + legal + email templates kaldı (incremental).
- **Production smoke test genişletme** (#79 DEPLOY-001):
  `release.yml::smoke-test` job Playwright'tan ÖNCE 4-step curl gate
  çalıştırır (~5 sn): frontend up, /health JSON, /auth/login bogus → 401,
  HSTS + X-Frame + CSP. Curl fail = deploy gate. Lokal runner:
  `frontend/scripts/smoke.sh` + `npm run smoke`. 2 yeni @smoke test
  (security headers + i18n switcher). docs/09-altyapi-test.md güncel.
- **i18n switcher overlap düzeltmesi**: TR/EN switcher dashboard
  layout'ta fixed-position'dan dashboard header'ına ve PageHeader'ına
  taşındı (kullanıcı geri bildirimi: Ayarlar/Çıkış üstüne biniyordu).
- **EN dil desteği foundation** (#78 i18n-001): Client-side cookie tabanlı
  TR/EN. `app/_i18n/dictionaries/{tr,en}.json` (auth + common + legal +
  footer anahtarları), `I18nProvider` React Context (`kfinans-locale`
  cookie, samesite=lax, 1 yıl), `useTranslation()` hook + `t("auth.login")`,
  `LanguageSwitcher` segmented (dashboard top-right + login top-right).
  Eksik anahtarlar key fallback. `<html lang>` dinamik güncelleme (ekran
  okuyucu duyurur). Login sayfası tam çevrildi (proof of concept). 16
  dashboard sayfası TR-only kaldı — incremental ileride. `app/[lang]/...`
  routing kullanılmadı (foundation için cookie context yeterli).
- **Sentry + OpenTelemetry distributed tracing** (#77 OBS-001):
  `app/observability.py::init_sentry/init_otel` `main.py` lifespan startup'ta
  çağrılır. Hepsi opt-in: `SENTRY_DSN` boş = no-op; `OTEL_ENDPOINT` boş = no-op.
  Sentry FastAPI + SQLAlchemy integration (exception capture, breadcrumb,
  perf monitoring, `send_default_pii=False` KVKK güvenli). OTel: FastAPI +
  SQLAlchemy + asyncpg + httpx instrumentation, `OTLPSpanExporter` HTTP.
  `traces_sample_rate` default %10. 7 yeni unit test (192 toplam unit).
  Frontend Sentry (`@sentry/nextjs`) ayrı issue.
- **Erişilebilirlik temel eklemeler** (#76 A11Y-001): `<html lang="tr">`,
  dashboard layout'ta sr-only "Ana içeriğe atla" skip-link, `useFocusTrap`
  hook (Tab/Shift+Tab modal döngüsü + Esc + initial focus restore),
  `SnapshotIssuesModal` aria-labelledby/describedby + focus trap, login
  formu `htmlFor` + `autoComplete=email|current-password` + error toast
  `role="alert" aria-live="assertive"`. 11 dosyada icon-only `✕` butonlarına
  aria-label + `<span aria-hidden="true">` + `focus-visible:ring-2`. 4 yeni
  Playwright @smoke test (`a11y.spec.ts`). Axe-core entegrasyonu ileride.
- **Request timing middleware** (#75 PERF-004): `RequestTimingMiddleware`
  her response'a `X-Response-Time` header'ı ekler; `>= 500ms` requestler
  WARNING log'a yazılır. Per-route ring buffer (deque maxlen=1000,
  template path ile gruplanır). `GET /api/v1/metrics/performance`
  token korumalı snapshot endpoint'i (p50/p95/p99/max + slow_count).
  OBS-001 (Sentry/OTel) eklenince deprecate edilebilir.

#### Changed — Mevcut davranış değişiklikleri

- **CI coverage gate** (#55 TEST-007): Line %50 → %60, branch %50, critical
  path (auth/security/masking) %90.
- **DB connection pool** (#33 DBA-004): pool_size=20, max_overflow=10,
  recycle=1800, pool_pre_ping. Multi-replica güvenli.
- **FK ondelete** (#31 DBA-001): integrations/wallets/snapshots/asset_positions/
  advice CASCADE; asset_positions.wallet_address_id + advice.snapshot_id
  SET NULL (history koru). Migration `f7a8b9c0d1e2`.
- **TEFAS fiyat helper** (#20 ARC-001): `_fetch_tefas_prices_for_codes`
  `app/api/v1/manual_crypto.py`'tan `app/services/tefas.py::fetch_tefas_prices_by_codes`'a
  taşındı (dependency inversion).
- **Snapshot job paralelizm** (#21 ARC-003): `asyncio.gather + Semaphore(5)`;
  100 user × 30sn → ~10 dk.
- **Multi-replica scheduler safety** (#23 ARC-011): `SCHEDULER_ENABLED` env
  + `pg_try_advisory_lock` defence-in-depth.
- **Multi-replica rate limit** (#29 SEC-003): `slowapi` Redis backend
  (`settings.redis_url`). K8s `replicas: 2 → 1` (Redis enable olana kadar).
- **WalletOut + WalletPositionOut address mask** (#26 BACK-013): Pydantic
  `field_serializer` ile `mask_address` (ilk 6 + son 4). xpub leak engeli.
- **Generic exception handler** (#22 ARC-006 + #25 BACK-008): main.py'a
  `IntegrityError → 409`, `SQLAlchemyError → 500 db_error`, `Exception →
  500 internal_error`. Hepsi `{detail, code, request_id}` sanitized format.
- **Snapshot endpoint response_model** (#24 BACK-001): `SnapshotPreviewOut`
  schema, `create_snapshot` dual-type fallback kaldırıldı.
- **Dashboard layout**: Finans grubu yukarı, Portföy aşağı; Snapshot al +
  Geçmiş butonları Portföy başlığı yanında, Nakit Akışı butonu Finans
  yanında (kullanıcı isteği).
- **Dashboard refactor** (#35 FE-003): page.tsx 971 → 654 satır. 3 component
  extraction (`icons.tsx`, `DashboardCard.tsx`, `SnapshotIssuesModal.tsx`).
- **Dashboard fetch orchestration** (#36 FE-004): 14 silent
  `.catch(() => {})` → `safe(label, fn)` wrapper + `cancelled` flag +
  `Promise.allSettled` orchestration.
- **DB izolasyon** (#53 TEST-004): function-scoped TRUNCATE autouse fixture
  her test sonunda. Testler artık kümülatif değil.
- **Migration test pattern** (#32 DBA-003): subprocess + `fresh_db` fixture
  ile alembic upgrade/downgrade round-trip 4 step.

#### Fixed — Hata düzeltmeleri

- **TCMB stale price USD fallback** (#58 FIN-005): Yahoo fail durumunda son
  bilinen USD fiyatına düş.
- **TCMB multi-currency cache** (#59 FIN-007): Cash holding GBP/USD/EUR
  TCMB rate cache (300s TTL).
- **unit_price_tl Numeric(28,10)** (#60 FIN-018): SHIB/PEPE mikro fiyat
  hassasiyeti (önce Numeric(18,4) yetersizdi).
- **Anthropic exception → HTTP status** (#38 AI-001): RateLimitError → 429
  Retry-After, APITimeoutError → 504, APIConnectionError → 503,
  AuthenticationError → 500, BadRequestError → 500, OverloadedError → 503.
- **JWT refresh rotation race** (TEST-005): rotation idempotency sequential
  test. Concurrent paralel test ASGITransport limit nedeniyle skip.
- **Yahoo Finance graceful degradation** (TEST-005): timeout / connect /
  malformed JSON / 5xx hepsi `_fetch_one` None döner.
- **CSP dev fix**: `next.config.ts` `connect-src` localhost:8000'a izin
  verir, `upgrade-insecure-requests` sadece prod. Dev'de "Failed to fetch"
  hatası düzeldi.

#### Security — Güvenlik düzeltmeleri

- **Wallet xpub Fernet** (FAZ C1): `wallet_addresses.address_encrypted` +
  `address_fingerprint` (SHA-256). `@hybrid_property` transparent
  decrypt/encrypt. Migration `b3c4d5e6f7a8`.
- **SecurityHeadersMiddleware** (FAZ C2): HSTS (1 yıl + preload), X-Frame
  DENY, X-Content-Type-Options, Referrer-Policy, CSP `default-src 'none'`,
  Permissions-Policy, COOP, CORP, Server maskeleme.
- **TrustedHostMiddleware** (FAZ C3): `settings.allowed_hosts` env'den.
  Host header injection koruması.
- **JWT TTL prod 30 dk + Refresh rotation** (FAZ C4): Prod 30 dk access;
  `/auth/refresh` her çağrıda eski refresh `jti` blacklist'e atar.
  Frontend single-flight refresh + 401 retry.
- **revoked_tokens cleanup cron** (FAZ C5): APScheduler her gün 03:00
  Europe/Istanbul.
- **Audit log altyapısı** (FAZ C6): `audit_logs` tablo + 10 hook (auth,
  wallet, integration, snapshot, account, advice, email_change, consent,
  data_export, password_reset). `GET /audit-logs` IDOR korumalı.
- **X-Forwarded-For spoofing engeli** (#30 SEC-004): `_client_ip` sadece
  `request.client.host`. Production Dockerfile CMD `--proxy-headers
  --forwarded-allow-ips="10.0.0.0/8,127.0.0.0/8"`.
- **Wallet xpub Excel mask** (#47 COMP-024): default maskeli; full xpub
  opt-in `?include_full_address=true` audit'li.

#### Test — Kapsam genişlemesi (FAZ H sonu)

- **192 unit test** (FAZ G öncesi 60'lı seviye; FAZ H ile 192).
- **357 integration test** (FAZ G öncesi 200'lü seviye; FAZ H ile 357).
- **TEST-001 + TEST-020** servis unit test'leri: audit (10), bitcoin (8),
  solana (5), reports (11), evm_tokens (17), simple_rest blockchain (9),
  binance (10), email (8), advisor (19), aggregator/exchange/security/
  stocks_currency/stocks_stale_price/limiter/negative_paths.
- **TEST-011** endpoint testleri: credit_cards (15 + çift sayım regression),
  stocks (8), tefas (8).
- **9 KVKK + auth test** (consent + email change + password reset + lockout).
- **4 migration round-trip test** (alembic upgrade/downgrade subprocess).

---

## [0.1.0] — 2026-05-06 (FAZ B sonu, repo public)

### Added (Faz 1+2+3 MVP özeti)

- Backend FastAPI iskeleti, JWT auth, slowapi rate limiting
- TEFAS, kripto (Binance/iCrypex), 10 blockchain (Bitcoin, Ethereum, Sonic,
  Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin), hisse
  (Yahoo Finance), kıymetli madenler (TCMB + Yahoo), BES manuel
- Manuel kripto modülü (API'siz borsalar — BinanceTR/iCrypex/BTCTurk vs.)
  3 fiyat modu (auto/manual/linked) + asset catalog autocomplete
- Harcama/gelir/bütçe/planlı ödemeler/finansal hedef/recurring income/
  realize akışı
- Kredi kartları (kart + ekstre + taksit nested CRUD; çift sayım kuralı)
- Nakit/banka (manuel; TRY/USD/EUR/GBP TCMB ile TL'ye normalize)
- Yıllık nakit akış projeksiyonu (recharts ComposedChart + xlsx/pdf rapor)
- Snapshot health/usd_try_rate (haftalık snapshot servisi)
- MKK e-Yatırımcı Excel import (xlrd 1.2.0)
- Frontend Next.js 16 dashboard, login, register, 17 alt sayfa
- Docker Compose dev + Kubernetes prod (Oracle Cloud Always Free + K3s)
- 6 GitHub Actions workflow (ci-backend, ci-frontend, e2e, security, sonar,
  release)
- Apache-2.0 LICENSE + SECURITY.md + CONTRIBUTING.md + CODE_OF_CONDUCT.md
- KVKK Aydınlatma Metni + Kullanım Şartları + Gizlilik Politikası +
  Çerez Politikası taslak

---

> **Not:** v0.1.0 öncesi "Faz" başlıkları (Faz 1, 2, 2.5, 3, A, B, C, D, E,
> F, G, H) `docs/01-tasarim-dokumani.md` §7-8'de detaylanır.
> Production v1.0.0 release planı: COMP-001/002/005 kullanıcı aksiyonları
> tamamlandıktan sonra (`gh release create v1.0.0`).
