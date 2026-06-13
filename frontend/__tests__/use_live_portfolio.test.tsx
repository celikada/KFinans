import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";

// ─── API mock ────────────────────────────────────────────────────────────────
const apiFns = vi.hoisted(() => ({
  getLivePortfolio: vi.fn(),
  refreshPortfolio: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: new Proxy(apiFns, {
    get: (target, prop: string) => target[prop as keyof typeof target],
  }),
}));

import { useLivePortfolio } from "@/app/_hooks/useLivePortfolio";

function okLive(overrides: Record<string, unknown> = {}) {
  return {
    status: "ok",
    refreshed_at: "2026-06-13T10:00:00Z",
    stale: false,
    total_value_tl: "100",
    rates: null,
    health_issues: [],
    error: null,
    sections: { wallets: { positions: [{ symbol: "BTC", total_value_tl: "100" }], errors: {} } },
    ...overrides,
  };
}

// Hook'u DOM'a yansıtan minik test bileşeni.
function Harness() {
  const { data, loading, refreshing, error, refresh } = useLivePortfolio();
  return (
    <div>
      <span data-testid="status">{data?.status ?? "—"}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="refreshing">{String(refreshing)}</span>
      <span data-testid="error">{error}</span>
      <span data-testid="wallet-count">{data?.sections.wallets?.positions?.length ?? 0}</span>
      <button onClick={() => refresh()}>refresh</button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useLivePortfolio", () => {
  it("mount'ta getLivePortfolio okur ve veriyi açar (status ok → poll yok)", async () => {
    apiFns.getLivePortfolio.mockResolvedValue(okLive());

    render(<Harness />);

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ok"));
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("refreshing").textContent).toBe("false");
    expect(screen.getByTestId("wallet-count").textContent).toBe("1");
    // status ok → tek okuma yeterli.
    expect(apiFns.getLivePortfolio).toHaveBeenCalledTimes(1);
  });

  it("status=refreshing → poll eder; sonradan ok olunca durur", async () => {
    vi.useFakeTimers();
    apiFns.getLivePortfolio
      .mockResolvedValueOnce(okLive({ status: "refreshing" }))
      .mockResolvedValue(okLive({ status: "ok" }));

    render(<Harness />);

    // İlk okuma (microtask) → refreshing.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId("status").textContent).toBe("refreshing");
    expect(screen.getByTestId("refreshing").textContent).toBe("true");

    // Poll aralığını ilerlet → ikinci okuma "ok" döner, poll durur.
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByTestId("status").textContent).toBe("ok");
    expect(screen.getByTestId("refreshing").textContent).toBe("false");
    expect(apiFns.getLivePortfolio).toHaveBeenCalledTimes(2);
  });

  it("okuma hatası → error set edilir, loading kapanır", async () => {
    apiFns.getLivePortfolio.mockRejectedValue(new Error("ağ koptu"));

    render(<Harness />);

    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("ağ koptu"));
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("refresh() → refreshPortfolio(force) + yeniden okuma", async () => {
    apiFns.getLivePortfolio.mockResolvedValue(okLive());
    apiFns.refreshPortfolio.mockResolvedValue({ status: "ok", refreshed_at: "x" });

    render(<Harness />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ok"));

    await act(async () => {
      screen.getByText("refresh").click();
    });

    await waitFor(() => expect(apiFns.refreshPortfolio).toHaveBeenCalledWith(true));
    // refresh içinde tekrar okuma yapılır (mount + refresh = en az 2).
    expect(apiFns.getLivePortfolio.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
