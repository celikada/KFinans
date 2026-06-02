import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import {
  BASE,
  setAuth,
  getAccessToken,
  getRefreshToken,
  formatErrorDetail,
  request,
  authedFetch,
  downloadBlob,
  uploadForm,
} from "../lib/api/_client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("_client token getters", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("getAccessToken / getRefreshToken localStorage'dan okur", () => {
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    setAuth("acc-1", "ref-1");
    expect(getAccessToken()).toBe("acc-1");
    expect(getRefreshToken()).toBe("ref-1");
  });
});

describe("formatErrorDetail tüm dallar", () => {
  it("falsy → boş string", () => {
    expect(formatErrorDetail(null)).toBe("");
    expect(formatErrorDetail(undefined)).toBe("");
    expect(formatErrorDetail("")).toBe("");
  });

  it("string → aynen döner", () => {
    expect(formatErrorDetail("hata mesajı")).toBe("hata mesajı");
  });

  it("array of strings → ' · ' ile birleşir", () => {
    expect(formatErrorDetail(["a", "b"])).toBe("a · b");
  });

  it("array of Pydantic loc/msg objeleri → loc: msg", () => {
    const detail = [
      { loc: ["body", "email"], msg: "field required" },
      { loc: ["body", "password"], msg: "too short" },
    ];
    expect(formatErrorDetail(detail)).toBe("body.email: field required · body.password: too short");
  });

  it("array of msg objesi (loc yok) → sadece msg", () => {
    expect(formatErrorDetail([{ msg: "sadece mesaj" }])).toBe("sadece mesaj");
  });

  it("array of msg objesi (loc array değil) → sadece msg", () => {
    expect(formatErrorDetail([{ msg: "loc string", loc: "body" as unknown as unknown[] }])).toBe("loc string");
  });

  it("array of bilinmeyen obje (msg yok) → JSON.stringify", () => {
    expect(formatErrorDetail([{ code: 42 }])).toBe('{"code":42}');
  });

  it("düz obje → JSON.stringify", () => {
    expect(formatErrorDetail({ detail: "x" })).toBe('{"detail":"x"}');
  });

  it("primitif number → String", () => {
    expect(formatErrorDetail(42)).toBe("42");
  });
});

describe("request() temel akışlar", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("token varsa Authorization header eklenir + JSON döner", async () => {
    setAuth("acc-xyz");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await request<{ ok: boolean }>("/test");

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/test`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer acc-xyz");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("token yoksa Authorization header eklenmez", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await request("/test");

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("options.method + body geçirilir", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await request("/items", { method: "POST", body: JSON.stringify({ a: 1 }) });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
  });

  it("204 No Content → undefined döner", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await request("/items/1", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("!ok (400) + detail string → Error fırlatır", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "geçersiz istek" }, 400));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/items")).rejects.toThrow("geçersiz istek");
  });

  it("!ok + JSON parse edilemez → statusText kullanır", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("not json", { status: 500, statusText: "Internal Server Error" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/items")).rejects.toThrow("Internal Server Error");
  });

  it("!ok + detail array (Pydantic) → formatlanmış mesaj", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ detail: [{ loc: ["body", "x"], msg: "required" }] }, 422),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/items")).rejects.toThrow("body.x: required");
  });

  it("/auth/refresh path'inde 401 retry yapılmaz → doğrudan hata", async () => {
    setAuth("acc", "ref");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "bad" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/auth/refresh", { method: "POST" })).rejects.toThrow("bad");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("request() 401 → refresh + retry (tryRefresh kapsamı)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("401 + refresh saklı → /auth/refresh çağrılır, yeni token ile retry", async () => {
    setAuth("eski-acc", "ref-1");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "yeni-acc", refresh_token: "yeni-ref" }))
      .mockResolvedValueOnce(jsonResponse({ data: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await request<{ data: string }>("/protected");

    expect(result).toEqual({ data: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // refresh çağrısı doğru body ile
    const refreshCall = fetchMock.mock.calls[1];
    expect(refreshCall[0]).toContain("/auth/refresh");
    expect(refreshCall[1].body).toBe('{"refresh_token":"ref-1"}');
    // yeni token'lar saklandı
    expect(localStorage.getItem("access_token")).toBe("yeni-acc");
    expect(localStorage.getItem("refresh_token")).toBe("yeni-ref");
    // retry yeni access token ile
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe("Bearer yeni-acc");
  });

  it("401 + refresh fail (!ok) → clearAuth + /login redirect + hata", async () => {
    setAuth("eski-acc", "gecersiz-ref");
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: "revoked" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/protected")).rejects.toThrow("Oturum süresi doldu");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("401 + refresh fetch throw → tryRefresh catch null → logout", async () => {
    setAuth("eski-acc", "ref-1");
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockRejectedValueOnce(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/protected")).rejects.toThrow("Oturum süresi doldu");
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("401 + refresh token yok → refresh denemeden logout", async () => {
    setAuth("eski-acc"); // refresh yok
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/protected")).rejects.toThrow("Oturum süresi doldu");
    expect(fetchMock).toHaveBeenCalledTimes(1); // refresh denenmedi
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("single-flight: 3 paralel 401 → tek refresh çağrısı", async () => {
    setAuth("eski-acc", "ref-1");
    let refreshCount = 0;
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/auth/refresh")) {
        refreshCount++;
        return Promise.resolve(jsonResponse({ access_token: "yeni-acc", refresh_token: "yeni-ref" }));
      }
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization ?? "";
      if (auth === "Bearer eski-acc") return Promise.resolve(jsonResponse({ detail: "expired" }, 401));
      return Promise.resolve(jsonResponse({ ok: true }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const results = await Promise.all([request("/a"), request("/b"), request("/c")]);
    expect(results).toHaveLength(3);
    expect(refreshCount).toBe(1);
  });
});

describe("authedFetch()", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("token varsa Authorization ekler, Content-Type set etmez", async () => {
    setAuth("acc-af");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await authedFetch("/raw", { method: "POST" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/raw`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer acc-af");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("token yoksa Authorization eklenmez", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await authedFetch("/raw");
    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });
});

describe("downloadBlob()", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("başarılı → blob alır, <a> click eder, URL revoke eder", async () => {
    vi.useFakeTimers();
    const blob = new Blob(["data"], { type: "application/octet-stream" });
    const fetchMock = vi.fn().mockResolvedValue(new Response(blob, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const createObjectURL = vi.fn().mockReturnValue("blob:fake-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const clickMock = vi.fn();
    // saveBlob <a>'yi DOM'a ekler + style ayarlar → stub style/remove icermeli, appendChild no-op.
    const anchor = { href: "", download: "", rel: "", style: {}, click: clickMock, remove: vi.fn() } as unknown as HTMLAnchorElement;
    const createElementSpy = vi.spyOn(document, "createElement").mockReturnValue(anchor);
    vi.spyOn(document.body, "appendChild").mockImplementation((n) => n as unknown as Node);

    await downloadBlob("/export.xlsx", "rapor.xlsx");

    expect(createElementSpy).toHaveBeenCalledWith("a");
    expect(anchor.href).toBe("blob:fake-url");
    expect(anchor.download).toBe("rapor.xlsx");
    expect(clickMock).toHaveBeenCalledOnce();
    // revoke gecikmeli (setTimeout 1.5s) — timer'i ilerlet.
    vi.advanceTimersByTime(1600);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
    vi.useRealTimers();
  });

  it("!ok → 'İndirme başarısız' hatası fırlatır", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(downloadBlob("/export.xlsx", "rapor.xlsx")).rejects.toThrow("İndirme başarısız");
  });
});

describe("uploadForm()", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("başarılı → FormData ile POST, JSON döner", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ imported: 3 }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "data.xlsx");
    const result = await uploadForm<{ imported: number }>("/import", file);

    expect(result).toEqual({ imported: 3 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/import`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("!ok + detail → formatErrorDetail ile hata fırlatır", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "yanlış dosya" }, 422));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "data.xlsx");
    await expect(uploadForm("/import", file)).rejects.toThrow("yanlış dosya");
  });

  it("!ok + JSON parse edilemez → statusText", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("boom", { status: 413, statusText: "Payload Too Large" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "data.xlsx");
    await expect(uploadForm("/import", file)).rejects.toThrow("Payload Too Large");
  });
});
