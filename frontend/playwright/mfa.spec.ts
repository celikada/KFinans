import { test, expect, type Page } from "@playwright/test";

// Bu testler backend MFA endpoint'lerini mock'lar (page.route).
// Backend agent paralelde MFA implementasyonu yaziyor — test'in calismasi
// icin backend'in canli olmasi zorunlu degil. Frontend UI akisinin
// dogru oldugunu kanitlamayi amaclar.

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
) + "/api/v1";

const FAKE_QR = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII=";
const FAKE_SECRET = "JBSWY3DPEHPK3PXP";
const FAKE_OTPAUTH = `otpauth://totp/KFinans:test?secret=${FAKE_SECRET}&issuer=KFinans`;
const RECOVERY = [
  "abcd-1111", "abcd-2222", "abcd-3333", "abcd-4444", "abcd-5555",
  "abcd-6666", "abcd-7777", "abcd-8888", "abcd-9999", "abcd-0000",
];

async function setAuthCookieAndStorage(page: Page) {
  // Dashboard'a girebilmek icin proxy.ts cookie istiyor + lib/api.ts localStorage.
  await page.context().addCookies([
    {
      name: "access_token",
      value: "fake-access-token",
      url: "http://localhost:3000",
      sameSite: "Strict",
    },
  ]);
  await page.addInitScript(() => {
    window.localStorage.setItem("access_token", "fake-access-token");
    window.localStorage.setItem("refresh_token", "fake-refresh-token");
  });
}

test.describe("MFA UI akisi (mock backend)", () => {
  test("Login → MFA challenge → 6-digit doğrula → dashboard", async ({ page }) => {
    // Login: backend MFA gerektiriyor diye don
    await page.route(`${API_BASE}/auth/login`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          mfa_required: true,
          pre_mfa_token: "pre-mfa-token-xyz",
        }),
      });
    });
    // mfa/verify: dogru kod gelince tokenlari don
    await page.route(`${API_BASE}/mfa/verify`, async (route) => {
      const post = route.request().postDataJSON();
      if (post?.totp_code === "123456") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            access_token: "real-access",
            refresh_token: "real-refresh",
            token_type: "bearer",
          }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid code" }),
        });
      }
    });
    // Dashboard yuklenmesi icin /user/me ve diger cagrilari da pasif olarak mock'la
    await page.route(/\/api\/v1\/.*/, async (route) => {
      const url = route.request().url();
      if (url.includes("/auth/login") || url.includes("/mfa/verify")) {
        // yukarida zaten yakalandi
        return route.fallback();
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await page.goto("/login");
    await page.fill('input[type="email"]', "mfa@test.com");
    await page.fill('input[type="password"]', "Strong123!");
    await page.click('button[type="submit"]');

    // MFA challenge formu acilmali
    await expect(page.getByTestId("mfa-challenge-form")).toBeVisible();
    await page.getByTestId("mfa-login-code").fill("123456");
    await page.getByTestId("mfa-login-submit").click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 });
  });

  test("Login → MFA challenge → yanlış kod → hata göster", async ({ page }) => {
    await page.route(`${API_BASE}/auth/login`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          mfa_required: true,
          pre_mfa_token: "pre-mfa-token-xyz",
        }),
      });
    });
    await page.route(`${API_BASE}/mfa/verify`, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid MFA code" }),
      });
    });

    await page.goto("/login");
    await page.fill('input[type="email"]', "mfa@test.com");
    await page.fill('input[type="password"]', "Strong123!");
    await page.click('button[type="submit"]');

    await expect(page.getByTestId("mfa-challenge-form")).toBeVisible();
    await page.getByTestId("mfa-login-code").fill("999999");
    await page.getByTestId("mfa-login-submit").click();

    await expect(page.locator('[role="alert"]')).toContainText(/Invalid|MFA|kod/i);
    // Hala MFA ekraninda kal
    await expect(page.getByTestId("mfa-challenge-form")).toBeVisible();
  });

  test("Login → MFA challenge → recovery moduna geçiş", async ({ page }) => {
    await page.route(`${API_BASE}/auth/login`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          mfa_required: true,
          pre_mfa_token: "pre-mfa-token-xyz",
        }),
      });
    });
    await page.route(`${API_BASE}/mfa/verify`, async (route) => {
      const post = route.request().postDataJSON();
      if (post?.recovery_code === "abcd-1111") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            access_token: "real-access",
            refresh_token: "real-refresh",
            token_type: "bearer",
          }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid recovery code" }),
        });
      }
    });
    await page.route(/\/api\/v1\/.*/, async (route) => {
      const url = route.request().url();
      if (url.includes("/auth/login") || url.includes("/mfa/verify")) {
        return route.fallback();
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await page.goto("/login");
    await page.fill('input[type="email"]', "mfa@test.com");
    await page.fill('input[type="password"]', "Strong123!");
    await page.click('button[type="submit"]');

    await expect(page.getByTestId("mfa-challenge-form")).toBeVisible();
    await page.getByTestId("mfa-login-toggle-mode").click();
    await page.getByTestId("mfa-login-recovery").fill("abcd-1111");
    await page.getByTestId("mfa-login-submit").click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 });
  });

  test("Settings/security: MFA kurulum (setup → QR → enable → recovery codes)", async ({
    page,
  }) => {
    await setAuthCookieAndStorage(page);

    let setupCalled = false;
    let enableCalled = false;

    await page.route(`${API_BASE}/mfa/status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ mfa_enabled: false }),
      });
    });
    await page.route(`${API_BASE}/mfa/setup`, async (route) => {
      setupCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          secret_base32: FAKE_SECRET,
          otpauth_url: FAKE_OTPAUTH,
          qr_png_base64: FAKE_QR,
        }),
      });
    });
    await page.route(`${API_BASE}/mfa/enable`, async (route) => {
      enableCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ recovery_codes: RECOVERY }),
      });
    });
    // Diger API cagrilari icin pasif yanit
    await page.route(/\/api\/v1\/.*/, async (route) => {
      const url = route.request().url();
      if (
        url.includes("/mfa/status") ||
        url.includes("/mfa/setup") ||
        url.includes("/mfa/enable")
      ) {
        return route.fallback();
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await page.goto("/dashboard/settings/security");

    // Initial state: setup butonu gorunmeli
    await expect(page.getByTestId("mfa-setup-btn")).toBeVisible();
    await page.getByTestId("mfa-setup-btn").click();

    // QR + secret + code input gorunmeli
    await expect(page.getByTestId("mfa-setup-panel")).toBeVisible();
    await expect(page.getByTestId("mfa-qr-image")).toBeVisible();
    await expect(page.getByTestId("mfa-secret")).toContainText(FAKE_SECRET);
    expect(setupCalled).toBe(true);

    // 6-digit kodu doğrula
    await page.getByTestId("mfa-setup-code").fill("123456");
    await page.getByTestId("mfa-enable-btn").click();

    // Recovery codes panel gorunmeli
    await expect(page.getByTestId("mfa-recovery-panel")).toBeVisible();
    const list = page.getByTestId("mfa-recovery-list");
    await expect(list).toContainText("abcd-1111");
    await expect(list).toContainText("abcd-0000");
    expect(enableCalled).toBe(true);

    // "Kaydettim" butonu kapatabilmeli
    await page.getByTestId("mfa-recovery-saved-btn").click();
    await expect(page.locator('[role="status"]')).toBeVisible();
  });

  test("Settings/security: MFA aktifken Disable formu calismali", async ({
    page,
  }) => {
    await setAuthCookieAndStorage(page);

    await page.route(`${API_BASE}/mfa/status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ mfa_enabled: true }),
      });
    });
    await page.route(`${API_BASE}/mfa/disable`, async (route) => {
      const post = route.request().postDataJSON();
      if (post?.totp_code === "654321") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ detail: "MFA disabled" }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid code" }),
        });
      }
    });
    await page.route(/\/api\/v1\/.*/, async (route) => {
      const url = route.request().url();
      if (url.includes("/mfa/status") || url.includes("/mfa/disable")) {
        return route.fallback();
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await page.goto("/dashboard/settings/security");

    await expect(page.getByTestId("mfa-status-badge")).toContainText(/Aktif|Active/);
    await page.getByTestId("mfa-disable-btn").click();

    await page.getByTestId("mfa-disable-code").fill("654321");
    await page.getByTestId("mfa-disable-confirm-btn").click();

    await expect(page.getByTestId("mfa-status-badge")).toContainText(/Pasif|Inactive/, {
      timeout: 5000,
    });
  });
});
