/// <reference lib="webworker" />
// KFinans service worker (Serwist).
//
// SECURITY / FINANCE INVARIANT:
//   Financial data is NEVER cached. Every API call — same-origin `/api/*` AND the
//   cross-origin backend (NEXT_PUBLIC_API_URL, e.g. https://api.kfinans.app) — is
//   served with `NetworkOnly`, so a stale balance/portfolio value can never be
//   shown from cache. Only static assets (JS/CSS/fonts/images/icons) and the
//   navigation shell are cached, plus an offline fallback page.
//
// We intentionally do NOT use `defaultCache` from "@serwist/next/worker": its
// preset caches same-origin `/api/` GETs (NetworkFirst, 24h) and cross-origin
// responses (NetworkFirst), both of which would risk serving stale financial
// data. We define our own runtime caching list below.

import {
  CacheFirst,
  ExpirationPlugin,
  NetworkOnly,
  Serwist,
  StaleWhileRevalidate,
  type PrecacheEntry,
  type RuntimeCaching,
  type SerwistGlobalConfig,
} from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    // Injected by @serwist/next at build time.
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope & typeof globalThis;

const ONE_DAY = 24 * 60 * 60;
const ONE_WEEK = 7 * ONE_DAY;
const ONE_YEAR = 365 * ONE_DAY;

// Offline fallback shell — precached so navigations work without network.
const OFFLINE_URL = "/offline";

const runtimeCaching: RuntimeCaching[] = [
  // 1) ALL API traffic → network only, never cached (finance data safety).
  //    Same-origin Next.js route handlers under /api/*.
  {
    matcher: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith("/api/"),
    handler: new NetworkOnly(),
  },
  //    Cross-origin backend API (NEXT_PUBLIC_API_URL host). Any request whose
  //    path contains /api/ on a different origin is the KFinans backend.
  {
    matcher: ({ url, sameOrigin }) => !sameOrigin && /\/api\//.test(url.pathname),
    handler: new NetworkOnly(),
  },

  // 2) Google Fonts (Geist is self-hosted via next/font, but keep this safe).
  {
    matcher: /^https:\/\/fonts\.(?:gstatic|googleapis)\.com\/.*/i,
    handler: new CacheFirst({
      cacheName: "google-fonts",
      plugins: [
        new ExpirationPlugin({ maxEntries: 8, maxAgeSeconds: ONE_YEAR }),
      ],
    }),
  },

  // 3) Static fonts.
  {
    matcher: /\.(?:eot|otf|ttc|ttf|woff|woff2)$/i,
    handler: new CacheFirst({
      cacheName: "static-fonts",
      plugins: [
        new ExpirationPlugin({ maxEntries: 8, maxAgeSeconds: ONE_YEAR }),
      ],
    }),
  },

  // 4) Images / icons.
  {
    matcher: /\.(?:jpg|jpeg|gif|png|svg|ico|webp|avif)$/i,
    handler: new StaleWhileRevalidate({
      cacheName: "static-images",
      plugins: [
        new ExpirationPlugin({ maxEntries: 64, maxAgeSeconds: ONE_WEEK }),
      ],
    }),
  },

  // 5) Next.js build output (immutable, content-hashed) → cache first.
  {
    matcher: /\/_next\/static\/.+/i,
    handler: new CacheFirst({
      cacheName: "next-static",
      plugins: [
        new ExpirationPlugin({ maxEntries: 128, maxAgeSeconds: ONE_YEAR }),
      ],
    }),
  },

  // 6) Other same-origin JS/CSS → revalidate in background.
  {
    matcher: /\.(?:js|css)$/i,
    handler: new StaleWhileRevalidate({
      cacheName: "static-assets",
      plugins: [
        new ExpirationPlugin({ maxEntries: 64, maxAgeSeconds: ONE_DAY }),
      ],
    }),
  },

  // 7) Everything else (cross-origin third-party, etc.) → network only.
  //    We do NOT cache same-origin HTML navigations here: those are handled by
  //    navigationPreload + the precached offline fallback so we never serve a
  //    stale authenticated page shell.
  {
    matcher: () => true,
    handler: new NetworkOnly(),
  },
];

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching,
  fallbacks: {
    entries: [
      {
        url: OFFLINE_URL,
        matcher: ({ request }) => request.destination === "document",
      },
    ],
  },
});

serwist.addEventListeners();

// ─── Web Push (feat/web-push) ───────────────────────────────────────────────
// Serwist's addEventListeners() wires up install/activate/fetch/message only —
// it does NOT register `push` or `notificationclick`. These extra listeners run
// alongside without conflicting. Backend push payload shape: { title, body, url, tag }.

interface PushPayload {
  title?: string;
  body?: string;
  url?: string;
  tag?: string;
}

self.addEventListener("push", (event) => {
  let data: PushPayload = {};
  try {
    data = (event.data?.json() as PushPayload | undefined) ?? {};
  } catch {
    // Malformed/empty payload → fall back to defaults below.
  }
  event.waitUntil(
    self.registration.showNotification(data.title ?? "KFinans", {
      body: data.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: data.url ?? "/dashboard" },
      tag: data.tag,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data?.url as string | undefined) ?? "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((wins) => {
      for (const w of wins) {
        if (w.url.includes(target) && "focus" in w) return w.focus();
      }
      return self.clients.openWindow(target);
    }),
  );
});
