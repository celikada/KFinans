# Frontend Mimarisi

**Sahip ajan:** `frontend-expert`
**Stack:** Next.js 16.2.4 (App Router, Turbopack) + React 19 + TypeScript (strict) + Tailwind CSS v4

---

## 1. Mevcut Fonksiyonel Gereksinimler (Çalışan)

Aşağıdaki ekranlar **fonksiyonel gereksinim** olarak kabul edilir — production'a kadar regresyon kabul edilmez:

| Ekran | URL | Durum |
|-------|-----|-------|
| Giriş (üzerinde "Kayıt ol" linki) | `/login` | ✅ Aktif |
| Kayıt (form + risk profili dropdown) | `/register` | ✅ Aktif |
| E-posta doğrulama (token okuma) | `/verify-email` | ✅ Aktif |
| Ana Dashboard (15 kart, kullanıcı tarafından gizlenebilir; Finans/Portföy iki grup + üstte Toplam Portföy ve Finans Net Bakiye özet kartları) | `/dashboard` | ✅ Aktif |
| Snapshot geçmişi (recharts line chart x2) | `/dashboard/history` | ✅ Aktif |
| Kripto pozisyonları (borsa filtresi + sıralama) | `/dashboard/crypto` | ✅ Aktif |
| Manuel kripto (API'siz borsalar — BinanceTR/iCrypex/BTCTurk/Paribu vs. + asset catalog autocomplete + 3 fiyat modu: auto/manual/linked) | `/dashboard/manual-crypto` | ✅ Aktif (Faz 3) |
| Hisse senedi portföyü (Yahoo + Excel + MKK + maliyet/kâr-zarar + kurum) | `/dashboard/stocks` | ✅ Aktif |
| Blockchain cüzdanları (10 zincir: BTC, ETH, Sonic, AVAX C/P, SOL, ADA, ALGO, DOT, LTC) | `/dashboard/wallets` | ✅ Aktif |
| TEFAS holdings (preview + Excel + MKK + maliyet/kâr-zarar + kurum) | `/dashboard/tefas` | ✅ Aktif |
| BES manuel giriş (plan adı + ₺ + Excel) | `/dashboard/bes` | ✅ Aktif |
| Harcama takibi (form + tablo + pasta grafik + ay seçici + Excel) | `/dashboard/expenses` | ✅ Aktif (Faz 3 MVP) |
| Planlı ödemeler & yıllık nakit akışı tahmini | `/dashboard/planned` | ✅ Aktif (Faz 3) |
| Gelir takibi (form + tablo + pasta grafik + Excel + recurring + realize) | `/dashboard/income` | ✅ Aktif (Faz 3) |
| Bütçe takibi (kategori bazlı bütçe + comparison) | `/dashboard/budget` | ✅ Aktif (Faz 3) |
| Kıymetli madenler (altın/gümüş — gram/BiGA/sikke + Excel) | `/dashboard/commodities` | ✅ Aktif (Faz 3) |
| Nakit / Banka hesabı (manuel; TRY/USD/EUR/GBP — TCMB ile TL'ye normalize) | `/dashboard/cash` | ✅ Aktif (Faz 3) |
| Yıllık nakit akış projeksiyonu (geçmiş + gelecek aylar — recharts ComposedChart + xlsx/pdf rapor) | `/dashboard/cash-flow` | ✅ Aktif (Faz 3) |
| Kredi kartları (kart + ekstre + taksit nested CRUD; çift sayım kuralı) | `/dashboard/credit-cards` | ✅ Aktif (Faz 3) |
| Kredi kartı detayı (kart bazlı statement + installment yönetimi) | `/dashboard/credit-cards/[id]` | ✅ Aktif (Faz 3) |
| Finansal hedef (pasif gelir hedefi + USD/EUR/GBP/TRY) | `/dashboard/goal` | ✅ Aktif (Faz 3) |
| Ayarlar (hesap özeti + risk + şifre + kart gizleme + hesap silme) | `/dashboard/settings` | ✅ Aktif (Faz 3) |

### Auth Davranışı (Korunmalı)
- Token yoksa `/dashboard/*` → `/login`'e redirect
- Token varsa `/login` → `/dashboard`'a redirect
- 401 response → `localStorage` temizlenir, `/login`'e redirect
- Bu yönlendirme `proxy.ts` (eski adıyla `middleware.ts`) ile yapılır

### Kayıt + Doğrulama Akışı (Yeni)
- `/register`: form (email, şifre, risk profili dropdown). Submit sonrası "kayıt başarılı, e-postanı kontrol et" mesajı + "doğrulama linki tekrar gönder" butonu görünür
- `/verify-email?token=...`: Suspense boundary içinde `useSearchParams` ile token okunur, `GET /auth/verify-email` çağrılır; başarıda "doğrulandı, giriş yapabilirsiniz" mesajı + `/login` linki
- `/login`: 403 dönerse "e-posta doğrulanmadı" mesajı gösterilir + "tekrar gönder" linki
- `/login` formunun altında "Hesabın yok mu? Kayıt ol" linki

### Snapshot Tetikleme (Yeni)
- `/dashboard` üst kısmında "Snapshot al" butonu — `POST /portfolio/snapshot` çağrılır
- Loading state + başarı/hata toast'u; başarıda mevcut özet kartları yeniden çekilir

### Dashboard Yenileme (Faz 3 ile Genişletildi)
- **11 kart yapısı** (`DASHBOARD_CARDS` `lib/format.ts` üzerinden render edilir): TEFAS, Kripto, Hisse Senedi, Blockchain Cüzdanlar, BES, Harcamalar (bu ay), Planlı Ödemeler (bu yıl), Gelirler (bu ay), Finansal Hedef, Altın & Gümüş, Bütçe Takibi
- Her kartta **top 3 detay** (en yüksek 3 varlık ad + TL) ve özet sayaç (fon sayısı, plan sayısı vb.)
- Üstte **"Toplam: X ₺"** (yatırım varlık kartlarının toplamı; harcama/gelir/bütçe sayaçları dahil değil)
- Sağ üstte **"Snapshot al"** + **"Geçmiş"** + **"Ayarlar"** butonları
- **Modern UI:** emoji ikonlar inline SVG'lere çevrildi; container `max-w-5xl`; satırlar `flex-wrap` ile mobile uyumlu
- **Logo bileşenleri:** `_components/Logos.tsx` `KFinansLogo size={"sm"|"md"|"lg"|"xl"}` + `MayotekLogo` (PNG dosyaları arşivlik kaldı)
- **TL/USD bileşeni:** `_components/TLValue.tsx` — `<TLValue tl={n} />` `1.234,56 ₺` gösterir; ayar açıksa altında `≈ $369.30`. Hook `useUsdRate()` `GET /portfolio/usd-rate`'i 5 dk localStorage cache ile çeker. Toggle: Settings sayfası "Genel Tercihler > USD karşılığı göster" — `localStorage.kfinans_show_usd` boolean. Değişiklik `kfinans-show-usd-changed` custom event ile tüm bileşenlere yayılır (storage event aynı sekmede tetiklenmez)
- **Kart gizleme:** Settings sayfasında her kart için toggle; `localStorage.kfinans_hidden_cards` (JSON `DashboardCardId[]`) ile saklanır

### Snapshot History Grafiği (Yeni)
- `/dashboard/history` — `recharts ^3.8.1` ile iki line chart
  1. **Toplam Portföy Değeri** — son 12 snapshot tek mavi çizgi
  2. **Varlık Tipine Göre** — crypto / fund / stock / pension / cash 5 renkli çizgi
- Üstte "Son snapshot (tarih)" + büyük TL değer
- Boş state: "Henüz snapshot yok — 'Snapshot al' butonuna basın veya Pazar 23:00 otomatik snapshot bekleyin"
- Backend `GET /portfolio/history?limit=12` endpoint'i kullanılıyor (zaten vardı)
- `lib/api.ts` yeni metot: `getPortfolioHistory(limit=12)` + yeni interface `SnapshotHistoryDTO` (id, snapshot_date, total_value_tl, asset_positions[])

### BES Akışı (Yeni)
- `/dashboard/bes`: TEFAS sayfası pattern'inde, ama her satırda iki input (plan adı + toplam ₺)
- Butonlar: "Plan ekle", "Kaldır", "Kaydet" (`PUT /portfolio/bes/holdings` — idempotent), "Excel İndir" (`GET /portfolio/bes/export`), "Excel Yükle" (`POST /portfolio/bes/import`)
- Footer'da toplam tutar gösterimi
- Dashboard kartı: önceki "Bireysel emeklilik — yakında" pasif kartı silindi, yerine `/dashboard/bes`'e link veren aktif buton geldi; `besTotal` ve `besPlanCount` state'leri ile özet TL gösteriliyor

### Harcama Takibi Akışı (Faz 3 MVP)
- `/dashboard/expenses` (~100 satır page.tsx, sadece composition); 4 component pattern (sayfa parçalama refactor'ünün ilk tam örneği):
  - `_components/ExpenseForm.tsx` — Tutar + Kategori + Tarih + Açıklama. Submit `POST /expenses`
  - `_components/ExpenseTable.tsx` — Aylık liste, sil butonu (confirm), footer'da toplam
  - `_components/CategoryPieChart.tsx` — `recharts` PieChart, 10 kategori için sabit renk paleti
  - `_components/MonthSelector.tsx` — Ay (1-12) + Yıl dropdown
- API katmanı: `listExpenses`, `createExpense`, `updateExpense`, `deleteExpense`, `getExpenseSummary`, **`exportExpenses`**, **`importExpenses`** + DTO'lar
- Sabitler: `EXPENSE_CATEGORIES` (10) + `EXPENSE_CATEGORY_LABELS` (TR)
- Dashboard kartı: kırmızı tema (SVG ikonu), bu ayın toplamı + top 3 kategori
- **Faz 3 ekleme:** Excel İndir / Yükle butonları (Excel import Türkçe label haritası ile)

### Yeni Dashboard Sayfaları (Faz 3)

**`/dashboard/income` — Gelir Takibi**
- Expenses ile birebir paralel pattern (4 component: form + tablo + pasta grafik + ay seçici + Excel butonları)
- 7 kategori: salary, freelance, rental, dividend, bonus, sale, other (TR etiketler `INCOME_CATEGORY_LABELS`)
- Dashboard kartı: yeşil tema, bu ayın toplamı + top 3 kategori

**`/dashboard/budget` — Bütçe Takibi**
- 2 component: `BudgetForm` (kategori + tutar UPSERT — `PUT /budgets/{category}`) + `ComparisonTable` (ay seçici + bütçe vs. gerçekleşen + over_budget kırmızı renk)
- Dashboard kartı: aşılan bütçe sayısı sayacı

**`/dashboard/commodities` — Kıymetli Madenler**
- 2 component: `CommodityForm` (unit_type seçimi gram/biga/coin → conditional alanlar) + `CommodityList` (anlık fiyat + gram eşdeğeri + ₺)
- Excel İndir / Yükle butonları
- **UI fault-tolerance uyarı bandı:** `gold_price_available=false` veya `silver_price_available=false` ise sayfa üstünde info banner ("Yahoo Finance'tan altın fiyatı alınamadı, etkilenen pozisyonlar toplama dahil değil")
- Dashboard kartı: toplam ₺ + adet sayısı

**`/dashboard/goal` — Finansal Hedef**
- Hedef tutar + para birimi (USD/EUR/GBP/TRY) seçimi + ilerleme barı
- Dashboard kartı: pasif gelir yüzdesi göstergesi

**`/dashboard/planned` — Planlı Ödemeler**
- 3 component: `PlannedForm` + `PlannedList` + `YearlyForecast` (12 aylık bar chart stili nakit akışı tahmini)
- Dashboard kartı: violet tema, bu yıl toplam tutar

**`/dashboard/settings` — Ayarlar**
- 5 bölüm:
  1. **Hesap özeti:** email, oluşturma tarihi, kredi bakiyesi, doğrulama durumu (`GET /user/me`)
  2. **Risk profili:** dropdown + kaydet (`PUT /user/profile`)
  3. **Şifre değiştir:** mevcut + yeni + tekrar (`PUT /user/password`)
  4. **Dashboard kart gizleme:** 11 kart için checkbox toggle (`localStorage.kfinans_hidden_cards`)
  5. **Hesap silme:** confirm dialog + `DELETE /user/me` (soft-delete) → `clearAuth()` + `/login` yönlendirme

### Wallets Sayfası — 10 Zincir (Yeni)

`/dashboard/wallets` `WalletForm` bileşeni (`_components/WalletForm.tsx`) 10 zincirli dropdown ile cüzdan ekleme formu sunar.

- **Zincir sırası (dropdown):** Bitcoin → Ethereum → Sonic → AVAX C → AVAX P → Solana → Cardano → Algorand → Polkadot → Litecoin
- **Dinamik placeholder:** Seçilen zincire göre adres formatı (`bc1q...` / `0x...` / `P-avax1...` / Base58 / `addr1...` vb.)
- **Dinamik hint başlığı:** `CHAIN_LABELS` üzerinden seçili zincirin adı kullanılır
- **(i) Info butonu:** Tıklayınca açılır panel — chain'e özel `format` (kabul edilen adres formatları) + `howTo` (örn. Ledger Live'da nereden alınır) bilgisi

**`_components/constants.ts` (yeni/genişletilmiş):**

| Sabit | İçerik |
|-------|--------|
| `Chain` (type) | 10 zincir union: `'bitcoin' \| 'ethereum' \| 'sonic' \| 'avalanche_c' \| 'avalanche_p' \| 'solana' \| 'cardano' \| 'algorand' \| 'polkadot' \| 'litecoin'` |
| `CHAIN_LABELS` | Her zincir için Türkçe etiket (örn. "Bitcoin", "Solana", "Avalanche C-Chain") |
| `CHAIN_SYMBOLS` | Native sembol: `BTC`, `ETH`, `S`, `AVAX`, `SOL`, `ADA`, `ALGO`, `DOT`, `LTC` |
| `CHAIN_PLACEHOLDERS` | Her zincir için spesifik input placeholder |
| `CHAIN_ADDRESS_HINTS` | `{ format, howTo }` — info panelinde gösterilen format + Ledger Live yönlendirmesi |

> ERC-20 token'ları (LINK/USDT/USDC) ve curated AVAX listesi (sAVAX/USDT.e/USDC.e) wallet response'unda otomatik görünür — formdan ayrıca eklenmez.

### TEFAS + Stocks Sayfaları (Faz 3 Genişletme)
- `HoldingsForm` bileşenlerine "Ort. maliyet ₺" + "Kurum" inputları eklendi
- `StockPositionsTable` ve TEFAS tablosu: yeni kolonlar Ort. Maliyet (₺) + **Kâr/Zarar (₺ + %)** (yeşil/kırmızı renk) + **Kurum** (mavi pill badge)
- **MKK Excel Import:** paylaşılan `MkkHint` bileşeni info kart + opsiyonel `onUpload` prop ile doğrudan upload butonu (`POST /portfolio/{tefas|stocks}/import-mkk`)
- Container `max-w-5xl`, form satırları `flex-wrap`

### Paylaşılan Bileşenler (`app/_components/`)
- `Logos.tsx` — `KFinansLogo size={"sm"|"md"|"lg"|"xl"}` + `MayotekLogo` (inline SVG)
- `MkkHint.tsx` — MKK e-Yatırımcı bilgi kartı + opsiyonel `onUpload?: (file: File) => Promise<void>` prop ile MKK xls upload butonu
- `PageHeader.tsx` — sayfa başlığı + opsiyonel açıklama

### `lib/format.ts` (Genişletildi)
- `fmtTL`, `fmtNum`, `fmtDate`, `shortAddr` formatlama yardımcıları
- `INPUT_CLS`, `TOOLBAR_BTN_CLS` paylaşılan Tailwind sınıfları
- `DASHBOARD_CARDS` (11 kart × `{id, label}`) + `DashboardCardId` type union
- `getHiddenCards()` / `saveHiddenCards()` localStorage helper'ları (`kfinans_hidden_cards` anahtarı)

---

## 2. Proje Yapısı

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout (Türkçe locale)
│   ├── globals.css               # Tailwind import + CSS variables
│   ├── _components/              # Paylaşılan bileşenler (Faz 3)
│   │   ├── Logos.tsx             # KFinansLogo (4 size) + MayotekLogo (inline SVG)
│   │   ├── MkkHint.tsx           # MKK e-Yatırımcı info kart + opsiyonel upload butonu
│   │   └── PageHeader.tsx        # Sayfa başlığı + açıklama
│   ├── login/page.tsx            # Giriş ("Kayıt ol" linki + 403 doğrulama mesajı)
│   ├── register/page.tsx         # Kayıt + risk profili + "tekrar gönder"
│   ├── verify-email/page.tsx     # Token landing (Suspense + useSearchParams)
│   ├── legal/                    # KVKK / gizlilik / kullanım şartları / çerez
│   └── dashboard/
│       ├── page.tsx              # Ana dashboard (11 kart + grand total + Snapshot al + Geçmiş + Ayarlar)
│       ├── history/page.tsx      # Snapshot geçmişi (recharts 2 line chart)
│       ├── crypto/page.tsx
│       ├── stocks/               # Hisse senedi (Yahoo + Excel + MKK + maliyet/kâr-zarar + kurum)
│       │   ├── page.tsx
│       │   └── _components/
│       │       ├── HoldingsForm.tsx
│       │       └── StockPositionsTable.tsx
│       ├── tefas/page.tsx        # TEFAS (Excel + MKK + maliyet/kâr-zarar + kurum)
│       ├── wallets/                # 10 zincir cüzdan formu (Faz A)
│       │   ├── page.tsx
│       │   └── _components/
│       │       ├── WalletForm.tsx  # 10 dropdown + (i) info paneli + dinamik placeholder/hint
│       │       └── constants.ts    # Chain, CHAIN_LABELS, CHAIN_SYMBOLS, CHAIN_PLACEHOLDERS, CHAIN_ADDRESS_HINTS
│       ├── bes/page.tsx
│       ├── expenses/             # Harcama (4 component + Excel)
│       │   ├── page.tsx
│       │   └── _components/{ExpenseForm,ExpenseTable,CategoryPieChart,MonthSelector}.tsx
│       ├── planned/              # Planlı ödemeler (Faz 3)
│       │   ├── page.tsx
│       │   └── _components/{PlannedForm,PlannedList,YearlyForecast}.tsx
│       ├── income/               # Gelir takibi (Faz 3)
│       │   ├── page.tsx
│       │   └── _components/...
│       ├── budget/               # Bütçe takibi (Faz 3)
│       │   ├── page.tsx
│       │   └── _components/{BudgetForm,ComparisonTable}.tsx
│       ├── commodities/          # Altın & Gümüş (Faz 3)
│       │   ├── page.tsx
│       │   └── _components/{CommodityForm,CommodityList}.tsx
│       ├── goal/page.tsx         # Finansal hedef (Faz 3)
│       └── settings/page.tsx     # Hesap + risk + şifre + kart gizleme + hesap silme (Faz 3)
│
├── lib/
│   ├── api.ts                    # Tüm API çağrıları + TypeScript DTO'ları
│   └── format.ts                 # fmtTL/fmtNum/fmtDate + INPUT_CLS + DASHBOARD_CARDS + getHiddenCards/saveHiddenCards
│
├── proxy.ts                      # Auth yönlendirme (Next.js 16: middleware → proxy)
│
├── public/images/
│   ├── kfinans-logo.png          # Arşivlik (UI artık inline SVG kullanıyor)
│   └── mayotek-logo.png          # Arşivlik
│
├── next.config.ts                # output: "standalone", watchOptions
├── tsconfig.json                 # strict: true
├── eslint.config.mjs
└── package.json
```

### Önemli: Next.js 16 Değişikliği
- `middleware.ts` **deprecated** → `proxy.ts`
- `export function middleware(...)` → `export function proxy(...)`
- Edge runtime YOK (Node.js'e zorlu); `proxy` runtime'ı seçilemez

---

## 3. API İstemcisi (`lib/api.ts`)

### Konfigürasyon
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```
Production'da `NEXT_PUBLIC_API_URL` Kubernetes ConfigMap'ten gelir.

### Token Yönetimi (Dual Storage + Refresh Rotation)
- `localStorage.access_token` — JS erişimi için (kısa ömürlü; prod 30 dk)
- `localStorage.refresh_token` — yenileme için (uzun ömürlü; 7 gün, FAZ C4 ile aktif)
- `document.cookie` `access_token=...` — `proxy.ts` server-side okuma için

`setAuth(access, refresh)` ikisini birden saklar; `clearAuth()` ikisini birden siler.

> **Güvenlik notu:** `localStorage` XSS'e açık. Production'da `httpOnly` cookie + CSRF token'a geçilmeli (Faz 3 güvenlik iyileştirmesi). FAZ C4 rotation bu açığı kısmen telafi eder — sızan refresh token bir sonraki gerçek refresh çağrısında geçersiz olur.

### Standart Fetch Pattern (FAZ C4 — refresh akışlı)
`request<T>()` fonksiyonu (`lib/api.ts`):
```typescript
async function request<T>(path, options = {}, _isRetry = false): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });

  // FAZ C4: 401 → bir kez refresh dene + retry. /auth/refresh kendi
  // 401'inde retry yapma (sonsuz döngü engeli).
  if (res.status === 401 && !_isRetry && path !== "/auth/refresh") {
    const newToken = await tryRefresh();
    if (newToken) return request<T>(path, options, true);
    clearAuth();
    window.location.replace("/login");
    throw new Error("Oturum süresi doldu");
  }
  // ...
}
```

**Single-flight pattern (kritik):** `tryRefresh()` `_refreshInflight` promise'i paylaşır. Aynı anda 5 farklı request 401 aldığında **tek bir refresh çağrısı** yapılır, hepsi aynı yeni token ile retry eder. Aksi halde backend rotation gereği 2. refresh çağrısı 401 alır ve kullanıcı logout olur.

```typescript
let _refreshInflight: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  if (_refreshInflight) return _refreshInflight;  // single-flight
  _refreshInflight = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, { ... });
      if (!res.ok) return null;
      const data = await res.json();
      setAuth(data.access_token, data.refresh_token);  // yeni rotated refresh
      return data.access_token;
    } finally {
      _refreshInflight = null;
    }
  })();
  return _refreshInflight;
}
```

### Logout Akışı
`api.logout()` parametresiz çağrıldığında storage'dan refresh token okur ve backend'e gönderir; backend `revoked_tokens`'a hem access hem refresh `jti`'sini ekler. Tarayıcıda `clearAuth()` ile her ikisi de silinir.

### TypeScript DTO Örnekleri
```typescript
// Backend Pydantic şemalarıyla birebir
export interface CryptoPosition {
  provider: string;
  symbol: string;
  liquid_quantity: string;   // Decimal → string
  staked_quantity: string;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
}

export interface CryptoResponse {
  positions: CryptoPosition[];
  errors: Record<string, string>;
}
```

---

## 4. Component Sınırları

### Kural: Sayfa Component'leri ≤ 150 Satır
Mevcut `crypto/page.tsx`, `stocks/page.tsx`, `wallets/page.tsx` 250-370 satır arasında. Bu **teknik borç**; component ayrımı + custom hook'lara taşıma yapılmalı.

### Önerilen Component Yapısı
```
app/dashboard/crypto/
├── page.tsx                      # ≤ 100 satır, sadece composition
├── _components/
│   ├── CryptoExchangeCards.tsx   # Borsa toplamı kartları
│   ├── CryptoPositionTable.tsx   # Sıralanabilir tablo
│   └── CryptoFilter.tsx          # Filtre/sıralama UI
└── _hooks/
    └── useCryptoPositions.ts     # API çağrısı + state + sort
```

`_components/` ve `_hooks/` Next.js App Router private folder convention'u — route oluşturmaz.

---

## 5. State Yönetimi

### Mevcut: `useState` + `useEffect` (Yetersiz)
Sayfalar arası paylaşım yok; her sayfa kendi API'sini çağırıyor.

### Plan (Faz 2)
- **Server Component'leri kullan** (App Router) — initial fetch SSR'de
- **`@tanstack/react-query`** — kripto/wallet/portfolio gibi cache'lenebilir veri için
- **Zustand** — global UI state (theme, sidebar collapsed)

### Cache Stratejisi
| Veri | TTL | Trigger |
|------|-----|---------|
| Portföy snapshot | 5 dk | Manuel refresh butonu |
| Kripto pozisyon | 30 sn | Otomatik + manuel |
| TEFAS fiyatı | 1 saat | Manuel refresh |
| Yahoo Finance | 5 dk | Manuel refresh |

---

## 6. Stil Kuralları (Tailwind v4)

### Sınıf Düzeni
```tsx
<div className="
  flex flex-col gap-4              // layout
  rounded-xl border border-zinc-200 // borders
  bg-white p-6                     // background, padding
  shadow-sm hover:shadow-md        // effects
  dark:bg-zinc-900 dark:border-zinc-800
">
```

### Renk Paleti (KFinans Markası)
```css
--brand-primary: #1D4ED8;   /* Mavi — TEFAS tablo başlığı */
--brand-success: #059669;   /* Yeşil — Hisse tablo başlığı */
--brand-warning: #F59E0B;
--brand-danger:  #DC2626;
```

---

## 7. Performans

### Mevcut Sorunlar
- Her sayfa client-side render — initial paint yavaş
- Görsel optimizasyon eksik (kripto logo'ları için Next/Image kullanılmıyor)
- Bundle size kontrolü yok (`@next/bundle-analyzer` eklenmeli)

### Hedefler
- **LCP** (Largest Contentful Paint): < 2.5s
- **FID** (First Input Delay): < 100ms
- **CLS** (Cumulative Layout Shift): < 0.1
- Bundle size: < 200KB (gzip, initial JS)

---

## 8. Erişilebilirlik (a11y)

### Mevcut Durum: ⚠️ Eksik
- ARIA label'lar çoğu butonu kapsamıyor
- Klavye navigasyonu test edilmedi
- Renk kontrastı henüz audit edilmedi

### Kontrol Listesi (Production'a Kadar)
- [ ] Tüm interaktif elementlerde focus ring (`focus:ring-2`)
- [ ] Form input'ları `<label>` ile bağlı
- [ ] Tablo sıralama butonları `aria-sort` ile annotated
- [ ] Modal/dialog'lar `role="dialog"` + focus trap
- [ ] Renk kontrastı WCAG AA (4.5:1 normal, 3:1 büyük metin)

---

## 9. Test Stratejisi (Kuruldu — 2026-04-30)

### Araçlar (Aktif)
- **Vitest 2.1** + jsdom + V8 coverage (%30 threshold)
- **@testing-library/react** + jest-dom + user-event
- **@playwright/test** (Chromium, CI'da retry x2)
- **MSW 2.6** (kurulu, henüz kullanılmadı)

### Mevcut Test Dosyaları
```
frontend/
├── vitest.config.ts             # ✅ jsdom + coverage gate
├── vitest.setup.ts              # ✅ jest-dom + cleanup
├── playwright.config.ts         # ✅ Chromium projects
├── __tests__/
│   └── api.test.ts              # ✅ setAuth/clearAuth — 3 test
└── playwright/
    ├── login.spec.ts            # ✅ Token redirect — 3 senaryo
    └── dashboard.spec.ts        # ✅ Register + login akışı — 2 senaryo
```

### npm Scripts
```bash
npm test              # Vitest run (CI)
npm run test:watch    # Watch mode
npm run test:coverage # Coverage raporu
npm run e2e           # Playwright headless
npm run e2e:ui        # Playwright UI mode
```

### Coverage Hedefi
- **Vitest unit + component:** %70+ (mevcut: %30 threshold)
- **Playwright E2E:** kritik akışların her biri (login ✅, dashboard ✅, holding kaydet ❌, kripto görüntüle ❌)

### Eksik (Faz 2)
- [ ] Component testleri (`CryptoPositionTable`, `LoginForm`, dashboard kartları)
- [ ] Hook testleri (custom hook'lar refactor edildikten sonra)
- [ ] MSW kullanımı — `lib/api.ts` fetch'lerinin mock'lanması
- [ ] Playwright: holding kaydet senaryosu, kripto pozisyon görüntüleme

---

## 10. Eksik / Eklenecek (TODO)

### Kısa Vade (Faz 2)
- [x] Kullanıcı kayıt sayfası (`/register`)
- [x] E-posta doğrulama landing page (`/verify-email`)
- [x] "Snapshot al" butonu — manuel haftalık snapshot tetikleme
- [x] BES manuel giriş ekranı (`/dashboard/bes` + dashboard kartı aktivasyonu)
- [x] Dashboard yenileme: 5 kart + top 3 detay + grand total + reusable `Card` component
- [x] Snapshot geçmişi grafiği (`/dashboard/history` — recharts 2 line chart)
- [ ] Şifre sıfırlama akışı (`/forgot-password`, `/reset-password`)
- [ ] Dashboard haftalık/aylık değişim oranı grafiği (WoW/MoM bar/line)
- [ ] Profil/ayarlar sayfası (risk profili, dil tercihi)

### Orta Vade (Faz 3)
- [ ] Kredi yönetimi sayfası (bakiye + paket satın alma)
- [ ] AI tavsiye ekranı (Markdown render — `react-markdown`)
- [x] Harcama takibi sayfaları (Faz 3 MVP — `/dashboard/expenses` + 4 component + dashboard kartı + Excel import/export)
- [x] Planlı ödemeler & yıllık nakit akışı (`/dashboard/planned` + 3 component)
- [x] Gelir takibi sayfaları (`/dashboard/income`)
- [x] Bütçe takibi (`/dashboard/budget` — UPSERT + comparison)
- [x] Kıymetli madenler (`/dashboard/commodities` — gram/BiGA/sikke + Excel + UI fault-tolerance banner)
- [x] Finansal hedef (`/dashboard/goal` — USD/EUR/GBP/TRY)
- [x] Ayarlar sayfası (`/dashboard/settings` — risk + şifre + kart gizleme + hesap silme)
- [x] MKK e-Yatırımcı Excel import (TEFAS + Stocks sayfalarına `MkkHint` bileşeni)
- [x] Modern UI (emoji → SVG, container max-w-5xl, flex-wrap satırlar, inline logolar)
- [ ] Harcama AI analizi ekranı (kredi tüketimli — `/expenses/analysis/generate`)
- [ ] PDF export (jsPDF veya server-side Puppeteer)
- [ ] Bildirim merkezi (toast + notification panel)

### Uzun Vade (Faz 4)
- [ ] PWA (offline mode, service worker)
- [ ] Çoklu dil desteği (i18n — `next-intl`)
- [ ] Dark mode toggle (mevcut: sadece system preference)
- [ ] Native widget (Flutter ile shared component'ler)

### Teknik Borç
- [ ] `crypto/page.tsx`, `stocks/page.tsx`, `wallets/page.tsx` 300+ satır → component'lere böl
- [ ] Dashboard `page.tsx` 30+ satır büyüdü (5 kart + grand total + Geçmiş butonu); reusable `Card` component çıkarıldı — sayfa parçalamanın başlangıcı, kalan iç state/fetch hook'lara taşınmalı
- [ ] `lib/api.ts` çok dosyaya böl (`lib/api/auth.ts`, `lib/api/portfolio.ts` vb.)
- [ ] React Query veya SWR ile cache'leme
- [ ] httpOnly cookie + CSRF token'a geçiş (XSS savunması)
