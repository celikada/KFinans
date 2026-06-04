import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import {
  deriveScope,
  loadCache,
  saveCache,
  clearDashboardCache,
  type DashboardSnapshot,
} from "../lib/dashboardCache";

const PREFIX = "kfinans-dash-v1-";

/** Test amacli minimal JWT uret: header.payload.signature (base64url payload). */
function makeJwt(payload: Record<string, unknown>): string {
  const b64url = (obj: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(obj)).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.sig`;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

// ─── deriveScope ─────────────────────────────────────────────────────────────

describe("deriveScope", () => {
  it("null/gecersiz token → 'anon'", () => {
    expect(deriveScope(null)).toBe("anon");
    expect(deriveScope("")).toBe("anon");
    expect(deriveScope("not-a-jwt")).toBe("anon");
    expect(deriveScope("only.two")).toBe("anon");
  });

  it("sub iceren JWT → deterministik, anon-disi scope", () => {
    const token = makeJwt({ sub: "user-42", exp: 9999999999 });
    const scope = deriveScope(token);
    expect(scope).not.toBe("anon");
    // Deterministik: ayni token → ayni scope
    expect(deriveScope(token)).toBe(scope);
  });

  it("farkli kullanici → farkli scope (izolasyon)", () => {
    const a = deriveScope(makeJwt({ sub: "alice@example.com" }));
    const b = deriveScope(makeJwt({ sub: "bob@example.com" }));
    expect(a).not.toBe(b);
  });

  it("sub PII ham olarak scope'a sizmaz (hash'lenir)", () => {
    const email = "secret@example.com";
    const scope = deriveScope(makeJwt({ sub: email }));
    expect(scope).not.toContain(email);
    expect(scope).not.toContain("secret");
  });

  it("sub yoksa → 'anon'", () => {
    expect(deriveScope(makeJwt({ exp: 123 }))).toBe("anon");
  });
});

// ─── saveCache / loadCache ───────────────────────────────────────────────────

describe("saveCache / loadCache", () => {
  it("kaydedilen kismi degerler aynen yuklenir", () => {
    saveCache("scopeA", { cryptoTotal: 1234.5, cryptoTop: [{ label: "BTC", value: 1000 }] });
    const loaded = loadCache("scopeA");
    expect(loaded).not.toBeNull();
    expect(loaded?.cryptoTotal).toBe(1234.5);
    expect(loaded?.cryptoTop).toEqual([{ label: "BTC", value: 1000 }]);
  });

  it("cache yoksa null doner", () => {
    expect(loadCache("bos-scope")).toBeNull();
  });

  it("ardisik saveCache MERGE eder (eski degerler korunur)", () => {
    saveCache("m", { cryptoTotal: 100 });
    saveCache("m", { stockTotal: 200 });
    const loaded = loadCache("m");
    expect(loaded?.cryptoTotal).toBe(100);
    expect(loaded?.stockTotal).toBe(200);
  });

  it("ayni anahtar tekrar yazilirsa yeni deger kazanir", () => {
    saveCache("m", { cryptoTotal: 100 });
    saveCache("m", { cryptoTotal: 999 });
    expect(loadCache("m")?.cryptoTotal).toBe(999);
  });

  it("farkli scope'lar izole (cross-user leak yok)", () => {
    saveCache("userA", { cryptoTotal: 111 });
    saveCache("userB", { cryptoTotal: 222 });
    expect(loadCache("userA")?.cryptoTotal).toBe(111);
    expect(loadCache("userB")?.cryptoTotal).toBe(222);
  });

  it("scope key prefix'li yazilir", () => {
    saveCache("xyz", { cryptoTotal: 1 });
    expect(localStorage.getItem(`${PREFIX}xyz`)).not.toBeNull();
  });
});

// ─── Bozuk / TTL ─────────────────────────────────────────────────────────────

describe("loadCache dayaniklilik", () => {
  it("bozuk JSON → null (cras etmez)", () => {
    localStorage.setItem(`${PREFIX}corrupt`, "{ not valid json");
    expect(loadCache("corrupt")).toBeNull();
  });

  it("envelope sekli bozuk (savedAt yok) → null", () => {
    localStorage.setItem(`${PREFIX}bad`, JSON.stringify({ data: { cryptoTotal: 1 } }));
    expect(loadCache("bad")).toBeNull();
  });

  it("TTL (24s) gecmis cache → null + temizlenir", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-01T00:00:00Z"));
    saveCache("ttl", { cryptoTotal: 5 });
    // 25 saat ilerlet
    vi.setSystemTime(new Date("2026-06-02T01:00:00Z"));
    expect(loadCache("ttl")).toBeNull();
    expect(localStorage.getItem(`${PREFIX}ttl`)).toBeNull();
  });

  it("TTL icindeki cache → yuklenir", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-01T00:00:00Z"));
    saveCache("fresh", { cryptoTotal: 5 });
    vi.setSystemTime(new Date("2026-06-01T12:00:00Z"));
    expect(loadCache("fresh")?.cryptoTotal).toBe(5);
  });
});

// ─── clearDashboardCache ─────────────────────────────────────────────────────

describe("clearDashboardCache", () => {
  it("tum dashboard cache key'lerini siler", () => {
    saveCache("u1", { cryptoTotal: 1 });
    saveCache("u2", { stockTotal: 2 });
    clearDashboardCache();
    expect(loadCache("u1")).toBeNull();
    expect(loadCache("u2")).toBeNull();
  });

  it("dashboard-disi localStorage anahtarlarina dokunmaz", () => {
    localStorage.setItem("access_token", "tok");
    localStorage.setItem("kfinans_hidden_cards", "[]");
    saveCache("u1", { cryptoTotal: 1 });
    clearDashboardCache();
    expect(localStorage.getItem("access_token")).toBe("tok");
    expect(localStorage.getItem("kfinans_hidden_cards")).toBe("[]");
    expect(loadCache("u1")).toBeNull();
  });
});

// Tip kontrol: DashboardSnapshot alanlari kismi saklanabilir.
describe("DashboardSnapshot tip uyumu", () => {
  it("Partial<DashboardSnapshot> kaydedilebilir", () => {
    const partial: Partial<DashboardSnapshot> = {
      tefasTotal: 1,
      besPlanCount: 2,
      goalPct: 50,
    };
    saveCache("typed", partial);
    expect(loadCache("typed")?.goalPct).toBe(50);
  });
});
