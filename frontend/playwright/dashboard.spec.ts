import { test, expect } from "@playwright/test";

const TEST_EMAIL = `e2e_${Date.now()}@example.com`;
const TEST_PASSWORD = "guclu-sifre-123";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

test.describe.serial("Dashboard akışı (kayıt → giriş → dashboard)", () => {
  test.beforeAll(async ({ request }) => {
    // E2E kullanıcısını backend'e direkt kaydet
    // COMP-010: age_confirmed=true zorunlu (KVKK 2018/482, TMK m.16)
    await request.post(`${API_URL}/api/v1/auth/register`, {
      data: { email: TEST_EMAIL, password: TEST_PASSWORD, age_confirmed: true },
    });
  });

  test("Doğru kimlik bilgileriyle giriş yapıp dashboard'u görmeli", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', TEST_EMAIL);
    await page.fill('input[type="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  });

  test("Giriş yaptıktan sonra /login'e gitmek dashboard'a yönlendirmeli", async ({ page }) => {
    // Önce login ol
    await page.goto("/login");
    await page.fill('input[type="email"]', TEST_EMAIL);
    await page.fill('input[type="password"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // Şimdi login'e tekrar git
    await page.goto("/login");
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
