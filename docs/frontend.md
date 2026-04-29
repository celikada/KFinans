# Frontend Mimarisi

**Sahip ajan:** `frontend-expert`
**Stack:** Next.js 16.2.4 (App Router, Turbopack) + React 19 + TypeScript (strict) + Tailwind CSS v4

---

## 1. Mevcut Fonksiyonel Gereksinimler (Çalışan)

Aşağıdaki ekranlar **fonksiyonel gereksinim** olarak kabul edilir — production'a kadar regresyon kabul edilmez:

| Ekran | URL | Durum |
|-------|-----|-------|
| Giriş | `/login` | ✅ Aktif |
| Ana Dashboard (özet kartlar) | `/dashboard` | ✅ Aktif |
| Kripto pozisyonları (borsa filtresi + sıralama) | `/dashboard/crypto` | ✅ Aktif |
| Hisse senedi portföyü | `/dashboard/stocks` | ✅ Aktif |
| Blockchain cüzdanları | `/dashboard/wallets` | ✅ Aktif |
| TEFAS holdings (preview + Excel) | `/dashboard/tefas` | ✅ Aktif |

### Auth Davranışı (Korunmalı)
- Token yoksa `/dashboard/*` → `/login`'e redirect
- Token varsa `/login` → `/dashboard`'a redirect
- 401 response → `localStorage` temizlenir, `/login`'e redirect
- Bu yönlendirme `proxy.ts` (eski adıyla `middleware.ts`) ile yapılır

---

## 2. Proje Yapısı

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout (Türkçe locale)
│   ├── globals.css               # Tailwind import + CSS variables
│   ├── login/
│   │   └── page.tsx              # Giriş sayfası
│   └── dashboard/
│       ├── layout.tsx            # Dashboard chrome (header + sidebar)
│       ├── page.tsx              # Ana dashboard (özet kartlar)
│       ├── crypto/page.tsx       # Kripto pozisyonları
│       ├── stocks/               # Hisse senedi
│       │   └── page.tsx
│       ├── wallets/              # Blockchain cüzdanları
│       │   └── page.tsx
│       └── tefas/page.tsx        # TEFAS
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

## 9. Test Stratejisi

### Mevcut: ❌ Hiç Yok
Frontend testleri henüz yazılmamış.

### Plan
- **Vitest** + React Testing Library (Jest yerine — Vite ekosistemi daha hızlı)
- **MSW** (Mock Service Worker) — API mock
- **Playwright** — E2E (login → kripto görüntüleme akışı)

```
__tests__/
├── unit/
│   ├── api.test.ts                # lib/api.ts fonksiyonları
│   └── hooks/
│       └── useCryptoPositions.test.tsx
├── components/
│   ├── CryptoPositionTable.test.tsx
│   └── LoginForm.test.tsx
└── e2e/
    └── login-flow.spec.ts
```

### Coverage Hedefi
- Unit + component: %70+
- E2E: kritik akışların her biri (login, holding kaydet, kripto görüntüle)

---

## 10. Eksik / Eklenecek (TODO)

### Kısa Vade (Faz 2)
- [ ] Kullanıcı kayıt sayfası (`/register`)
- [ ] E-posta doğrulama landing page
- [ ] Şifre sıfırlama akışı
- [ ] BES manuel giriş ekranı
- [ ] Dashboard haftalık/aylık değişim grafiği (Recharts veya Chart.js)
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
- [ ] `lib/api.ts` çok dosyaya böl (`lib/api/auth.ts`, `lib/api/portfolio.ts` vb.)
- [ ] React Query veya SWR ile cache'leme
- [ ] httpOnly cookie + CSRF token'a geçiş (XSS savunması)
