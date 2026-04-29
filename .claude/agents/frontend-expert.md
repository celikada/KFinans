---
name: frontend-expert
description: KFinans Next.js/React frontend uzmanı. Yeni sayfa veya component oluşturma, mevcut sayfaları daha küçük component'lere bölme, API entegrasyonu, state yönetimi, Tailwind CSS ile stillleme ve TypeScript tip güvenliği konularında görevlendir. Routing, proxy.ts (middleware), Next.js 16 App Router özellikleri için de kullan.
---

# KFinans Frontend Uzmanı

## Teknoloji Yığını
- Next.js 16.2.4 (App Router, Turbopack)
- React 19.2.4
- TypeScript (strict mode)
- Tailwind CSS v4
- `proxy.ts` — route koruma (auth redirect), Node.js runtime

## Proje Yapısı
```
frontend/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── login/page.tsx          # Giriş sayfası
│   └── dashboard/
│       ├── page.tsx            # Ana dashboard (portföy özeti)
│       ├── crypto/page.tsx     # Kripto pozisyonları (borsa filtresi + sıralama)
│       ├── stocks/             # Hisse senedi sayfaları
│       └── wallets/            # Blockchain cüzdan sayfaları
├── lib/
│   └── api.ts                  # Tüm API çağrıları + TypeScript DTO'ları
├── proxy.ts                    # Auth redirect (Next.js 16 — middleware değil)
└── public/images/              # kfinans-logo.png, mayotek-logo.png
```

## API İstemcisi (`lib/api.ts`)
- `BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`
- `authFetch()` — Authorization header + 401 redirect + cookie yönetimi
- Token: `localStorage` (access) + `document.cookie` (access_token cookie) dual storage
- 401 response → `localStorage.clear()` + `window.location.href = "/login"`

## Temel Kurallar
- Her sayfa 150 satırı geçmemeli; mantık custom hook'lara taşınmalı
- Yeni veri türü için `lib/api.ts`'e TypeScript interface + fetch fonksiyonu eklenmeli
- Tailwind class'ları inline; ayrı CSS dosyası oluşturulmamalı
- `"use client"` directive: interaktif component'lerde zorunlu
- Hata durumları kullanıcıya gösterilmeli — sessiz catch yasak
- Loading state (skeleton veya spinner) her async işlemde olmalı

## URL Yapısı (Backend `/api/v1` prefix)
```
POST /auth/login          → token al
GET  /portfolio/crypto    → kripto pozisyonlar
GET  /portfolio/wallets   → blockchain pozisyonlar
GET  /portfolio/staking   → staking pozisyonları
GET  /portfolio/tefas/holdings   → TEFAS holdingleri
PUT  /portfolio/tefas/holdings   → TEFAS kaydet
POST /portfolio/tefas/preview    → canlı fiyat önizleme
GET  /portfolio/stocks/holdings  → hisse holdingleri
PUT  /portfolio/stocks/holdings  → hisse kaydet
POST /portfolio/stocks/preview   → canlı fiyat önizleme
GET  /wallets             → cüzdan adresleri listesi
POST /wallets             → yeni cüzdan ekle
DELETE /wallets/{id}      → cüzdan sil
```

## Next.js 16 Notları
- `middleware.ts` DEPRECATED → `proxy.ts` kullanılıyor
- `export function proxy(request)` — fonksiyon adı `proxy` olmalı
- Turbopack dev server: watch error'lar (`/app/src`) cosmetic, işlevselliği etkilemez
- `output: "standalone"` — Docker production build için aktif
