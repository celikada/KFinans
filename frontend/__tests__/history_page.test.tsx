import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
const replaceMock = vi.fn();
const pushMock = vi.fn();
// STABIL router — handle401 = useCallback([router]); yeni referans effect'i tetikler.
const routerStub = { replace: replaceMock, push: pushMock, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

// STABIL i18n objesi — useTranslation her render'da yeni `t` referansi dönerse
// useEffect([..., t]) sonsuz tekrar fetch eder ve points state'ini ezer.
const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));

vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl, className }: { tl: number; className?: string }) => (
    <span data-testid="tl-value" className={className}>{String(tl)}</span>
  ),
}));

// recharts → jsdom'da chart render etmesin (sade pass-through / null).
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}));

const getPortfolioHistory = vi.fn();
const getPortfolioHistoryYears = vi.fn();
const deleteSnapshot = vi.fn();
const downloadReport = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getPortfolioHistory: (...a: unknown[]) => getPortfolioHistory(...a),
    getPortfolioHistoryYears: (...a: unknown[]) => getPortfolioHistoryYears(...a),
    deleteSnapshot: (...a: unknown[]) => deleteSnapshot(...a),
    downloadReport: (...a: unknown[]) => downloadReport(...a),
  },
}));

import HistoryPage from "@/app/dashboard/history/page";

function snapshot(date: string, total: string, opts: {
  rate?: string | null;
  issues?: Array<{ source: string; code: string; msg: string; level?: "warn" | "info"; symbol?: string }>;
  positions?: Array<{ asset_type: string; total_value_tl: string }>;
} = {}) {
  return {
    id: `id-${date}`,
    snapshot_date: date,
    total_value_tl: total,
    usd_try_rate: opts.rate === undefined ? "40" : opts.rate,
    health_issues: opts.issues ?? [],
    asset_positions: (opts.positions ?? []).map((p, i) => ({
      id: `p-${i}`,
      asset_type: p.asset_type,
      provider: "x",
      symbol: "S",
      name: "N",
      total_value_tl: p.total_value_tl,
      weight_pct: "0",
    })),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getPortfolioHistory.mockResolvedValue([]);
  getPortfolioHistoryYears.mockResolvedValue([]);
  deleteSnapshot.mockResolvedValue(undefined);
  downloadReport.mockResolvedValue(undefined);
});

describe("HistoryPage — yukleme + bos durum", () => {
  it("yuklenirken loading, sonra snapshot yoksa bos durum metni", async () => {
    let resolve!: (v: unknown[]) => void;
    getPortfolioHistory.mockImplementation(() => new Promise((r) => { resolve = r; }));
    render(<HistoryPage />);

    expect(screen.getByText("content.history.loading")).toBeInTheDocument();
    resolve([]);

    expect(await screen.findByText("content.history.noSnapshotTitle")).toBeInTheDocument();
  });

  it("load 401 → login'e yonlendirir", async () => {
    getPortfolioHistory.mockRejectedValue(new Error("Request failed 401"));
    render(<HistoryPage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("load 401 disi hata → hata mesaji", async () => {
    getPortfolioHistory.mockRejectedValue(new Error("500 boom"));
    render(<HistoryPage />);
    expect(await screen.findByText("500 boom")).toBeInTheDocument();
  });

  it("load Error olmayan deger → fallback mesaj", async () => {
    getPortfolioHistory.mockRejectedValue("oops");
    render(<HistoryPage />);
    expect(await screen.findByText("content.history.loadFailed")).toBeInTheDocument();
  });

  it("geri butonu /dashboard'a push eder", async () => {
    render(<HistoryPage />);
    expect(await screen.findByText("content.history.noSnapshotTitle")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "common.back" }));
    expect(pushMock).toHaveBeenCalledWith("/dashboard");
  });
});

describe("HistoryPage — snapshot listesi + grafikler", () => {
  const DATA = [
    snapshot("2026-01-15", "100000", {
      rate: "40",
      positions: [
        { asset_type: "crypto", total_value_tl: "60000" },
        { asset_type: "fund", total_value_tl: "40000" },
      ],
    }),
    snapshot("2026-02-15", "120000", {
      rate: "42",
      positions: [{ asset_type: "stock", total_value_tl: "120000" }],
    }),
  ];

  it("snapshot'lar yuklenir → son snapshot karti + liste + grafikler", async () => {
    getPortfolioHistory.mockResolvedValue([...DATA].reverse()); // siralama testi
    render(<HistoryPage />);

    await waitFor(() =>
      expect(screen.queryByText("content.history.loading")).not.toBeInTheDocument(),
    );
    // Son snapshot karti (TRY varsayilan → TLValue). Metin "(...)" ile bolundugu
    // icin esnek matcher kullan.
    expect(
      screen.getByText((c) => c.startsWith("content.history.lastSnapshot")),
    ).toBeInTheDocument();
    // Iki grafik render edilir.
    expect(screen.getAllByTestId("line-chart")).toHaveLength(2);
    // Liste 2 satir.
    expect(screen.getByText("content.history.snapshots")).toBeInTheDocument();
    // Sayim ifadesi.
    expect(screen.getByText(/content.history.lastCountPre/)).toBeInTheDocument();
  });

  it("TL/USD toggle → USD'ye gecince son snapshot $ degeri gosterir", async () => {
    getPortfolioHistory.mockResolvedValue(DATA);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.queryByText("content.history.loading")).not.toBeInTheDocument(),
    );
    const user = userEvent.setup();

    // TRY modunda TLValue var.
    expect(screen.getByTestId("tl-value")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "content.history.usdToggle" }));
    // USD modunda son snapshot: 120000 / 42 ≈ 2857 → "$2,857". Hem ozet kartta hem
    // liste satirinda gecebilir; en az birini bekle.
    const usdMatches = await screen.findAllByText(/\$2,857/);
    expect(usdMatches.length).toBeGreaterThan(0);
    // TLValue (TRY karti) artik yok.
    expect(screen.queryByTestId("tl-value")).not.toBeInTheDocument();

    // Geri TRY'ye don.
    await user.click(screen.getByRole("button", { name: "content.history.tlToggle" }));
    expect(await screen.findByTestId("tl-value")).toBeInTheDocument();
  });

  it("USD modunda rate'i olmayan son snapshot → em-dash (—)", async () => {
    getPortfolioHistory.mockResolvedValue([snapshot("2026-03-01", "5000", { rate: null })]);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.queryByText("content.history.loading")).not.toBeInTheDocument(),
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "content.history.usdToggle" }));
    expect(await screen.findByText("—")).toBeInTheDocument();
  });
});

describe("HistoryPage — yil filtresi", () => {
  it("availableYears varsa secici gorunur + secim getPortfolioHistory'yi year ile cagirir", async () => {
    getPortfolioHistoryYears.mockResolvedValue([2025, 2026]);
    getPortfolioHistory.mockResolvedValue([snapshot("2026-01-01", "1000")]);
    render(<HistoryPage />);

    const select = await screen.findByLabelText("content.history.yearFilterAria");
    expect(select).toBeInTheDocument();
    // Ilk cagri "all" (year param yok).
    await waitFor(() => expect(getPortfolioHistory).toHaveBeenCalled());

    fireEvent.change(select, { target: { value: "2025" } });
    await waitFor(() =>
      expect(getPortfolioHistory).toHaveBeenLastCalledWith({ limit: 365, year: 2025 }),
    );

    // Tekrar "all" → year param kalkar.
    fireEvent.change(select, { target: { value: "all" } });
    await waitFor(() =>
      expect(getPortfolioHistory).toHaveBeenLastCalledWith({ limit: 365 }),
    );
  });

  it("getPortfolioHistoryYears fail → secici cizilmez (sessiz catch)", async () => {
    getPortfolioHistoryYears.mockRejectedValue(new Error("yil hatasi"));
    getPortfolioHistory.mockResolvedValue([]);
    render(<HistoryPage />);
    expect(await screen.findByText("content.history.noSnapshotTitle")).toBeInTheDocument();
    expect(screen.queryByLabelText("content.history.yearFilterAria")).not.toBeInTheDocument();
  });
});

describe("HistoryPage — rapor indirme", () => {
  it("xlsx + pdf butonlari downloadReport'u dogru path/filename ile cagirir", async () => {
    getPortfolioHistory.mockResolvedValue([snapshot("2026-05-04", "1000")]);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.queryByText("content.history.loading")).not.toBeInTheDocument(),
    );
    const user = userEvent.setup();

    await user.click(screen.getByTitle("content.history.xlsxTitle"));
    expect(downloadReport).toHaveBeenCalledWith(
      "/portfolio/snapshot/2026-05-04/report.xlsx",
      "portfoy-2026-05-04.xlsx",
    );

    await user.click(screen.getByTitle("content.history.pdfTitle"));
    expect(downloadReport).toHaveBeenCalledWith(
      "/portfolio/snapshot/2026-05-04/report.pdf",
      "portfoy-2026-05-04.pdf",
    );
  });
});

describe("HistoryPage — snapshot silme", () => {
  async function renderWithRow() {
    getPortfolioHistory.mockResolvedValue([snapshot("2026-04-20", "9999")]);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.queryByText("content.history.loading")).not.toBeInTheDocument(),
    );
    return userEvent.setup();
  }

  it("sil → onay dialogu acilir, iptal kapatir", async () => {
    const user = await renderWithRow();
    await user.click(screen.getByRole("button", { name: "content.history.deleteBtn" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("content.history.deleteConfirmTitle")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "common.cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(deleteSnapshot).not.toHaveBeenCalled();
  });

  it("onayla → deleteSnapshot cagrilir + satir listeden kalkar", async () => {
    const user = await renderWithRow();
    await user.click(screen.getByRole("button", { name: "content.history.deleteBtn" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "content.history.confirmDeleteBtn" }));

    await waitFor(() => expect(deleteSnapshot).toHaveBeenCalledWith("2026-04-20"));
    // Tum noktalar silindi → liste satiri (sil butonu) kalkar + bos durum gelir.
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "content.history.deleteBtn" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText("content.history.noSnapshotTitle")).toBeInTheDocument();
  });

  it("delete hata → hata mesaji, dialog kapanir", async () => {
    deleteSnapshot.mockRejectedValue(new Error("silme reddedildi"));
    const user = await renderWithRow();
    await user.click(screen.getByRole("button", { name: "content.history.deleteBtn" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "content.history.confirmDeleteBtn" }));

    expect(await screen.findByText("silme reddedildi")).toBeInTheDocument();
  });

  it("backdrop tiklamasi dialogu kapatir", async () => {
    const user = await renderWithRow();
    await user.click(screen.getByRole("button", { name: "content.history.deleteBtn" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    // Backdrop artik native <button> (aria-label=common.close); tiklayinca kapatir.
    fireEvent.click(screen.getByRole("button", { name: "common.close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("HistoryPage — saglik uyarilari (issues)", () => {
  const ISSUE_DATA = [
    snapshot("2026-06-01", "1000", {
      issues: [
        { source: "binance", code: "PRICE_MISSING", msg: "fiyat yok", level: "warn", symbol: "ETH" },
        { source: "info-src", code: "INFO_X", msg: "bilgi notu", level: "info" },
      ],
    }),
  ];

  it("issue'lu snapshot → rozet listesi gorunur, rozet tiklayinca popup acilir", async () => {
    getPortfolioHistory.mockResolvedValue(ISSUE_DATA);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.queryByText("content.history.problematicSnapshots")).toBeInTheDocument(),
    );
    const user = userEvent.setup();

    // Rozet bloku basligin altinda gorunur.
    expect(screen.getByText("content.history.problematicSnapshots")).toBeInTheDocument();

    // Listedeki ! butonu (title ile) ile popup ac.
    await user.click(screen.getByTitle(/content.history.warningCountTitle/));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("fiyat yok")).toBeInTheDocument();
    expect(within(dialog).getByText("bilgi notu")).toBeInTheDocument();
    // warn + info ozet etiketleri.
    expect(within(dialog).getByText(/content.history.problemsLabel/)).toBeInTheDocument();
    expect(within(dialog).getByText(/content.history.infoLabel/)).toBeInTheDocument();

    // Kapat butonu.
    await user.click(within(dialog).getByRole("button", { name: "content.history.close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("rozet (problematicSnapshots bloku) tiklamasi da popup acar", async () => {
    getPortfolioHistory.mockResolvedValue(ISSUE_DATA);
    render(<HistoryPage />);
    await waitFor(() =>
      expect(screen.getByText("content.history.problematicSnapshots")).toBeInTheDocument(),
    );
    const user = userEvent.setup();

    // Rozet butonu: tarih · adet metni iceren amber buton.
    const badges = screen.getAllByRole("button").filter((b) => /·\s*2/.test(b.textContent ?? ""));
    expect(badges.length).toBeGreaterThan(0);
    await user.click(badges[0]);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
