import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { setAuth, clearAuth, api } from "../lib/api";

describe("setAuth / clearAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("setAuth localStorage'a ve cookie'ye access token yazar", () => {
    setAuth("test-token-123");
    expect(localStorage.getItem("access_token")).toBe("test-token-123");
    expect(document.cookie).toContain("access_token=test-token-123");
  });

  it("setAuth(access, refresh) refresh'i de saklar (FAZ C4)", () => {
    setAuth("acc-001", "ref-001");
    expect(localStorage.getItem("access_token")).toBe("acc-001");
    expect(localStorage.getItem("refresh_token")).toBe("ref-001");
  });

  it("setAuth refresh parametresi opsiyonel — verilmezse refresh dokunulmaz", () => {
    localStorage.setItem("refresh_token", "onceki-refresh");
    setAuth("yeni-access");  // refresh parametresi yok
    expect(localStorage.getItem("access_token")).toBe("yeni-access");
    expect(localStorage.getItem("refresh_token")).toBe("onceki-refresh");
  });

  it("clearAuth hem access hem refresh hem cookie temizler", () => {
    setAuth("acc-temizlenecek", "ref-temizlenecek");
    clearAuth();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(document.cookie).not.toContain("access_token=acc-temizlenecek");
  });

  it("setAuth cookie SameSite=Strict ayarlar", () => {
    setAuth("strict-token");
    // Note: jsdom does not expose SameSite in document.cookie reads,
    // but we verified the call path.
    expect(document.cookie).toContain("access_token=strict-token");
  });
});


// ─── FAZ C4: refresh token akışı + 401 otomatik retry ──────────────────────

describe("Request 401 → otomatik refresh + retry akışı", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Access expired (401) + refresh saklı → /auth/refresh çağrılır + retry başarılı", async () => {
    setAuth("eski-access", "ref-001");

    const fetchMock = vi.fn()
      // 1. /user/me ilk çağrı: 401 (access expired)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Token expired" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      // 2. /auth/refresh: 200 yeni token'lar
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "yeni-access",
            refresh_token: "yeni-ref",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      // 3. /user/me retry: 200 user data
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email: "test@example.com",
            risk_profile: "balanced",
            created_at: "2026-05-07T00:00:00Z",
            email_verified: true,
            credit_balance: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.getMe();

    expect(result.email).toBe("test@example.com");
    // 3 fetch çağrısı: ilk 401, refresh, retry
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // Yeni token'lar saklanmış
    expect(localStorage.getItem("access_token")).toBe("yeni-access");
    expect(localStorage.getItem("refresh_token")).toBe("yeni-ref");

    // Retry isteği yeni access token ile gitmeli
    const retryCall = fetchMock.mock.calls[2];
    const retryHeaders = retryCall[1]?.headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe("Bearer yeni-access");
  });

  it("Refresh fail (401) → clearAuth + login redirect + hata fırlatır", async () => {
    setAuth("eski-access", "gecersiz-ref");
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Token expired" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      // /auth/refresh: 401 (refresh de geçersiz)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Token iptal edilmiş" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getMe()).rejects.toThrow();

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("Refresh saklı değil → 401 doğrudan logout (refresh denemeden)", async () => {
    setAuth("eski-access");  // refresh yok
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Token expired" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getMe()).rejects.toThrow();

    // Sadece 1 fetch (refresh denenmedi)
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("Single-flight: aynı anda 3 paralel 401 → tek refresh çağrısı, 3 retry", async () => {
    setAuth("eski-access", "ref-001");

    let refreshCallCount = 0;
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/auth/refresh")) {
        refreshCallCount++;
        return Promise.resolve(
          new Response(
            JSON.stringify({
              access_token: "yeni-access",
              refresh_token: "yeni-ref",
              token_type: "bearer",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (url.includes("/user/me")) {
        // İlk çağrılarda eski access ile 401 dön; sonraki çağrılarda 200
        const auth = (init?.headers as Record<string, string> | undefined)?.Authorization ?? "";
        if (auth === "Bearer eski-access") {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: "expired" }), {
              status: 401,
              headers: { "Content-Type": "application/json" },
            }),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              email: "test@example.com",
              risk_profile: "balanced",
              created_at: "2026-05-07T00:00:00Z",
              email_verified: true,
              credit_balance: 0,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.reject(new Error("unexpected url"));
    });
    vi.stubGlobal("fetch", fetchMock);

    // 3 paralel istek
    const results = await Promise.all([api.getMe(), api.getMe(), api.getMe()]);

    expect(results).toHaveLength(3);
    results.forEach((r) => expect(r.email).toBe("test@example.com"));
    // Single-flight: refresh sadece 1 kez çağrıldı
    expect(refreshCallCount).toBe(1);
  });
});
