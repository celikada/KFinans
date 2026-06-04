import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { BASE } from "../lib/api/_client";
import { releaseApi } from "../lib/api/release";

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
    new Response(JSON.stringify({ release_notes_opt_in: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.restoreAllMocks());

describe("releaseApi", () => {
  it("getReleaseOptIn GET", async () => {
    await releaseApi.getReleaseOptIn();
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/release-notes/opt-in`);
    expect(init.method ?? "GET").toBe("GET");
  });

  it("setReleaseOptIn PUT + body", async () => {
    const res = await releaseApi.setReleaseOptIn(true);
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/release-notes/opt-in`);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe('{"opt_in":true}');
    expect(res.release_notes_opt_in).toBe(true);
  });

  it("sendReleaseNotes POST + version body", async () => {
    await releaseApi.sendReleaseNotes("0.2.0");
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE}/release-notes/send`);
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"version":"0.2.0"}');
  });

  it("unsubscribe GET + encode token, ok → true", async () => {
    const ok = await releaseApi.unsubscribe("tok en/123");
    expect(lastCall().url).toBe(`${BASE}/release-notes/unsubscribe?token=tok%20en%2F123`);
    expect(ok).toBe(true);
  });

  it("unsubscribe !ok → false", async () => {
    fetchMock.mockResolvedValue(new Response("nope", { status: 404 }));
    const ok = await releaseApi.unsubscribe("bad");
    expect(ok).toBe(false);
  });
});
