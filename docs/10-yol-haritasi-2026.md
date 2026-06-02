# 10 — KFinans Yol Haritası 2026 (Rekabet Analizi + Ürün Stratejisi + Teknik Plan)

> **Amaç:** KFinans'ı pazardaki muadilleriyle kıyaslayıp (1) rakiplerde olup bizde
> eksik nitelikli özellikleri kapatmak, (2) mevcut özellikleri iyileştirmek,
> (3) **kimsede olmayan ama Türk kullanıcının gerçek ihtiyacına cevap veren**
> farklılaştırıcı özellikler eklemek için somut, teknik bir yol haritası.
>
> **Tarih:** 2026-06-02 · **Sürüm:** v0.1.0-rc16 (production canlı) → hedef v1.0.0 ve sonrası.
> Bu belge `docs/02-mimari.md` ve `docs/05-ai-ve-finans.md` ile birlikte okunmalıdır.

---

## 1. Yönetici Özeti

KFinans bugün **işlevsel olarak çalışan, production'da canlı, güvenlik-sertleştirilmiş**
bir kişisel net worth + finans agregatörü. Pazar analizinde ortaya çıkan tablo:

- **Global muadiller** (Kubera, Finary, Empower, Monarch) güçlü ama **Türkiye varlık
  ekosistemine kör** (TEFAS / BES / MKK / BIST / Türk altın türleri yok).
- **Türk muadiller** (Finvestor, Midas, ForInvest) TEFAS + BIST + kripto fiyat takibi
  yapar ama **çok zincirli cüzdan tarama + borsa API sync + BES + MKK import + bütçe**
  birleşimini sunmaz; çoğu manuel/fiyat-izleme ağırlıklı.
- **KFinans'ın yapısal moat'ı:** (a) Türkiye'ye tam yerellik, (b) self-hosted / veri
  sahipliği (Mint kapanışının gösterdiği riski ortadan kaldırır), (c) kripto-native
  10 zincir cüzdan + borsa otomasyonu.

**Stratejik tez:** KFinans, *"Türkiye'ye uyarlanmış, self-hosted Kubera + Monarch"*
konumundadır. Yol haritasının üç önceliği:

1. **Para birimi + reel getiri** (rekabet paritesi + en güçlü yerel farklılaştırıcı).
2. **AI danışman aktivasyonu** (altyapı hazır, çok düşük marjinal efor, yüksek algı).
3. **Mobil + MCP** (platform genişleme; pazarda kimsede olmayan MCP açılımı).

---

## 2. Pazar Konumu (önceki rekabet analizinin sentezi)

### 2.1 Özellik karşılaştırma matrisi

> **Kategori notu:** Kubera/Finary/Empower/Monarch = net worth/portföy agregatörü;
> Finvestor/Midas = Türk yatırım/fiyat takibi; **Clint = AI gider + abonelik yöneticisi**
> (portföy/varlık takibi yapmaz — farklı kategori ama KFinans'ın *harcama/bütçe*
> modülüyle örtüşür ve oradan öğrenilecek güçlü fikirleri var, bkz. §2.3).

| Özellik                                   | **KFinans** | Kubera | Finary | Empower | Monarch  | Finvestor | Midas |      Clint      |
| ----------------------------------------- | :---------: | :----: | :----: | :-----: | :------: | :-------: | :---: | :-------------: |
| TEFAS fonları                             |      ✅      |   ❌    |   ❌    |    ❌    |    ❌     |     ✅     |   ✅   |        ❌        |
| BES emeklilik                             |      ✅      |   ❌    |   ❌    |  kısmi  |    ❌     |     ❓     |   ❌   |        ❌        |
| MKK e-Yatırımcı import                    |      ✅      |   ❌    |   ❌    |    ❌    |    ❌     |     ❌     |   ❌   |        ❌        |
| BIST hisse                                |      ✅      |   ✅    |   ❌    |    ❌    |    ❌     |     ✅     |   ✅   |        ❌        |
| Global hisse                              |      ✅      |   ✅    |   ✅    |    ✅    |    ✅     |     ✅     |   ✅   |        ❌        |
| Kripto borsa API sync                     |      ✅      |   ✅    |   ✅    |  zayıf  | sınırlı  |   yarı    |   ❌   |        ❌        |
| 10 zincir cüzdan tarama                   |      ✅      |   ✅    | kısmi  |    ❌    |    ❌     |     ❌     |   ❌   |        ❌        |
| Türk altın türleri (çeyrek/cumhuriyet)    |      ✅      | metal  | metal  |    ❌    |    ❌     |   altın   |   ❌   |        ❌        |
| Bütçe/harcama/gelir                       |      ✅      |   ❌    | kısmi  |  kısmi  |    ✅     |     ❌     |   ❌   |        ✅        |
| **Makbuz/e-posta tarama (AI OCR)**        |      ❌      |   ❌    |   ❌    |    ❌    |  kısmi   |     ❌     |   ❌   |        ✅        |
| **Abonelik takibi + yenileme uyarısı**    |  ⏳ manuel   |   ❌    |   ❌    |    ❌    |  kısmi   |     ❌     |   ❌   |        ✅        |
| **Banka otomatik bağlama (open banking)** |      ❌      |   ✅    |   ✅    |    ✅    |    ✅     |     ❌     |   —   |   bilinçli ❌    |
| **Çoklu para birimi**                     |      ❌      |   ✅    |   ✅    |    ✅    |    ✅     |   kısmi   |   ❌   |        ✅        |
| **Mobil uygulama**                        |      ❌      |   ✅    |   ✅    |    ✅    |    ✅     |     ✅     |   ✅   |        ✅        |
| **Getiri analitiği (TWR/XIRR)**           |      ❌      |   ✅    |   ✅    |    ✅    |  kısmi   |     ❌     | kısmi |        ❌        |
| **AI özellikleri**                        |  ⏳ altyapı  |   ❌    | kısmi  |  kısmi  | ✅ (2026) |     ❌     |   ❌   |    ✅ (gider)    |
| Self-hosted / veri sahipliği              |      ✅      |   ❌    |   ❌    |    ❌    |    ❌     |     ❌     |   ❌   |        ❌        |
| TL-bazlı + yerel                          |      ✅      |   ❌    |   ❌    |    ❌    |    ❌     |     ✅     |   ✅   | kısmi (TRY var) |

✅ var · ❌ yok · ⏳ kısmi/altyapı hazır · ❓ belirsiz · "bilinçli ❌" = ürün tercihi olarak yok

### 2.2 Boşluk analizi (nereye oynayacağız)

- **Kapatılacak paritesizlikler:** çoklu para birimi, getiri analitiği, mobil, AI aktivasyonu, bildirim.
- **Regülasyona bağlı uzun vade:** open banking (BDDK Açık Bankacılık Servisleri).
- **Kimsede olmayan yerel farklılaştırıcı:** **enflasyon-düzeltilmiş reel getiri**, Türkiye vergi-bilinçli raporlama, **MCP Server**.

### 2.3 Clint incelemesi (kategori-komşusu — gider/abonelik yöneticisi)

[Clint](https://www.clint.website/) bir net worth agregatörü **değil**; "Track every expense,
your way" diyen **AI destekli gider + abonelik yöneticisi** (iOS/Android/Web). KFinans'ın
harcama/bütçe/planlı-ödeme modülüyle doğrudan örtüşür. Özellikleri:

- **Banka bağlantısı GEREKTİRMEDEN** gider yakalama: **Gmail senkronizasyonu** (sadece
  finansal e-postaları okur), Google Drive, **PDF yükleme**, **fotoğraf/makbuz tarama**
  (AI ile vendor + tutar + tarih çıkarımı), manuel giriş.
- **Abonelik algılama + yenileme/fiyat-değişim uyarıları** (tekrar eden ödeme tespiti).
- **Harita görünümü** (konum-bazlı harcama ısı haritası), dönem karşılaştırmalı analitik,
  Excel export, "AI savings insights" (yakında).
- **Kredi-tabanlı AI fiyatlandırma:** Free 40 kredi/ay → Flow $5 (150) → Pro $12 (600)
  → Maximus $24 (1.000). Plaid bağımlılığı yok → ülke kısıtsız, **TRY dahil çoklu para birimi**.
- Bağımsız güvenlik denetimi (Tac Security) ile gizlilik vurgusu.

**KFinans için çıkarımlar:**

1. **Doğrudan ödünç alınacak fikirler** (KFinans gider modülünü Clint seviyesine taşır):
   makbuz/e-posta AI tarama, **abonelik oto-tespiti + yenileme uyarısı**, harcama ısı haritası.
   → Yeni özellik **C6** + mevcut **C3** zenginleştirildi (aşağıda).
2. **Stratejik doğrulama:** Clint'in **kredi-tabanlı AI fiyatlandırması**, KFinans'ın
   mevcut kredi sistemiyle (`docs/06-kredi-sistemi.md`) **birebir aynı modeli** — AI
   maliyetini krediyle yansıtma yaklaşımımızın pazar tarafından doğrulandığını gösterir.
3. **"Banka bağlantısız" gizlilik açısı:** Clint Plaid kullanmadan (Gmail/PDF/foto) gider
   yakalıyor. Bu, KFinans'ın self-hosted/veri-sahipliği konumuyla **aynı felsefede** —
   open banking (A6) regülasyonu beklemeden gider otomasyonu sağlanabilir (C3).
4. **Konum farkı:** Clint salt gider; KFinans gideri **bütünsel net worth** içine koyar.
   KFinans bu fikirleri eklerse, Clint'in yapamadığı "gider + portföy + reel getiri tek
   ekranda" konumuna ulaşır — Clint'in üstüne çıkar, altına değil.

---

## 3. Stratejik Temalar

Yol haritası üç "kova"ya ayrılır. Her özellik: **Problem → Çözüm → Teknik detay →
Efor → Bağımlılık → Öncelik** formatında.

Efor skalası: **XS** (<1 gün) · **S** (1-3 gün) · **M** (4-8 gün) · **L** (2-4 hafta) · **XL** (>1 ay).
Öncelik: **P0** (v1.0 öncesi) · **P1** (v1.x) · **P2** (gelecek).

---

## KOVA A — Rekabet Paritesi (rakiplerde var, bizde eksik/zayıf)

### A1. Çoklu Para Birimi (onboarding'de seçilen base + opsiyonel display)
- **Problem:** Kubera/Finary/Empower/Monarch hepsinde var; yurtdışı kullanıcı veya
  döviz bazlı düşünen kullanıcı için temel beklenti. KFinans TL-only.
- **Çözüm:** Kayıt sırasında **değiştirilemez base currency** seçimi (TRY/USD/EUR/GBP).
  Tüm snapshot + finans kayıtları bu birimde saklanır. "Değiştirilemez" kısıtı,
  tarihsel yeniden-çevrim ve migration problemlerini ortadan kaldırır.
- **Teknik detay:**
  - **DB:** `users.base_currency VARCHAR(3) NOT NULL DEFAULT 'TRY'` (1 Alembic migration).
    Mevcut kullanıcılar `TRY` alır → migration riski yok.
  - **Normalizasyon chokepoint:** [aggregator.py](../backend/app/services/aggregator.py)
    `to_asset_position` + [snapshot.py](../backend/app/services/snapshot.py) `_gather_*`
    "→ TL" yerine "→ base currency". Çapraz kur `fetch_tcmb_rates()` dict'inden türetilir
    (USD→EUR = (USD/TRY)÷(EUR/TRY)) — **yeni veri kaynağı gerekmez**.
  - **Cash modülü:** zaten multi-currency → TL çeviriyor; hedef base currency yapılır.
  - **Manuel finans (expense/income/budget/credit card):** kullanıcı zaten kendi
    biriminde girer → **çevrim yok**.
  - **Frontend:** `fmtTL` → `fmtMoney(value, currency)` + sembol haritası; `TLValue`
    bileşeni `MoneyValue` olur. `₺` 44 dosyada dağınık ama merkezi bileşen + helper
    üzerinden temizlenir (uzun kuyruk ama mekanik).
  - **Immutability guard:** `PATCH /user/me` base_currency değişimini 409 ile reddeder.
  - **`_tl` kolon isimleri:** non-TL tutacak (isim borcu) — **rename etme**, yorumla
    dokümante et; rename ayrı/sonraki iş.
  - **Snapshot:** `usd_try_rate` → `base_to_usd_rate` semantiği; geçmiş USD eğimi korunur.
- **Efor:** **M** (~4-6 gün; frontend format temizliği en uzun kuyruk).
- **Bağımlılık:** Yok. İlk yapılabilir.
- **Öncelik:** **P1** (onboarding akışıyla birlikte).
- **Not:** Detaylı tartışma bu oturumda yapıldı; "değiştirilemez + kayıtta seçim"
  yaklaşımı tam rewrite'tan kaçınmanın anahtarı.

### A2. Getiri / Performans Analitiği (TWR, XIRR, benchmark)
- **Problem:** Kubera/Finary/Empower'da var; "ne kadar kazandım?" en temel yatırımcı
  sorusu. KFinans snapshot + `avg_cost_tl` tutuyor ama **zaman-ağırlıklı getiri (TWR)**
  veya **iç verim oranı (XIRR)** hesaplamıyor.
- **Çözüm:** Snapshot zaman serisi + nakit akışları (alım/satım/yatırma) üzerinden
  TWR + XIRR + benchmark (BIST100, S&P500, altın, USD/TRY) karşılaştırma.
- **Teknik detay:**
  - Cash flow event tablosu gerekli: alım/satım/depozito hareketleri (şu an snapshot
    sadece anlık değer tutuyor, akış yok). `portfolio_cashflows` (date, amount, type).
  - XIRR: Newton-Raphson ile `scipy` olmadan saf-Python implementasyon (bağımlılık eklemeden).
  - Benchmark serileri: Yahoo Finance (S&P500 `^GSPC`, BIST `XU100.IS`) + mevcut altın/USD.
  - Yeni servis `services/performance.py` + `GET /portfolio/performance?period=&benchmark=`.
  - Frontend: getiri grafiği + benchmark overlay (mevcut Recharts ComposedChart deseni).
- **Efor:** **L** (cash flow event modeli + hesaplama + UI).
- **Bağımlılık:** Snapshot geçmişi (var); cash flow event kaydı (yeni).
- **Öncelik:** **P1**.

### A3. AI Danışman Aktivasyonu + Zenginleştirme
- **Problem:** [advisor.py](../backend/app/services/advisor.py) altyapısı + kredi sistemi
  + KVKK consent + prompt caching **zaten var** (docs/05, docs/06) ama "Faz 3" etiketli.
  Monarch 2026'da AI asistan ekledi; algı/pazarlama değeri yüksek.
- **Çözüm:** Mevcut altyapıyı tam aktive et + use-case'leri genişlet:
  - Portföy sağlık raporu (PDF/Excel — `feedback_report_formats` kuralına uygun çift format).
  - Rebalancing önerisi (hedef ağırlık vs gerçek sapma).
  - Anomali tespiti (ani değer düşüşü, beklenmedik gider).
  - Risk profili + çeşitlendirme skoru.
- **Teknik detay:**
  - `advisor.py` system prompt zaten 1500-2000 token + prompt cache aktif.
  - Yeni prompt şablonları (rapor üretimi, rebalancing) — `ai-expert` ajanı görevi.
  - `/advice/generate` çağrı sırası (consent → kredi → rate limit → çağrı → düşüm) korunur.
  - Çıktı SPK disclaimer post-processing (`_ensure_disclaimer`) zaten mevcut.
- **Efor:** **S-M** (altyapı hazır, esas iş prompt engineering + rapor şablonu).
- **Bağımlılık:** Yok. Hızlı kazanım.
- **Öncelik:** **P1** (yüksek algı/efor oranı).

### A4. Bildirim / Alarm Sistemi
- **Problem:** Hiçbir proaktif uyarı yok. Rakiplerde fiyat alarmı, bütçe aşımı,
  hesap özeti standart.
- **Çözüm:** Olay-tabanlı bildirim: bütçe aşımı, kredi kartı son ödeme tarihi yaklaştı,
  fiyat alarmı, snapshot hazır, periyodik gelir realize zamanı.
- **Teknik detay:**
  - `notification_rules` + `notifications` tabloları.
  - Kanal: e-posta (Resend SDK zaten var) + frontend in-app + ileride mobil push.
  - APScheduler'a değerlendirme job'u (mevcut scheduler altyapısı + leader election).
  - `GET/POST /notifications` + `/notification-rules` CRUD.
- **Efor:** **M**.
- **Bağımlılık:** Mobil push için A → mobil (D3).
- **Öncelik:** **P1**.

### A5. Mobil Uygulama (Flutter)
- **Problem:** Tüm rakipler mobil-first; KFinans web-only. (Roadmap memory:
  `project_roadmap_post_web` — sıra: web → Flutter → MCP.)
- **Çözüm:** Mevcut FastAPI'yi tüketen Flutter app (iOS + Android). Backend
  değişmez; yalnız bazı endpoint'ler mobil-dostu hale getirilir (pagination, ince payload).
- **Teknik detay:**
  - JWT + refresh rotation zaten mobil uyumlu; secure storage (Keychain/Keystore).
  - Pagination (PERF-001) mobil için kritik → B3 ile birlikte.
  - Biyometrik kilit + MFA (TOTP zaten var).
  - Push: FCM/APNs → A4 bildirim sistemiyle entegre.
- **Efor:** **XL**.
- **Bağımlılık:** B3 (pagination), A4 (bildirim).
- **Öncelik:** **P2**.

### A6. Açık Bankacılık (Banka Hesabı Otomatik Bağlama)
- **Problem:** Empower/Monarch/Finary'nin en güçlü yanı; KFinans'ta banka bakiyesi/işlem
  manuel. Türkiye'de **BDDK Açık Bankacılık Servisleri** (BKM üzerinden) regüle.
- **Çözüm:** BKM/BDDK açık bankacılık API'leri ile hesap + işlem çekme (hesap bilgisi servisi).
- **Teknik detay:**
  - Lisans/regülasyon önkoşulu (yetkili kuruluş ya da aracı entegrasyon). **Hukuki ağırlık yüksek.**
  - Teknik: OAuth2 + mTLS, BKM API entegrasyonu, işlem normalizasyonu → otomatik kategorize (C3 ile).
  - KVKK + finansal veri saklama yükümlülükleri.
- **Efor:** **XL** (+ regülasyon).
- **Bağımlılık:** Regülasyon/lisans; C3 (oto-kategorize).
- **Öncelik:** **P2** (uzun vade, regülasyon-bağımlı).

---

## KOVA B — Mevcut Özellik İyileştirmeleri

### B1. Enflasyon-Düzeltilmiş Reel Getiri *(aynı zamanda farklılaştırıcı — bkz. C1)*
- Detay C1'de. Mevcut snapshot/getiri ekranlarına **reel (TÜFE-arındırılmış)** katman
  eklemek hem iyileştirme hem farklılaştırıcı.

### B2. Snapshot Sıklığı + Tazeleme
- **Problem:** Snapshot haftalık (Pazar 23:00). Kullanıcı gün içi değişimi göremiyor;
  ad-hoc snapshot manuel.
- **Çözüm:** Opsiyonel **günlük snapshot** + dashboard'da "anlık değer" (snapshot'tan
  bağımsız canlı toplama, mevcut `GET /portfolio/wallets` cache deseniyle).
- **Teknik detay:** Scheduler'a günlük job (kullanıcı tercihi `users.snapshot_frequency`);
  blockchain/borsa cache TTL'leri (10 dk) zaten gün içi tazelemeyi destekliyor.
  Storage maliyeti: günlük snapshot → yıllık ~365 satır/kullanıcı, ihmal edilebilir.
- **Efor:** **S**.
- **Öncelik:** **P1**.

### B3. Pagination Tamamlama (PERF-001 borcu)
- **Problem:** `PaginatedResponse[T]` altyapısı var ama yalnız `/audit-logs` kullanıyor.
  `/expenses /incomes /wallets /planned-expenses` paginate değil → büyük veri + mobilde sorun.
- **Çözüm:** Mevcut `schemas/pagination.py` deseniyle 4 endpoint'i paginate et.
- **Efor:** **S**.
- **Bağımlılık:** Mobil (A5) önkoşulu.
- **Öncelik:** **P1**.

### B4. i18n Tam EN Çevirisi — ✅ TAMAMLANDI (i18n-002)
- **Durum:** **Tamamlandı.** `tr.json`/`en.json` ikisi de 953 satır (EN, TR'yi tam yansıtır),
  53 bileşen `useTranslation` kullanıyor — 20 dashboard sayfası + login + register dahil.
  Cookie tabanlı (`kfinans-locale`), `LanguageSwitcher` toggle, eksik anahtar key'i geri döner.
- **Kalan (küçük backlog):** `DASHBOARD_CARDS.label` hâlâ TR hard-coded (`labelKey`'e taşınmalı);
  bare-string yakalayan ESLint custom rule; yeni eklenen sayfalarda anahtar disiplinini koru.
- **Öncelik:** kapandı (yalnız bakım/lint iyileştirmesi P2).

### B5. Performans: Blockchain Tarama + Cache
- **Problem:** 10 zincir paralel tarama snapshot'ı yavaşlatabiliyor; OOM dersi (rc13)
  bellek baskısını gösterdi.
- **Çözüm:** Cache TTL ayarı (zincir başına), batch RPC, gereksiz token discovery'yi
  azaltma; `Semaphore` paralelizm ayarı (ARC-003).
- **Teknik detay:** Redis cache (mevcut `settings.redis_url` opsiyonel) ile in-memory
  cache'i kalıcılaştır → multi-replica + restart sonrası sıcak cache.
- **Efor:** **M**.
- **Öncelik:** **P2**.

### B6. Maliyet Bazı + Realize/Unrealize Ayrımı
- **Problem:** `avg_cost_tl` var (TEFAS/hisse) ama kripto/cüzdan/manuel kriptoda maliyet
  bazı yok; gerçekleşmiş/gerçekleşmemiş kâr ayrımı yok.
- **Çözüm:** Tüm varlık tiplerine opsiyonel maliyet bazı + FIFO/ortalama lot takibi.
- **Teknik detay:** A2 (cash flow event) ile birleşir; lot tablosu → vergi raporu (C2) besler.
- **Efor:** **L**.
- **Bağımlılık:** A2.
- **Öncelik:** **P2**.

---

## KOVA C — Farklılaştırıcı (kimsede yok, yerel ihtiyaç)

### C1. Enflasyon-Düzeltilmiş (Reel) Portföy Değeri ve Getiri ⭐
- **Problem:** Türkiye'nin yüksek enflasyon ortamında **nominal TL getirisi yanıltıcı**.
  "Portföyüm %40 arttı" ama enflasyon %50 ise reel olarak kaybettin. **Hiçbir global
  veya yerel uygulama bunu yapmıyor** — Türk kullanıcı için kritik ve eşsiz.
- **Çözüm:** TÜİK TÜFE serisi ile snapshot zaman serisini **reel TL**'ye indirgeyen
  katman: "nominal vs reel getiri" toggle, satın alma gücü cinsinden portföy.
- **Teknik detay:**
  - **Veri kaynağı:** TÜİK TÜFE aylık endeks (EVDS — TCMB Elektronik Veri Dağıtım Sistemi
    API'si; aylık seri, API key ücretsiz). `services/inflation.py` + aylık cache.
  - `tcmb_evds` veya TÜİK açık veri → endeks tablosu `cpi_index` (year, month, index).
  - Reel değer = nominal × (baz_endeks ÷ dönem_endeksi).
  - `GET /portfolio/performance?real=true` → reel getiri serisi.
  - Frontend: history + performans grafiklerinde "Reel (enflasyondan arındırılmış)" toggle.
  - AI danışman (A3) reel getiriyi yorumlamada kullanır — güçlü sinerji.
- **Efor:** **M**.
- **Bağımlılık:** A2 (performans serisi) ile birleşince en güçlü.
- **Öncelik:** **P1** ⭐ — **en yüksek farklılaştırma/efor oranı.**

### C2. Türkiye Vergi-Bilinçli Raporlama
- **Problem:** Türkiye'de kripto vergilendirmesi gündemde; TEFAS stopajı, hisse stopajı,
  temettü vergisi karmaşık. CoinTracker/Koinly global ama Türk mevzuatına kör.
- **Çözüm:** Yıllık vergi özeti: TEFAS stopaj, hisse alım-satım kazancı, kripto kazanç
  (mevzuat netleştikçe), temettü → PDF/Excel rapor (çift format kuralı).
- **Teknik detay:**
  - B6 (lot/maliyet bazı) + A2 (cash flow event) önkoşul.
  - `services/tax_report.py`; mevzuat parametreleri config'te (stopaj oranları değişebilir).
  - **Uyarı:** "vergi danışmanlığı değildir" disclaimer (SPK/mali müşavir sınırı).
- **Efor:** **L** (+ mevzuat takibi).
- **Bağımlılık:** A2, B6.
- **Öncelik:** **P2** (mevzuat olgunlaşınca).

### C3. Akıllı İşlem Kategorize (AI) + Otomatik Import — *(Clint paritesi)*
- **Problem:** Harcama/gelir manuel girişli. Monarch/Mint otomatik kategorize, **Clint
  ise banka bağlantısı olmadan Gmail/PDF/foto tarama** ile öne çıktı. KFinans en geride.
- **Çözüm:** Çok kanallı gider yakalama: (1) banka/kart ekstresi (CSV/Excel/PDF) yükle,
  (2) **makbuz fotoğrafı/PDF → AI OCR** ile vendor+tutar+tarih çıkarımı, (3) **Gmail
  senkronizasyonu** (sadece finansal e-posta) → AI ile otomatik kategorize + tekrar eden
  işlem tespiti. Hepsi **banka bağlantısı gerektirmeden** (Clint felsefesi = self-hosted
  gizlilik konumuyla uyumlu).
- **Teknik detay:**
  - Mevcut `upload_validation` + Excel parse altyapısı temel.
  - **AI çıkarım:** Claude API (advisor altyapısı + kredi sistemi) ile makbuz/e-posta →
    yapılandırılmış expense; kredi düşümü Clint'in kredi modeliyle aynı (doğrulanmış).
  - Kategorize: kural-tabanlı (merchant pattern) + Claude fallback.
  - **Gmail:** OAuth2 read-only scope (`gmail.readonly`) + sadece finansal gönderen
    filtresi; **KVKK aydınlatma + açık rıza** şart (e-posta içeriği hassas).
  - Açık bankacılık (A6) geldiğinde otomatik akışı besler.
- **Efor:** **M** (PDF/foto OCR) → **L** (Gmail entegrasyonu + KVKK akışı dahil).
- **Bağımlılık:** A3 (AI) önerilir; A6 ile sinerji.
- **Öncelik:** **P2** (PDF/foto tarama P1'e çekilebilir — düşük regülasyon yükü).

### C6. Abonelik Takibi + Yenileme/Fiyat Uyarısı — *(Clint'ten ilham)*
- **Problem:** KFinans `planned_expenses` + `recurring_incomes` ile **manuel** periyodik
  kayıt tutuyor ama **otomatik abonelik tespiti yok**. Clint'in çekirdek değer önerisi
  tam burada: "çok aboneliği olanlar için gizli hazine".
- **Çözüm:** Tekrar eden ödemeleri otomatik tespit et (Netflix, Spotify, hosting, vb.),
  abonelik panosu + yenileme tarihi yaklaştı / fiyat arttı uyarısı; "kullanmadığın
  abonelikleri iptal et" AI önerisi.
- **Teknik detay:**
  - C3 (oto-import) verisinden tekrar eden merchant + tutar + periyot tespiti
    (aynı vendor, ~aynı tutar, ~30/90/365 gün aralık).
  - `subscriptions` tablosu (vendor, amount, currency, cycle, next_renewal, status,
    detected_from) — mevcut `planned_expenses` ile ilişkilendirilir veya ona genişletilir.
  - Uyarılar **A4 bildirim sistemi** üzerinden (yenileme T-3 gün, fiyat değişimi).
  - Frontend: yeni "Abonelikler" kartı (Finans grubu) + aylık/yıllık abonelik yükü özeti.
  - AI (A3): "yıllık ₺X abonelik harcaman var, şu 2'si 3 aydır kullanılmıyor olabilir".
- **Efor:** **M**.
- **Bağımlılık:** C3 (oto-tespit için veri), A4 (uyarı), A3 (öneri — opsiyonel).
- **Öncelik:** **P1** (yüksek kullanıcı değeri, mevcut planned_expenses üstüne kurulur).

### C4. KFinans MCP Server ⭐
- **Problem:** Kimsede yok. Kullanıcı kendi portföy verisini **kendi AI asistanıyla**
  (Claude Desktop, ChatGPT, vb.) doğal dille sorgulayamıyor.
- **Çözüm:** KFinans verisini **Model Context Protocol** ile dışa açan MCP server.
  Kullanıcı: *"Bu ay en çok hangi kategoride harcadım, geçen aya göre reel olarak ne değişti?"*
  diye kendi LLM'ine sorar. (Roadmap memory: web → Flutter → MCP.)
- **Teknik detay:**
  - MCP server (Python SDK) → KFinans API'yi tüketir; OAuth/PAT ile kullanıcı yetkisi.
  - Tool'lar: `get_portfolio`, `get_snapshot_history`, `get_expenses`, `get_performance`,
    `get_real_return` (read-only — güvenlik için yazma yok ilk sürümde).
  - Read-only + kullanıcı-scoped token; KVKK: veri kullanıcının kendi LLM'ine gider.
  - Dağıtım: ayrı container; mevcut K3s + ingress.
- **Efor:** **L**.
- **Bağımlılık:** A1, A2, C1 (zengin veri olunca anlamlı).
- **Öncelik:** **P2** ⭐ — düşük rekabet, yüksek "wow", teknik olarak fizibıl.

### C5. Hedef/Senaryo Simülasyonu (What-if + Monte Carlo)
- **Problem:** Mevcut "Finansal Hedef" statik. Empower retirement planner var ama
  Türkiye enflasyon/kur dinamiğine kör.
- **Çözüm:** "X yıl sonra Y TL hedefe ulaşır mıyım?" — enflasyon + kur + tahmini getiri
  ile Monte Carlo senaryo bandı (kötümser/baz/iyimser).
- **Teknik detay:**
  - Saf-Python simülasyon (numpy opsiyonel); C1 (reel) + A2 (geçmiş getiri varyansı) girdi.
  - `POST /goal/simulate` → senaryo dağılımı; frontend fan chart.
- **Efor:** **L**.
- **Bağımlılık:** A2, C1.
- **Öncelik:** **P2**.

---

## 4. Fazlama ve Zaman Çizelgesi (öneri)

> Tek geliştirici + uzman ajan desteği varsayımı. Süreler kaba; bağımlılık sıralaması bağlayıcı.

### Faz D1 — "Yerel Üstünlük" (v1.0 → v1.1, ~6-8 hafta)
Hedef: rakiplere parite + en güçlü yerel farklılaştırıcıyı hızla sahaya sür.
1. **A1** Çoklu para birimi + onboarding (M)
2. **C1** Enflasyon-düzeltilmiş reel getiri ⭐ (M)
3. **A3** AI danışman aktivasyonu (S-M)
4. **B3** Pagination tamamlama (S)
5. **B2** Günlük snapshot opsiyonu (S)

### Faz D2 — "Yatırımcı Derinliği + Gider Otomasyonu" (v1.2, ~8-10 hafta)
Hedef: ciddi yatırımcıyı tutacak analitik + Clint paritesi gider deneyimi.
1. **A2** Getiri analitiği TWR/XIRR + benchmark (L) — cash flow event modeli burada doğar
2. **A4** Bildirim/alarm sistemi (M)
3. **C6** Abonelik takibi + yenileme/fiyat uyarısı (M) — A4 üstüne, Clint paritesi
4. **C3 (kısmi)** Makbuz/PDF/foto AI tarama (M) — Gmail kısmı D4'te kalır (KVKK yükü)
5. **B6** Maliyet bazı + realize/unrealize (L)

> Not: **B4 (i18n tam EN) ✅ tamamlandı** (i18n-002) — fazlamadan çıkarıldı.

### Faz D3 — "Platform Genişleme" (v2.0, ~3-4 ay)
1. **A5** Flutter mobil (XL)
2. **C4** MCP Server ⭐ (L)
3. **C5** Hedef/senaryo simülasyonu (L)
4. **B5** Redis cache + performans (M)

### Faz D4 — "Regülasyon Bağımlı" (uzun vade)
1. **C2** Vergi raporlama (L, mevzuat takibi)
2. **A6** Açık bankacılık (XL + lisans)
3. **C3 (Gmail)** E-posta senkronizasyonlu oto-kategorize (L, KVKK açık rıza + A6 sinerji)

---

## 5. Öncelik Matrisi (Etki × Efor)

| | Düşük Efor | Yüksek Efor |
|---|---|---|
| **Yüksek Etki** | A3 (AI aktivasyon), B2 (günlük snapshot), B3 (pagination) | **A1 (para birimi), C1 (reel getiri)⭐**, A2 (analitik), C6 (abonelik), C3 (makbuz tarama), A5 (mobil), C4 (MCP)⭐ |
| **Düşük/Orta Etki** | — | B5 (cache), C5 (senaryo) · (B4 i18n ✅ tamam) |
| **Regülasyon Kapısı** | — | A6 (open banking), C2 (vergi), C3-Gmail |

**Hızlı kazanımlar (hemen yap):** A3, B2, B3.
**Stratejik yatırımlar (planla):** A1 + C1 (birlikte), A2, C6 + C3 (Clint paritesi), C4.

---

## 6. Teknik Borç ve Altyapı Önkoşulları

Yeni özellikler öncesi temizlenmesi/kurulması gerekenler:

1. **Cash flow event modeli** (A2 önkoşulu) — şu an snapshot sadece anlık değer; akış yok.
   Bu model A2 + B6 + C2 + C5'in ortak temeli. **İlk inşa edilecek altyapı.**
2. **Pagination (B3)** — mobil ve büyük veri için zorunlu.
3. **Redis cache (B5)** — multi-replica + sıcak cache; `settings.redis_url` zaten opsiyonel.
4. **`_tl` kolon isim borcu** — para birimi sonrası semantik yorum; rename gelecekte.
5. **Mevcut borçlar** (memory): COMP off-site backup (rclone), KVKK placeholder'lar
   (`project_kvkk_placeholders`), cost-basis test güncellemesi. (i18n tam EN ✅ kapandı.)

---

## 7. Riskler ve Regülasyon

- **Açık bankacılık (A6):** BDDK lisans/yetki ağır; aracı entegratörle gidilebilir. v1.0 blocker değil.
- **Vergi raporu (C2):** "vergi danışmanlığı değildir" disclaimer şart; mevzuat değişken (config'te tut).
- **AI danışman (A3):** SPK uyumlu disclaimer zaten `_ensure_disclaimer` ile var; KVKK m.9 consent korunur.
- **MCP (C4):** read-only + kullanıcı-scoped token; veri kullanıcının kendi LLM'ine gider (KVKK m.9 aydınlatma).
- **Çoklu para birimi (A1):** TCMB'nin fiyatlamadığı para birimi seçtirilmemeli (TRY/USD/EUR/GBP ile sınırla).

---

## 8. Sonraki Adım

Bu rapor onaylanırsa, **Faz D1'in ilk iki maddesi (A1 + C1)** için detaylı uygulama
planı çıkarılabilir (DB migration + servis değişiklikleri + endpoint + frontend + test
stratejisi, dosya-bazlı). A1'in teknik tartışması bu oturumda yapıldı; C1 için EVDS/TÜİK
TÜFE veri kaynağının doğrulanması ilk teknik görev olur.

> İlgili belgeler: [02-mimari.md](02-mimari.md) · [05-ai-ve-finans.md](05-ai-ve-finans.md)
> · [06-kredi-sistemi.md](06-kredi-sistemi.md) · [audits/2026-05-22-master-audit.md](audits/2026-05-22-master-audit.md)
