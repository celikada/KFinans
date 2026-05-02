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
| Ana Dashboard (5 kart + grand total + "Snapshot al" + "Geçmiş" butonu) | `/dashboard` | ✅ Aktif |
| Snapshot geçmişi (recharts line chart x2) | `/dashboard/history` | ✅ Aktif |
| Kripto pozisyonları (borsa filtresi + sıralama) | `/dashboard/crypto` | ✅ Aktif |
| Hisse senedi portföyü (Yahoo Finance + Excel) | `/dashboard/stocks` | ✅ Aktif |
| Blockchain cüzdanları (ekle/sil + Excel) | `/dashboard/wallets` | ✅ Aktif |
| TEFAS holdings (preview + Excel) | `/dashboard/tefas` | ✅ Aktif |
| BES manuel giriş (plan adı + ₺ + Excel) | `/dashboard/bes` | ✅ Aktif |

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

### Dashboard Yenileme (Yeni)
- 5 kart yapısı: TEFAS, Kripto, **Hisse Senedi** (`/dashboard/stocks`'a link), **Blockchain Cüzdanlar** (`/dashboard/wallets`'a link — eski "yakında" pasif kart aktive edildi), BES
- Her kartta **top 3 detay** (en yüksek 3 varlık ad + TL): TEFAS top 3 fund kodu, Kripto top 3 coin, Hisse top 3 ticker, Blockchain top 3 sembol, BES top 3 plan
- Üstte **"Toplam: X ₺"** (5 kart toplamı / grand total)
- Sağ üstte **"Geçmiş"** butonu → `/dashboard/history`
- Reusable `Card` component (5 kart için ortak — büyük sayfa parçalama refactor'ünün başlangıcı)

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

---

## 2. Proje Yapısı

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout (Türkçe locale)
│   ├── globals.css               # Tailwind import + CSS variables
│   ├── login/
│   │   └── page.tsx              # Giriş sayfası ("Kayıt ol" linki dahil)
│   ├── register/
│   │   └── page.tsx              # Kayıt formu + risk profili dropdown + "tekrar gönder"
│   ├── verify-email/
│   │   └── page.tsx              # Token landing (Suspense + useSearchParams)
│   └── dashboard/
│       ├── layout.tsx            # Dashboard chrome (header + sidebar)
│       ├── page.tsx              # Ana dashboard (5 kart + grand total + Snapshot al + Geçmiş)
│       ├── history/              # Snapshot geçmişi (recharts 2 line chart)
│       │   └── page.tsx
│       ├── crypto/page.tsx       # Kripto pozisyonları
│       ├── stocks/               # Hisse senedi (Yahoo Finance + Excel)
│       │   └── page.tsx
│       ├── wallets/              # Blockchain cüzdanları (ekle/sil + Excel)
│       │   └── page.tsx
│       ├── tefas/page.tsx        # TEFAS
│       └── bes/                  # BES manuel giriş (plan adı + ₺ + Excel)
│           └── page.tsx
│
├── lib/
│   └── api.ts                    # Tüm API çağrıları + TypeScript DTO'ları
│
├── proxy.ts                      # Auth yönlendirme (Next.js 16: middleware → proxy)
│
├── public/images/
│   ├── kfinans-logo.png
│   └── mayotek-logo.png
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

### Token Yönetimi (Dual Storage)
- `localStorage.access_token` — JS erişimi için
- `document.cookie` `access_token=...` — `proxy.ts` server-side okuma için
- `localStorage.refresh_token` — yenileme için

> **Güvenlik notu:** `localStorage` XSS'e açık. Production'da `httpOnly` cookie + CSRF token'a geçilmeli (Faz 3 güvenlik iyileştirmesi).

### Standart Fetch Pattern
```typescript
async function authFetch(path: string, init?: RequestInit) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${BASE_URL}/api/v1${path}`, {
    ...init,
    headers: { ...init?.headers, Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) {
    localStorage.clear();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  return res;
}
```

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
- [ ] Harcama takibi sayfaları (kategori, liste, analiz)
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
