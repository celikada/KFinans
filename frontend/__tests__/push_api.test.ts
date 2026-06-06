import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { BASE } from "../lib/api/_client";
import { pushApi } from "../lib/api/push";

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
    new Response(JSON.stringify({ public_key: "BPubKey", sent: 1 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.restoreAllMocks());

describe("pushApi", () => {
  it("getVapidPublicKey GET", async () => {
    const res = await pushApi.getVapidPublicKey();
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/push/vapid-public-key`);
    expect(init.method ?? "GET").toBe("GET");
    expect(res.public_key).toBe("BPubKey");
  });

  it("subscribePush POST + body", async () => {
    fetchMock.mockResolvedValue(
      new Response("{}", { status: 201, headers: { "Content-Type": "application/json" } }),
    );
    await pushApi.subscribePush({
      endpoint: "https://push.example/abc",
      keys: { p256dh: "p", auth: "a" },
      user_agent: "UA",
    });
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/push/subscribe`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      endpoint: "https://push.example/abc",
      keys: { p256dh: "p", auth: "a" },
      user_agent: "UA",
    });
  });

  it("unsubscribePush POST + endpoint body", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await pushApi.unsubscribePush("https://push.example/abc");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/push/unsubscribe`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"endpoint":"https://push.example/abc"}');
  });

  it("sendTestPush POST → sent", async () => {
    const res = await pushApi.sendTestPush();
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/push/test`);
    expect(init.method).toBe("POST");
    expect(res.sent).toBe(1);
  });
});
