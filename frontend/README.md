# KFinans Frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS. Dashboard + 20 alt sayfa, MKK Excel direkt import, SVG ikonlu modern UI, TR/EN çok dillilik (cookie tabanlı).

→ Genel proje açıklaması için [üst seviye README](../README.md).
→ Detaylı frontend mimarisi için [`docs/04-frontend.md`](../docs/04-frontend.md).

---

## Kurulum

```bash
cd frontend
npm install

# Ortam değişkenleri (opsiyonel)
cp .env.local.example .env.local

# Geliştirme sunucusu
npm run dev
```

Tarayıcı: http://localhost:3000

---

## Proje Yapısı

```
frontend/
├── app/                     # Next.js App Router
│   ├── layout.tsx           # Root layout + I18nProvider + ConfirmDialogProvider
│   ├── page.tsx             # Boş — proxy.ts /login veya /dashboard'a yönlendirir
│   ├── login/               # Giriş + MFA 2. adım
│   ├── register/            # Kayıt + KVKK onayları
│   ├── verify-email/        # E-posta doğrulama landing
│   ├── dashboard/           # Ana dashboard + 14 kart (Portföy/Finans iki grup)
│   │   ├── page.tsx         # Dashboard ana sayfa
│   │   ├── layout.tsx       # Skip-link + LanguageSwitcher + nav
│   │   ├── tefas/           # TEFAS fon portföyü + MKK import
│   │   ├── stocks/          # Hisse senedi + MKK import
│   │   ├── crypto/          # Kripto borsa pozisyonları + entegrasyon CRUD
│   │   ├── manual-crypto/   # Manuel kripto (API'siz borsalar + asset catalog)
│   │   ├── wallets/         # Blockchain cüzdan CRUD + şifre korumalı tam-adres export
│   │   ├── bes/             # Bireysel emeklilik
│   │   ├── commodities/     # Altın & gümüş (gram/BiGA/sikke)
│   │   ├── cash/            # Nakit / banka (TRY/USD/EUR/GBP)
│   │   ├── cash-flow/       # 12 aylık nakit akış projeksiyonu + rapor
│   │   ├── credit-cards/    # Kredi kartları + [id] detay (ekstre/taksit)
│   │   ├── expenses/        # Harcamalar + Excel I/O
│   │   ├── income/          # Gelirler + recurring + realize + Excel I/O
│   │   ├── planned/         # Planlı ödemeler + 12 ay tahmin
│   │   ├── budget/          # Bütçe limit + karşılaştırma
│   │   ├── goal/            # Finansal özgürlük hedefi
│   │   ├── history/         # Snapshot geçmişi grafikleri + rapor indirme
│   │   ├── settings/        # Hesap, USD tercih, profil, şifre, kart gizleme
│   │   │   └── security/    # MFA / TOTP kurulum + recovery code
│   │   └── _components/     # DashboardCard, icons, SnapshotIssuesModal
│   ├── legal/               # KVKK, gizlilik, şartlar, çerezler
│   ├── _components/         # Logos, MkkHint, PageHeader, TLValue, ConfirmDialog
│   ├── _hooks/              # useFocusTrap
│   └── _i18n/               # I18nProvider, LanguageSwitcher, dictionaries/{tr,en}.json
├── lib/
│   ├── api.ts               # Geriye-uyumlu re-export (api namespace)
│   ├── api/                 # Domain bazlı istemci (_client + 19 domain + types)
│   └── format.ts            # fmtTL, fmtNum, fmtDate + DASHBOARD_CARDS/GROUPS
├── proxy.ts                 # Next middleware (auth gate)
├── public/images/           # KFinans + Mayotek PNG (eski, SVG'ye geçildi)
├── playwright/              # E2E @smoke test'leri
├── __tests__/               # Vitest unit + component test'leri
├── package.json
└── next.config.ts           # output: standalone + güvenlik header'ları (HSTS/CSP)
```

---

## Komutlar

```bash
npm run dev              # Geliştirme sunucusu (Turbopack)
npm run build            # Production build
npm run start            # Production server
npm run lint             # ESLint
npm test                 # Vitest unit
npm run e2e              # Playwright E2E (npm run e2e:ui — UI mode)
npm run smoke            # Production smoke (scripts/smoke.sh)
npx tsc --noEmit         # Type check
```

---

## Önemli Bileşenler

### Layout & Navigasyon
- **`app/_components/PageHeader.tsx`** — Tüm alt sayfalarda kullanılan başlık + Geri butonu
- **`proxy.ts`** — Next middleware: token yoksa `/dashboard/*` → `/login`'e yönlendir

### Logolar (inline SVG)
- **`KFinansLogo`** — `size="sm|md|lg|xl"` propu, 24/32/40/64 px ikon + wordmark
- **`MayotekLogo`** — Footer için kompakt versiyon

### Dashboard Kartları
- 14 kart (Portföy 8 + Finans 6), hepsi inline SVG ikonlu (emoji yok)
- Kullanıcı `/dashboard/settings` üzerinden istediği kartı gizleyebilir (localStorage `kfinans_hidden_cards`)
- Her kart kendi backend endpoint'inden veri çeker, paralel yüklenir

### Çok Dillilik (i18n)
- `app/_i18n/` — cookie tabanlı (`kfinans-locale`) TR/EN; `useTranslation()` + `LanguageSwitcher`
- `dictionaries/{tr,en}.json` iki dosya da senkron; sayfaların tamamı çevrilidir (reload yok)

### Güvenlik (MFA)
- `/dashboard/settings/security` — TOTP kurulum (QR + recovery code), devre dışı bırakma
- Login MFA etkin kullanıcıda ikinci adım doğrulaması ister (`pre_mfa_token`)

### MKK Excel Import
- **`MkkHint`** bileşeni: Bilgi notu + opsiyonel "MKK Excel'i Yükle" butonu
- TEFAS sayfası → Fon satırlarını yükler
- Stocks sayfası → HS + Ek Tanım=A satırlarını yükler (.IS suffix otomatik)
- Backend `xlrd` ile binary .xls parse eder

### Form Düzenleri
- TEFAS ve Stocks: `flex flex-wrap` + `min-w-[160px]` ile responsive satır
- Tüm input'larda `text-gray-900 placeholder:text-gray-400` (okunaklılık için)
- INPUT_CLS sabiti `lib/format.ts`'te

---

## State + API Pattern

```tsx
// Tipik bir dashboard alt sayfası
const [data, setData] = useState<TDto[] | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState("");

useEffect(() => {
  if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
  api.getX()
    .then(setData)
    .catch(err => err.message.includes("401") ? router.replace("/login") : setError(err.message))
    .finally(() => setLoading(false));
}, [router]);
```

---

## Stillendirme

- **Tailwind CSS 4** — utility-first, no custom config beyond defaults
- **Renk paleti:** gray (nötr), blue (primary), emerald (kazanç), red (zarar/aşım), amber (uyarı/altın), violet (planlı/hedef), purple (cüzdan), indigo (hisse)
- **Yuvarlak köşeler:** `rounded-lg` (8px), `rounded-xl` (12px), `rounded-2xl` (16px)
- **Tipografi:** `tabular-nums` para tutarlarında, `font-mono` kod/ticker'da

---

## Test Stratejisi

- **Vitest** (`__tests__/`): Lib fonksiyonları (`api.ts`, `format.ts`)
- **Playwright** (`playwright/`): E2E (login, dashboard render)
- TypeScript `tsc --noEmit` CI gate
- ESLint `next/core-web-vitals` config
