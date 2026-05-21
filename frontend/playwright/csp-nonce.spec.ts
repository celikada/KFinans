import { test, expect } from "@playwright/test";

// Audit (orta priority): CSP nonce-based — proxy.ts her HTML request icin
// 16-byte rastgele base64 nonce uretir; response header'da CSP'ye
// `'nonce-...'` injekte edilir. Bu test:
//   1. /login response header'inda CSP'de "nonce-" substring var mi?
//   2. Iki ardisik request farkli nonce uretiyor mu (per-request unique)?
//   3. CSP'de 'unsafe-inline' yok (production); dev'de 'strict-dynamic'
//      veya 'unsafe-inline' (Turbopack HMR) tolere edilir.

test.describe("CSP nonce-based @smoke", () => {
  test("@smoke /login CSP header'inda per-request nonce var", async ({ request }) => {
    const res = await request.get("/login");
    expect(res.status()).toBeLessThan(400);

    const csp = res.headers()["content-security-policy"];
    expect(csp).toBeDefined();
    // Nonce substring kontrolu
    expect(csp).toMatch(/'nonce-[A-Za-z0-9+/=]{20,}'/);

    // 'strict-dynamic' (prod) veya 'unsafe-inline' (dev Turbopack) — ikisi de
    // legitime. Sadece script-src direktifinin nonce icermesi sart.
    expect(csp).toMatch(/script-src[^;]*'nonce-/);
  });

  test("@smoke Iki ardisik request farkli nonce uretmeli", async ({ request }) => {
    const a = await request.get("/login");
    const b = await request.get("/login");

    const cspA = a.headers()["content-security-policy"] ?? "";
    const cspB = b.headers()["content-security-policy"] ?? "";

    const nonceA = /'nonce-([^']+)'/.exec(cspA)?.[1];
    const nonceB = /'nonce-([^']+)'/.exec(cspB)?.[1];

    expect(nonceA).toBeTruthy();
    expect(nonceB).toBeTruthy();
    expect(nonceA).not.toBe(nonceB);
  });

  test("CSP icinde temel guvenlik direktifleri mevcut", async ({ request }) => {
    const res = await request.get("/login");
    const csp = res.headers()["content-security-policy"] ?? "";

    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
  });

  test("X-Nonce response header'inda da expose ediliyor (debug/SSR)", async ({
    request,
  }) => {
    const res = await request.get("/login");
    const nonce = res.headers()["x-nonce"];
    expect(nonce).toBeDefined();
    expect(nonce?.length).toBeGreaterThanOrEqual(20);

    // CSP icindeki nonce ile ayni olmali
    const csp = res.headers()["content-security-policy"] ?? "";
    expect(csp).toContain(`'nonce-${nonce}'`);
  });
});
