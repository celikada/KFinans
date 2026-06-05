import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";

// CSP — frontend HTML response'larina uygulanir.
// Dev modda backend http://localhost:8000'da, prod'da https://kfinans.app'da.
// Bu yuzden connect-src ve upgrade-insecure-requests ortama gore degisir.
const isDev = process.env.NODE_ENV !== "production";

const connectSrc = isDev
  // Dev: localhost backend (http) + WebSocket HMR (ws)
  ? "connect-src 'self' http://localhost:8000 ws://localhost:* http://localhost:*"
  : "connect-src 'self' https://kfinans.app https://www.kfinans.app https://api.kfinans.app";

const cspBase = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  // Next.js dev + runtime
  "style-src 'self' 'unsafe-inline'",                  // Tailwind inline + CSS-in-JS
  "img-src 'self' data: blob:",                        // chart canvas, base64
  "font-src 'self' data:",
  connectSrc,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  // PWA: service worker + web app manifest must load from same origin.
  "worker-src 'self'",
  "manifest-src 'self'",
];

// upgrade-insecure-requests sadece production'da — dev'de HTTP backend'i HTTPS'e
// cevirmeye calisip "Failed to fetch" hatasina yol acar.
const csp = (isDev ? cspBase : [...cspBase, "upgrade-insecure-requests"]).join("; ");

const securityHeaders = [
  // HSTS — 1 yıl + alt domain + preload (.app TLD zaten preload listesinde
  // ama defence-in-depth)
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
  // Anti-framing / sniffing
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Referrer
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // CSP
  { key: "Content-Security-Policy", value: csp },
  // Permissions
  {
    key: "Permissions-Policy",
    value: "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
  },
  // Cross-Origin izolasyon
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  // Next.js 16 Turbopack varsayılan. Serwist (`withSerwist`) bir `webpack` config
  // enjekte ettiği için `next dev` "custom webpack config" hatası verip çıkıyordu
  // (dev restart döngüsü). Boş `turbopack` config'i bu hatayı susturur → dev
  // Turbopack'te hızlı çalışır; serwist dev'de zaten disabled. Prod build
  // `next build --webpack` ile açıkça webpack kullandığından bu ayardan etkilenmez.
  turbopack: {},
  watchOptions: {
    pollIntervalMs: 1000,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

// PWA service worker (Serwist). Source app/sw.ts is compiled to public/sw.js at
// build time. Disabled in development so `next dev` (Turbopack) stays fast and
// the SW never serves stale shells while iterating. `next build` must run with
// the Webpack bundler (npm run build uses --webpack) because Serwist's SW
// compilation requires Webpack; the app bundle itself is unaffected.
const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
  // Reload all open tabs once a new SW activates, so users get fresh assets.
  reloadOnOnline: true,
});

export default withSerwist(nextConfig);
