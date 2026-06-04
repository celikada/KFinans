import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { BASE, setAuth } from "../lib/api/_client";
import { authApi } from "../lib/api/auth";

let fetchMock: ReturnType<typeof vi.fn>;

function lastCall() {
  const calls = fetchMock.mock.calls;
  const [url, init] = calls[calls.length - 1];
  return { url: url as string, init: (init ?? {}) as RequestInit };
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.restoreAllMocks());

describe("authApi temel endpoint'ler", () => {
  it("login POST + body", async () => {
    await authApi.login("a@b.com", "pw");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/auth/login`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"email":"a@b.com","password":"pw"}');
  });

  it("mfaStatus GET", async () => {
    await authApi.mfaStatus();
    expect(lastCall().url).toBe(`${BASE}/mfa/status`);
  });

  it("mfaSetup POST", async () => {
    await authApi.mfaSetup();
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/mfa/setup`);
    expect(init.method).toBe("POST");
  });

  it("mfaEnable POST + totp body", async () => {
    await authApi.mfaEnable("123456");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/mfa/enable`);
    expect(init.body).toBe('{"totp_code":"123456"}');
  });

  it("mfaDisable POST + totp body", async () => {
    await authApi.mfaDisable("123456");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/mfa/disable`);
    expect(init.body).toBe('{"totp_code":"123456"}');
  });

  it("register POST + age_confirmed body (opt-in varsayılan false)", async () => {
    await authApi.register("a@b.com", "pw", "balanced", true);
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/auth/register`);
    expect(init.body).toBe(
      '{"email":"a@b.com","password":"pw","risk_profile":"balanced","age_confirmed":true,"release_notes_opt_in":false}',
    );
  });

  it("register POST + release_notes_opt_in true geçilebilir", async () => {
    await authApi.register("a@b.com", "pw", "balanced", true, true);
    expect(lastCall().init.body).toBe(
      '{"email":"a@b.com","password":"pw","risk_profile":"balanced","age_confirmed":true,"release_notes_opt_in":true}',
    );
  });

  it("verifyEmail GET + encode token", async () => {
    await authApi.verifyEmail("a b/c");
    expect(lastCall().url).toBe(`${BASE}/auth/verify-email?token=a%20b%2Fc`);
  });

  it("resendVerification POST + email body", async () => {
    await authApi.resendVerification("a@b.com");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/auth/resend-verification`);
    expect(init.body).toBe('{"email":"a@b.com"}');
  });
});

describe("authApi.logout refresh token fallback", () => {
  it("parametre verilirse onu kullanır", async () => {
    setAuth("acc", "saklı-ref");
    await authApi.logout("açık-ref");
    expect(lastCall().init.body).toBe('{"refresh_token":"açık-ref"}');
  });

  it("parametre yoksa localStorage refresh'i kullanır", async () => {
    setAuth("acc", "saklı-ref");
    await authApi.logout();
    expect(lastCall().init.body).toBe('{"refresh_token":"saklı-ref"}');
  });

  it("refresh yoksa null gönderir", async () => {
    setAuth("acc");
    await authApi.logout();
    expect(lastCall().init.body).toBe('{"refresh_token":null}');
  });
});

describe("authApi.mfaVerify (raw fetch, pre_mfa_token)", () => {
  it("başarılı → pre_mfa_token Authorization header + payload", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: "a", refresh_token: "r" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await authApi.mfaVerify("PRE-TOKEN", { totp_code: "123456" });

    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/mfa/verify`);
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer PRE-TOKEN");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"totp_code":"123456"}');
    expect((result as { access_token: string }).access_token).toBe("a");
  });

  it("recovery_code payload da geçer", async () => {
    await authApi.mfaVerify("PRE", { recovery_code: "rec-1" });
    expect(lastCall().init.body).toBe('{"recovery_code":"rec-1"}');
  });

  it("!ok + detail → formatErrorDetail ile hata fırlatır", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "geçersiz kod" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(authApi.mfaVerify("PRE", { totp_code: "000000" })).rejects.toThrow("geçersiz kod");
  });

  it("!ok + JSON parse edilemez → statusText", async () => {
    fetchMock.mockResolvedValue(
      new Response("boom", { status: 500, statusText: "Internal Server Error" }),
    );
    await expect(authApi.mfaVerify("PRE", { totp_code: "000000" })).rejects.toThrow(
      "Internal Server Error",
    );
  });
});
