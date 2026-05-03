import { test, expect } from "@playwright/test";

test.describe("Login akışı", () => {
  test("Geçersiz kullanıcı için hata mesajı göstermeli", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/login/);

    await page.fill('input[type="email"]', "olmayan@example.com");
    await page.fill('input[type="password"]', "yanlis-sifre");
    await page.click('button[type="submit"]');

    // Hata mesajı veya 401 sonrası login sayfasında kalmalı
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test("Token'sız /dashboard erişimi /login'e yönlendirmeli", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("Token'sız /dashboard/crypto erişimi /login'e yönlendirmeli", async ({ page }) => {
    await page.goto("/dashboard/crypto");
    await expect(page).toHaveURL(/\/login/);
  });
});
