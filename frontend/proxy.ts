import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Audit (orta priority): CSP nonce-based. Her HTML request icin 16-byte rastgele
// nonce uret; CSP header'inda `'nonce-...'` + `'strict-dynamic'` ile script-src
// 'unsafe-inline'/'unsafe-eval' yerine kullan. App layout `headers()` ile
// nonce'u okur ve `<script nonce={nonce}>` ile inline scriptleri imzalar.
//
// Production'da 'strict-dynamic' + nonce; nonce'i tasiyan scriptin yukledigi
// scriptler de tutarli sekilde calisir. Dev'de Turbopack icin 'unsafe-eval'
// kalir (HMR runtime'i icin gerekli — production build'inde dusulur).

const isDev = process.env.NODE_ENV !== "production";

function generateNonce(): string {
  // 16 byte = 22 char base64 (paddingsiz). Edge runtime web crypto kullan.
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let bin = "";
  for (const b of bytes) bin += String.fromCodePoint(b);
  // btoa edge runtime'da global olarak mevcut.
  return btoa(bin);
}

function buildCsp(nonce: string): string {
  const connectSrc = isDev
    ? "connect-src 'self' http://localhost:8000 ws://localhost:* http://localhost:*"
    : "connect-src 'self' https://kfinans.app https://www.kfinans.app https://api.kfinans.app";

  // Dev: Turbopack HMR icin 'unsafe-eval' ve 'unsafe-inline' (next/script + inline runtime).
  // Prod: 'strict-dynamic' + nonce ile inline scriptleri imzala — 'unsafe-inline'/'unsafe-eval' kaldirildi.
  const scriptSrc = isDev
    ? `script-src 'self' 'nonce-${nonce}' 'unsafe-inline' 'unsafe-eval'`
    : `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https:`;

  const directives = [
    "default-src 'self'",
    scriptSrc,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    connectSrc,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ];

  if (!isDev) directives.push("upgrade-insecure-requests");

  return directives.join("; ");
}

export function proxy(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const { pathname } = request.nextUrl;

  // 1) Yonlendirmeler — onceki davranis aynen korunur.
  if (pathname === "/") {
    return NextResponse.redirect(
      new URL(token ? "/dashboard" : "/login", request.url)
    );
  }

  if (pathname.startsWith("/dashboard") && !token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (pathname === "/login" && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // 2) Nonce ve CSP — her HTML response'a unique nonce.
  const nonce = generateNonce();
  const csp = buildCsp(nonce);

  // Request header'ina nonce'i ekle — App layout `headers().get("x-nonce")`
  // ile okuyup `<script nonce={...}>` veya `<Script>` propu olarak iletir.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  // Response'a CSP header'i — next.config.ts'deki static header'i bu override eder.
  response.headers.set("Content-Security-Policy", csp);
  // Debug/test icin nonce'u response'da expose et (uretimde de zararsiz — nonce zaten CSP'de).
  response.headers.set("x-nonce", nonce);

  return response;
}

export const config = {
  // Tum HTML routelarinda CSP nonce uretmeliyiz; eski matcher sadece auth icindi.
  // Static asset'leri (_next/static, favicon, public/) hariç tut.
  matcher: [
    String.raw`/((?!_next/static|_next/image|favicon.ico|images/|.*\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2)$).*)`,
  ],
};
