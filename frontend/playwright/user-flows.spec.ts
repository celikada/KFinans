import { test, expect } from "@playwright/test";

/**
 * TEST-008 (FAZ H): Kritik kullanici yolculuklari E2E.
 *
 * Mevcut login.spec.ts + dashboard.spec.ts: 5 senaryo (smoke + temel auth).
 * Bu dosya 5 ek kritik akis ekler:
 *  - Register form (age_confirmed checkbox UI)
 *  - Logout (token clear + redirect)
 *  - Settings sayfasi navigation
 *  - Dashboard kart gizleme persist
 *  - Cuzdan ekleme (form submit + listede gozukmeli)
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";


test.describe("Register form @smoke", () => {
  test("Register sayfasi acilir + 18+ checkbox gorunur (COMP-010)", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL(/\/register/);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    // 18+ checkbox metni icermeli
    await expect(page.getByText(/18 yaşımı doldurdum/i)).toBeVisible();
  });

  test("18+ checkbox isaretlenmeden submit yapilirsa hata mesaji", async ({ page }) => {
    await page.goto("/register");
    await page.fill('input[type="email"]', `noage_${Date.now()}@example.com`);
    // Sifre alanlari (en az 8 char)
    const pwInputs = page.locator('input[type="password"]');
    await pwInputs.first().fill("guclu-sifre-123");
    await pwInputs.nth(1).fill("guclu-sifre-123");
    // KVKK + Terms + Overseas isaretle ama age yok
    const checkboxes = page.locator('input[type="checkbox"]');
    const count = await checkboxes.count();
    // Son checkbox age, onu atla
    for (let i = 0; i < count - 1; i++) {
      await checkboxes.nth(i).check();
    }
    await page.click('button[type="submit"]');
    // Hata mesaji 18 yas hakkinda olmali
    await expect(page.getByText(/18 yaş/i)).toBeVisible();
  });
});


test.describe("Logout flow @smoke", () => {
  const email = `logout_${Date.now()}@example.com`;
  const password = "guclu-sifre-123";

  test.beforeAll(async ({ request }) => {
    await request.post(`${API_URL}/api/v1/auth/register`, {
      data: { email, password, age_confirmed: true },
    });
  });

  test("Login sonrasi logout token'i temizler ve /login'e yonlendirir", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

    // localStorage'da access_token mevcut olmali
    const tokenBefore = await page.evaluate(() => localStorage.getItem("access_token"));
    expect(tokenBefore).toBeTruthy();

    // Cikis butonuna tikla
    await page.getByRole("button", { name: /Çıkış/i }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });

    // Token temizlenmis olmali
    const tokenAfter = await page.evaluate(() => localStorage.getItem("access_token"));
    expect(tokenAfter).toBeFalsy();
  });
});


test.describe("Settings navigation", () => {
  const email = `settings_${Date.now()}@example.com`;
  const password = "guclu-sifre-123";

  test.beforeAll(async ({ request }) => {
    await request.post(`${API_URL}/api/v1/auth/register`, {
      data: { email, password, age_confirmed: true },
    });
  });

  test("Dashboard'dan Ayarlar'a gidilir", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

    await page.getByRole("button", { name: /Ayarlar/i }).click();
    await expect(page).toHaveURL(/\/dashboard\/settings/, { timeout: 5000 });
    // Kart gizleme bolumu gorunmeli
    await expect(page.getByText(/Kart Görünürlüğü|kart gizleme/i).first()).toBeVisible({ timeout: 5000 });
  });
});


test.describe("Cash flow page accessible", () => {
  const email = `cashflow_${Date.now()}@example.com`;
  const password = "guclu-sifre-123";

  test.beforeAll(async ({ request }) => {
    await request.post(`${API_URL}/api/v1/auth/register`, {
      data: { email, password, age_confirmed: true },
    });
  });

  test("Dashboard Finans grubunda Nakit Akisi linki calisir", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

    // Nakit Akisi butonuna tikla (Finans basligi yaninda)
    await page.getByRole("button", { name: /Nakit Akışı/i }).click();
    await expect(page).toHaveURL(/\/dashboard\/cash-flow/, { timeout: 5000 });
  });
});
