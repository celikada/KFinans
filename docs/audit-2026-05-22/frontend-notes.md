# Frontend Audit Notları — 2026-05-22

Kapsam: `frontend/app/` altındaki 17 dashboard sayfası + 11 alt-sayfa, `_components/`, `_i18n/`, `_hooks/`, `lib/api.ts` (1511 satır) ve `lib/format.ts`, `next.config.ts`, `proxy.ts`. Odak: reusability, portability, Next.js 16 + React 19 best-practice uyumu, WCAG 2.1 AA hedefi.

## ✓ Mevcut Pozitif

- **`proxy.ts` (Next.js 16 pattern)** doğru kullanılmış: `middleware.ts` deprecate edildi, fonksiyon adı `proxy`, matcher dar tutulmuş (`/`, `/login`, `/dashboard/:path*`). Cookie tabanlı erken redirect FOUC'u önlüyor, dashboard layout'ta `localStorage` safety net ile ikili katman var.
- **`lib/format.ts`** (74 satır) ortak format/CSS sabitlerini (`INPUT_CLS`, `TOOLBAR_BTN_CLS`, `fmtTL`, `fmtNum`, `fmtDate`, `shortAddr`) tek dosyada topluyor — magic string kopya yok.
- **`TLValue` component** USD karşılığını localStorage flag + `useUsdRate` hook ile tek noktadan yönetiyor; `kfinans-show-usd-changed` custom event ile aynı sekmede broadcast pattern temiz (storage event aynı sekmede tetiklenmez sorunu çözülmüş).
- **FE-013 `ConfirmDialogProvider` + `useConfirm()`**: 13 yerde `window.confirm()` accessible alertdialog ile değiştirildi. `role="alertdialog"`, focus trap, Esc, destructive flag, i18n bütünleşik.
- **FE-003**: Dashboard ana sayfası 970→727 satıra düştü; `Card / GoalCard / BudgetCard` ve `SnapshotIssuesModal` ayrı `_components/` modüllerine extract edildi.
- **FE-004**: Dashboard 14 paralel fetch'i `cancelled` flag + `safe()` wrapper + `Promise.allSettled` ile race-safe; component unmount sonrası `setState` uyarısı yok.
- **FE-005**: Dashboard auth guard tek noktada (`layout.tsx`); önceki 17 sayfanın her birindeki localStorage kontrolü temizlendi.
- **FAZ C4 refresh token rotation**: `lib/api.ts::tryRefresh()` single-flight (`_refreshInflight` promise) — paralel 401'lerde tek refresh request, sonsuz döngü koruması (`_isRetry` flag + `/auth/refresh` exempt).
- **i18n foundation (i18n-001)**: Cookie tabanlı TR/EN context, dictionary lookup dot-notation, `<html lang>` runtime update (screen reader duyurur), reload yok.
- **A11Y-001**: `<html lang="tr">`, skip-to-content link, `useFocusTrap` hook, modal aria-*; login formu `htmlFor` + `autoComplete=email|current-password` + error `role="alert" aria-live="assertive"`.
- **Dockerfile (DEVOPS-018)** `ARG NEXT_PUBLIC_API_URL=""` ile path-based ingress için boş string default — prod `/api/v1` relative çağrı; build args ile override mümkün.

## ⚠ Çelişki / Düzeltme Notları

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | **Yüksek** | `bg-white rounded-2xl border border-gray-100 shadow-sm` Tailwind class kombinasyonu **68 yerde** copy-paste; benzer şekilde `min-h-screen bg-gray-50` page wrapper 20 sayfada inline | Tasarım sistemi değişimi 68 dosya değiştirmeyi gerektirir; tutarsızlık riski yüksek | `_components/Card.tsx` + `_components/PageShell.tsx` extract et: `<PageShell title="..." back="...">{children}</PageShell>`. `Card`'ın varyantları `tone="default"\|"warning"` props ile |
| 2 | **Yüksek** | i18n-002 **bekliyor**: 17 dashboard sayfasından sadece login + dashboard layout çevrili; geri kalan ~600 string TR-only hard-coded ("Bağlı Borsalar", "Pozisyonlar alınamadı", "Yükleniyor...", vs.). Pek çoğu JSX'te string literal | EN kullanıcı yarım deneyim alıyor; pazarlanabilirlik kısıtlı. Mevcut altyapı (`useTranslation`) yeterli ama uygulama eksik | i18n-002 incremental plan: her PR 2-3 sayfa. Sözlük key namespacing `pages.<sayfa>.<key>` (mevcut sadece `auth.*`, `common.*`, `mfa.*`). ESLint custom rule ile bare TR string yakala (faz sonu) |
| 3 | **Yüksek** | `handle401 = useCallback(() => router.replace("/login"))` pattern 5 sayfada (`tefas`, `stocks`, `bes`, `expenses`, `history`) **21 çağrı** halinde tekrarlanmış. Aynı zamanda `lib/api.ts::request()` zaten 401'de `window.location.replace("/login")` yapıyor — çift redirect mantığı | Davranış tutarsız: lib otomatik redirect ediyor, sayfa da yapıyor. Refactor risk: aynı anda iki redirect race condition | `lib/api.ts`'in 401 davranışı tek doğru kaynak olmalı; sayfalardaki `handle401` kaldırılmalı. `err.message.includes("401")` substring check fragile (mesaj değişirse bozulur) — API helper hata code'u return etmeli |
| 4 | **Yüksek** | `lib/api.ts` **1511 satır**, tek dosya: 50+ endpoint, 30+ TypeScript interface, format helper, refresh logic, error mapper hepsi birlikte. Tek sembol değişimi tüm bundle re-compile | Bakım maliyeti; code splitting kolay değil; tree-shaking sınırlı (named exports olduğu için OK ama IDE search yavaş) | `lib/api/{auth,portfolio,expenses,wallets,...}.ts` modüllerine böl; `lib/api/types.ts` DTO'lar; `lib/api/client.ts` request/refresh core. Index re-export geriye dönük uyumluluk sağlar |
| 5 | **Yüksek** | `lib/api.ts:1` `BASE` modül yükleme anında **bir kez** evaluate ediliyor (`process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`). `NEXT_PUBLIC_*` Next.js 16'da **build-time** inline edildiği için Dockerfile'da `ARG NEXT_PUBLIC_API_URL=""` ile bake ediliyor. Path-based ingress (`""` → `/api/v1`) çalışıyor ama subdomain split (`api.kfinans.app`) prod build'i yeniden gerekiyor | Multi-tenant SaaS veya domain split deploy'da her domain için ayrı image build; runtime config esnekliği yok | Runtime env exposure pattern: server-side `/api/config` endpoint'i + client-side fetch on app load + setState. Veya Next.js 16 `instrumentation.ts` ile runtime ENV inject. Veya `<script id="kfinans-config">window.__CONFIG__={...}</script>` SSR'da inject (CSP nonce ile uyumlu) |
| 6 | **Orta** | `legal/privacy/page.tsx`, `legal/kvkk/page.tsx` içine `kfinans.app`, `kvkk@kfinans.app`, `privacy@kfinans.app` hard-coded. `next.config.ts:11` CSP allowlist'inde `https://kfinans.app`, `https://www.kfinans.app`, `https://api.kfinans.app` hard-coded | White-label / multi-tenant deploy imkânsız; staging env (`staging.kfinans.app`) için CSP fallback yok | Legal sayfalar için `lib/branding.ts` config dosyası (`COMPANY_NAME`, `LEGAL_EMAIL`, `DPO_EMAIL`, `DOMAIN`). CSP'yi env-driven yap: `process.env.NEXT_PUBLIC_ALLOWED_DOMAINS?.split(",")` |
| 7 | **Orta** | `react-hooks/set-state-in-effect` warn'a indirildi (`eslint.config.mjs:28`) — 23 yerde mevcut pattern var. React 19 yeni Effect Event API'siyle düzeltilmesi gerekiyor. `react-hooks/exhaustive-deps` da warn — `// eslint-disable-next-line` 5 dosyada (`bes`, `crypto`, `wallets`, `stocks`, `tefas`) | Cascading render riski; performans/davranış bozukluğu lint'te yakalanmıyor. Yeni dev "warn" görüp ignore ediyor | İki seçenek: (a) React 19 `useEffectEvent` ile refactor (Effect Event docs Context7'den çek), (b) `// eslint-disable` yerine `useRef` pattern ile mount-only fetch'i açıkça belirt. İdeal: `useSWR`/`@tanstack/react-query` migrate — fetch state machine zaten orada |
| 8 | **Orta** | Vitest coverage **%2.93** — sadece `lib/api.ts::setAuth/clearAuth` test ediliyor. 17 page.tsx, 30+ alt-component, custom hook'lar test edilmiyor. E2E Playwright @smoke kapsıyor ama unit level yok | Refactor riski yüksek: TypeScript tip değişimi yakalanır, davranışsal regresyon değil | Hedef: %50 coverage. Öncelikler: `lib/format.ts` (saf fonksiyon), `_i18n/I18nProvider.tsx` (cookie + lookup), `_components/TLValue.tsx` (USD toggle), `_components/ConfirmDialog.tsx` (async resolve). MSW (`msw` zaten devDeps'te) ile API mock; test-expert agent koordinasyonu |
| 9 | **Orta** | Dashboard `page.tsx` halen **727 satır** — 14 ayrı asset için 14 useState seti + 14 fetch + 14 props mapping. FE-003 sonrası 970→727 düştü ama hala "god component" | Yeni asset type eklemek (örn. tahvil) 6-8 satır useState + fetch + Card render gerektirir | Asset-config-driven pattern: `dashboardAssets: AssetConfig[]` (id, fetcher, parser, icon, color). Tek useEffect tüm config'leri iterate eder; her satır küçük `useAsset(config)` hook'una indirgenir |
| 10 | **Orta** | `lib/api.ts::request<T>` 401 retry pattern `_isRetry` flag ile recursion bir kez izinli — doğru. Ama `formatErrorDetail` Pydantic error dizisi formatını parse ediyor (Array.isArray check); FastAPI'nin yeni error formatı değişirse bozulur. Test yok | Backend validation hata mesajları kullanıcıya düzgün yansımayabilir; debug uzun sürer | `formatErrorDetail` için unit test (TS-002 pattern): string, obje, `{detail: [...Pydantic]}`, network error scenarios. Test fixture'lar `tests/fixtures/error-responses.ts` |
| 11 | **Orta** | `lib/api.ts:16` `setAuth` `document.cookie = "access_token=...; SameSite=Strict"` — **`Secure`** flag yok. Localhost HTTP dev'de gerekli değil ama prod'da HTTPS-only cookie olmalı | Cookie güvenliği: prod build'de XSS sonrası cookie çalınma riski (zaten localStorage de var, dual storage zayıflık) | `process.env.NODE_ENV === "production" ? "; Secure" : ""` ekle. İdeal: backend `HttpOnly` cookie set etsin (XSS-proof), frontend localStorage'a hiç yazmasın — ama bu büyük refactor (axios interceptor, refresh token endpoint yenisi) |
| 12 | **Orta** | `_components/PageHeader.tsx` 30 satır — minimal; ama dashboard ana sayfasında kullanılmıyor (`PageHeader` 16 sayfada kullanılıyor, dashboard hariç). Ana sayfanın kendi header'ı var (logout butonu, hidden cards toggle vb. dahil) | Tutarsız UX: dashboard'da geri butonu yok (anchor), alt sayfalarda var. LanguageSwitcher konumu farklı | `PageHeader`'a slot pattern: `actions?: ReactNode`. Ana sayfa kendi `MainHeader`'ını PageHeader extend etsin (logout, hidden-cards bileşeni `actions`'a) |
| 13 | **Orta** | `useFocusTrap` hook tek sayfada (`_hooks/`) ve sadece 2 yerde kullanılıyor (`ConfirmDialog`, `SnapshotIssuesModal`). Diğer modallarda (settings tabs'larda dropdown'lar dahil) focus trap yok | A11y eksik: klavye kullanıcı modal dışına Tab ile çıkabilir, arka plan content'e focus alır | Tüm modal/popup'larda zorunlu kullanım. Lint rule veya code review checklist. WCAG 2.4.3 (Focus Order) AA gerekliliği |
| 14 | **Düşük** | `next.config.ts:15` `script-src 'self' 'unsafe-inline' 'unsafe-eval'` — Next.js runtime inline + Tailwind nedeniyle. CSP nonce-based denenip "Invalid segment config" hatasıyla geri alındı | XSS koruması zayıf: inline script enjekte edilirse çalışır. `'unsafe-eval'` modern Next.js'de gerekli değil (Turbopack hot-reload sadece dev'de) | Yeniden deneme: production-only nonce. Detay: aşağıdaki "CSP Nonce-Based Yeniden Deneme Planı" bölümü |
| 15 | **Düşük** | `useUsdRate` hook localStorage'da kur cache'liyor (5 dk TTL); ama TLValue her instance kendi `useUsdRate()`'ı çağırıyor — bir sayfada 20 TLValue varsa 20 ayrı `useState` ve aynı cache okuma | Mikro perf; localStorage I/O 20× | Hook'u context'e taşı: `<UsdRateProvider>` root layout'ta; tüm TLValue paylaşır. Veya React 19 `cache()` pattern (ama client-only) |
| 16 | **Düşük** | Loading state'leri tutarsız: bazı sayfalar `<p>Yükleniyor...</p>` (BES, crypto), bazı sayfalar inline spinner (dashboard), bazı sayfalar skeleton yok (tefas initial fetch) | UX tutarsız; "Yükleniyor..." text-only screen reader için zayıf (canlı bölge yok) | `_components/Spinner.tsx` + `_components/Skeleton.tsx` + `<LoadingState message="..." />`. `aria-live="polite"` ekle; finished state announce et |
| 17 | **Düşük** | `lib/format.ts::DASHBOARD_CARDS` array'inde `label` TR hard-coded ("BES", "Kredi Kartları"). i18n dictionary'ye taşınmamış | Settings > Kart Görünürlüğü sayfasında EN dilde TR label'lar görünür | `DASHBOARD_CARDS` `labelKey: "dashboard.cards.bes"` formatına çevir; render sırasında `t(labelKey)` |
| 18 | **Düşük** | `app/dashboard/_components/icons.tsx` (varsa) ICONS map inline SVG; benzer şekilde `Logos.tsx` SVG. Ama 14 farklı kart için her ICON inline | Bundle boyutu marjinal artıyor; tree-shaking SVG için zor | Lucide-react veya heroicons npm paketi: import name'lere göre tree-shake. Veya `next/image` + public/icons/ |

## Reusability Patterns

- **PageHeader, MkkHint, Logos, ConfirmDialog, TLValue, DashboardCard (Card/GoalCard/BudgetCard), SnapshotIssuesModal, useFocusTrap, useUsdRate, useTranslation, useConfirm** — 11 reusable parça var. İyi.
- **Eksik kritik primitive'ler:**
  - `PageShell` (page wrapper + header + main grid) — 17 sayfa kendi düzenini yazıyor.
  - `Card` (basic surface) — 68 yerde inline class.
  - `Section` (h2 + p text) — ~30 yerde duplicate.
  - `EmptyState` (icon + title + cta) — manuel oluşturuluyor her sayfada.
  - `LoadingState` / `Spinner` / `Skeleton` — bazıları text-only.
  - `ErrorBanner` (`role="alert"` + style) — login dışında kullanılmıyor; sayfalar inline `<p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">` yazıyor.
  - `Toolbar` (export/import butonları + filtreler) — `TOOLBAR_BTN_CLS` var ama wrapper yok.
- **lib/api.ts**: 50+ endpoint tek modülde — `lib/api/{module}.ts` split (#4).
- **Tahmini silinebilir kod**: page.tsx'lerde ortak `min-h-screen + max-w-3xl mx-auto px-6 py-8 space-y-6` boilerplate'i ile **150-200 satır** PageShell extract sonrası temizlenebilir.

## Portability

- **`NEXT_PUBLIC_API_URL` build-time bake (Next.js 16 davranışı)**: Dockerfile `ARG NEXT_PUBLIC_API_URL=""` ile path-based default ayarlanmış. Path-based ingress (`kfinans.app/api/v1`) çalışıyor. Subdomain split (`api.kfinans.app`) için ayrı build gerekir. **Runtime config pattern eksik** (#5).
- **Hard-coded domain referansları**:
  - `next.config.ts:11` CSP allowlist 3 domain.
  - `legal/{privacy,kvkk}/page.tsx` `@kfinans.app` mailto + domain text.
  - `playwright/*.spec.ts` 4 test dosyası `NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` fallback (test-only, kabul edilebilir).
- **localStorage anahtarları**: `access_token`, `refresh_token`, `kfinans_show_usd`, `kfinans_usd_rate_cache`, `kfinans_hidden_cards`, `kfinans-locale` (cookie). 3 farklı prefix tutarsız (`kfinans_`, `kfinans-`, ham `access_token`). Çoklu uygulama aynı domain'i paylaşırsa çakışma olabilir.
- **`localhost:8000` hard-coded**: 6 dosyada (5 test + lib/api + next.config + scripts/smoke.sh) — kabul edilebilir dev default.
- **Tailwind class'lar inline (kural gereği)** — taşınabilir ama design system primitive'ler eksikse (#1) sıkıntılı.
- **Sentry browser SDK henüz yok** (OBS-001 sadece backend) — frontend exception izleme yok.

## Best Practice — Next.js 16 + React 19 Uyumu

- **proxy.ts** ✓ doğru pattern (`middleware.ts` deprecated).
- **App Router** ✓ tüm sayfalar.
- **Server Component eksik**: Tüm sayfalar `"use client"`. Login + dashboard layout için bu zorunlu (interaktivite), ama legal sayfaları (`legal/privacy/page.tsx`, `legal/kvkk/page.tsx`, `legal/terms/page.tsx`, `legal/cookies/page.tsx`) statik HTML — RSC olmalı. Bundle JS azalır, SEO iyileşir.
- **Turbopack** ✓ default (dev). `watchOptions.pollIntervalMs: 1000` Windows WSL ortamı için ekli.
- **`output: "standalone"`** ✓ Docker prod build.
- **`async headers()`** ✓ CSP + HSTS + X-Frame-Options vs.
- **React 19 features kullanılmıyor**: `use()` hook (promise resolve), `useOptimistic`, `Action` form (server action). Tüm form'lar manuel `useState` + `handleSubmit`. Gelecekte: settings sayfası `<form action={updateProfile}>` server action ile basitleşebilir.
- **`React.memo` / `useMemo` / `useCallback`**: Dashboard 727 satırda 14 fetch, ama child'lar pure değil — re-render maliyeti net değil. React Compiler (`react-compiler` Next.js 16 opt-in) etkinleştirilmesi gerek (manuel memo ihtiyacını otomatize eder).

## A11y WCAG 2.1 AA Hedef Durumu

| Kriter | Durum | Not |
|---|---|---|
| 1.3.1 Info & Relationships | ✓ | Label-input pairing login/register'da, table semantic kullanım iyi |
| 1.4.3 Contrast Minimum | ⚠ | Gray-400 placeholder text `text-gray-400` gri-üstü-beyazda 3.2:1 (AA için 4.5:1) — borderline. Lighthouse axe doğrulanmalı |
| 2.1.1 Keyboard | ✓ | Native HTML button/input |
| 2.1.2 No Keyboard Trap | ✓ | Modal'larda focus trap (useFocusTrap) |
| 2.4.1 Bypass Blocks | ✓ | Skip-to-content link (dashboard layout) |
| 2.4.3 Focus Order | ⚠ | Modal yes ama dropdown'lar (settings) custom — review gerekli |
| 2.4.7 Focus Visible | ✓ | `focus-visible:ring-2 focus-visible:ring-blue-500` çoğu input/butonda |
| 3.1.1 Language of Page | ✓ | `<html lang="tr">`, dil değişimi runtime update |
| 3.3.1 Error Identification | ⚠ | Login `role="alert"` var; register/settings/cash/expense formlarında `aria-live` yok |
| 3.3.2 Labels & Instructions | ⚠ | Çoğu yerde `<label htmlFor>` var ama bazı inline form'lar (manual-crypto, history filter) sadece placeholder kullanıyor |
| 4.1.2 Name, Role, Value | ⚠ | İkon-only butonlarda `aria-label` 11 dosyada eklendi ama dropdown/toggle butonlarda inconsistent |
| 4.1.3 Status Messages | ⚠ | Loading "Yükleniyor..." `aria-live` ile sarmıyor; spinner'lar `aria-busy="true"` eksik |

**Genel hedef:** %60-70 AA uyumlu. Eksikler: aria-live status mesajları, contrast review, dropdown focus trap, error mesaj aria-live tutarlılığı. **axe-core entegrasyonu** (`@axe-core/playwright`) yapılırsa otomatik test mümkün.

## CSP Nonce-Based Yeniden Deneme Planı (Next.js 16 proxy pattern)

**Geçmiş başarısızlık**: Nonce'u `app/layout.tsx`'te `export const dynamic = "force-dynamic"` ile çalıştırma denemesi "Invalid segment config" build hatası verdi.

**Yeni plan** (Next.js 16 önerilen pattern):

1. **Nonce üretimini `proxy.ts`'e taşı**:
   ```ts
   // proxy.ts
   const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
   const requestHeaders = new Headers(request.headers);
   requestHeaders.set("x-nonce", nonce);
   const response = NextResponse.next({ request: { headers: requestHeaders } });
   response.headers.set("Content-Security-Policy",
     `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`);
   ```
2. **Layout'ta `headers()` ile nonce oku**:
   ```ts
   // app/layout.tsx (Server Component zorunlu)
   import { headers } from "next/headers";
   const nonce = (await headers()).get("x-nonce") ?? "";
   ```
3. **`<Script nonce={nonce}>` next/script + Next.js otomatik inline'lara nonce iletir** (Next.js 16 native destek var).
4. **matcher genişletme**: `proxy.ts::config.matcher` `/((?!api|_next/static|_next/image|favicon.ico).*)` — tüm HTML yanıtlarına nonce uygula. Static asset'ler bypass.
5. **Şart**: `output: "standalone"` runtime'da nonce header'ı geçer mi doğrula (Vercel CDN edge ile çalışıyor; K3s nginx-ingress önünde de çalışmalı — ingress-nginx default header'ları pass-through eder).

**Riskler**:
- Tailwind inline style (`'unsafe-inline'` style için) nonce'a çevrilmez — `style-src 'self' 'nonce-...'` ile çakışır. Tailwind v4 `@layer` kullanır, inline `style` attribute az ama Recharts SVG inline style üretir. `style-src 'self' 'unsafe-inline'` kalsın (XSS impact düşük).
- Dev mode (`next dev` Turbopack) HMR inline script enjekte ediyor — nonce uygulanmıyor. `isDev ? 'unsafe-inline' : nonce` branching koru.

**Yedek plan**: nonce yerine `sha256-...` hash'leri inline script için pre-compute. Daha karmaşık ama build-time deterministic.

## Önerilen Eylem Sırası

1. **i18n-002 incremental rollout** (#2) — kullanıcı görünür, planlanmış 600 string.
2. **`PageShell` + `Card` + `EmptyState` extract** (#1, #9, #12) — 200 satır tasarruf, gelecek sayfa eklemelerini kolaylaştırır.
3. **handle401 cleanup + `lib/api.ts` 401 davranışı netleştirme** (#3) — bug riski.
4. **`lib/api.ts` modüler split** (#4) — IDE/refactor performansı.
5. **Vitest coverage %50 hedefi** (#8) — test-expert agent ile koordineli.
6. **CSP nonce yeniden deneme** (#14) — security-expert + devops-expert koordineli (ingress header pass-through doğrulama).
7. **WCAG AA gap fix** (contrast review, aria-live, dropdown focus trap) — compliance-expert ile koordineli.
8. **Runtime config pattern** (#5) — SaaS multi-tenant veya domain split olduğunda zorunlu olacak; şimdi opsiyonel.

## Diğer Ajanlarla Koordinasyon

- **test-expert**: Vitest coverage artışı, MSW mock setup, axe-core Playwright entegrasyonu.
- **compliance-expert**: KVKK metin domain hard-code'ları (#6), WCAG AA gap'leri.
- **security-expert**: CSP nonce planı (#14), Secure cookie flag (#11), localStorage vs HttpOnly debate.
- **backend-expert**: 401 davranışı netleştirme (#3) için backend error code standardı; runtime config endpoint'i (#5).
- **devops-expert**: Dockerfile build args strategy (#5), ingress header pass-through (CSP nonce için).
- **ai-expert**: Doğrudan etkilenmez.
