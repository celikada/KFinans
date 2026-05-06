import type { NextConfig } from "next";

// Production CSP — frontend HTML response'larina uygulanir.
// API çağrılarına connect-src ile izin veriyoruz (kfinans.app + localhost dev).
// Next.js inline runtime için 'unsafe-inline' (script-src) kaçınılmaz; nonce
// stratejisi ileride App Router middleware ile eklenebilir.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  // Next.js dev + runtime
  "style-src 'self' 'unsafe-inline'",                  // Tailwind inline + CSS-in-JS
  "img-src 'self' data: blob:",                        // chart canvas, base64
  "font-src 'self' data:",
  "connect-src 'self' https://kfinans.app https://www.kfinans.app",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

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
