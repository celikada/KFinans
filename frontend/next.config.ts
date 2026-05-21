import type { NextConfig } from "next";

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

export default nextConfig;
