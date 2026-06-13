import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { act, render, screen, waitFor } from "@testing-library/react";

// ─── Mock'lar ──────────────────────────────────────────────────────────────
const replaceMock = vi.fn();
const pushMock = vi.fn();
const routerStub = { replace: replaceMock, push: pushMock, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));
vi.mock("@/app/_i18n/LanguageSwitcher", () => ({
  LanguageSwitcher: () => <div />,
}));
vi.mock("@/app/_components/Logos", () => ({
  KFinansLogo: () => <div />,
  MayotekLogo: () => <div />,
}));
// Modal'lar — render karmaşası olmadan no-op.
vi.mock("@/app/dashboard/_components/SnapshotIssuesModal", () => ({
  SnapshotIssuesModal: () => null,
}));
vi.mock("@/app/dashboard/_components/PendingRealizeModal", () => ({
  PendingRealizeModal: () => null,
}));
vi.mock("@/app/dashboard/_components/CreditCardRemindersModal", () => ({
  CreditCardRemindersModal: () => null,
}));

// Cache her zaman boş (cache hit yolu test edilmiyor; direkt fetch yolu).
vi.mock("@/lib/dashboardCache", () => ({
  deriveScope: () => "test",
  loadCache: () => null,
  saveCache: vi.fn(),
}));

vi.mock("@/lib/api/_client", () => ({
  getAccessToken: () => null,
}));

// TLValue — USD karşılığı kapalı, usdRate sabit.
vi.mock("@/app/_components/TLValue", () => ({
  useUsdRate: () => 35,
  getShowUsd: () => false,
  SHOW_USD_CHANGED_EVENT: "kfinans-show-usd-changed",
}));

// ─── API mock ────────────────────────────────────────────────────────────────
// Finans toplamları için *_display alanları (USD görüntüleme); yatırım için TL.
// vi.hoisted: factory hoisting'inden önce çalışır → mock fn'leri güvenle paylaşılır.
const apiFns = vi.hoisted(() => ({
  // Finans
  getIncomeSummary: vi.fn(),
  getIncomeDashboard: vi.fn(),
  getExpenseSummary: vi.fn(),
  getCashFlow: vi.fn(),
  listCreditCards: vi.fn(),
  getForecast: vi.fn(),
  getBudgetComparison: vi.fn(),
  getGoal: vi.fn(),
  // Yatırım (TL)
  getTefasHoldings: vi.fn(),
  tefasPreview: vi.fn(),
  getCryptoPositions: vi.fn(),
  getStockHoldings: vi.fn(),
  stockPreview: vi.fn(),
  getWalletPositions: vi.fn(),
  getBesHoldings: vi.fn(),
  getCommodities: vi.fn(),
  listCash: vi.fn(),
  listManualCrypto: vi.fn(),
  // Popup'lar
  getPendingRealizations: vi.fn(),
  getCreditCardReminders: vi.fn(),
  // Money/rates
  getRates: vi.fn(),
  // Sunucu-cache canlı portföy (ağır kartlar)
  getLivePortfolio: vi.fn(),
  refreshPortfolio: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: new Proxy(apiFns, {
    get: (target, prop: string) => target[prop as keyof typeof target],
  }),
  clearAuth: vi.fn(),
  EXPENSE_CATEGORY_LABELS: {},
  INCOME_CATEGORY_LABELS: {},
}));

import DashboardPage from "@/app/dashboard/page";
import { DISPLAY_CURRENCY_CHANGED } from "@/lib/defaultCurrency";

const now = new Date();
const YYYY = now.getFullYear();
const MM = now.getMonth() + 1;

function emptyCashFlowYear(year: number) {
  const months = Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    income_actual: "0", income_forecast: "0", expense_actual: "0", expense_forecast: "0",
    income_total: "0", expense_total: "0", net: "0", is_past: i + 1 < MM,
    income_total_display: "0", expense_total_display: "0", net_display: "0",
    income_actual_display: "0", income_forecast_display: "0",
    expense_actual_display: "0", expense_forecast_display: "0",
  }));
  // Bu ay net_display = 250 USD (TL'de 8750 olurdu — round-trip kontrolü).
  const cur = months.find((m) => m.month === MM)!;
  cur.net = "8750";
  cur.net_display = "250";
  return {
    year, months,
    total_income: "0", total_expense: "0", total_net: "0",
    display_currency: "USD", total_income_display: "0", total_expense_display: "0", total_net_display: "0",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  // Görüntüleme para birimi USD.
  localStorage.setItem("kfinans_default_currency", "USD");

  // Rates: 1 USD = 35 TL. (formatTlAs yanlışlıkla *_display'e uygulansaydı /35 olurdu.)
  apiFns.getRates.mockResolvedValue({ rates: { TRY: "1", USD: "35" } });

  // Finans: *_display USD biriminde.
  apiFns.getIncomeSummary.mockResolvedValue({
    year: YYYY, month: MM, total: "35000", total_display: "1000", display_currency: "USD",
    count: 2, by_category: [],
  });
  apiFns.getIncomeDashboard.mockResolvedValue({
    this_month_actual: "35000", ytd_actual: "0", this_month_recurring: "0",
    ytd_recurring: "0", remaining_year_recurring: "0", year_total_estimate: "70000",
    display_currency: "USD",
    this_month_actual_display: "1000", ytd_actual_display: "0", this_month_recurring_display: "0",
    ytd_recurring_display: "0", remaining_year_recurring_display: "0", year_total_estimate_display: "2000",
  });
  apiFns.getExpenseSummary.mockResolvedValue({
    year: YYYY, month: MM, total: "17500", total_display: "500", display_currency: "USD",
    count: 3, by_category: [],
  });
  apiFns.getCashFlow.mockImplementation((y: number) => Promise.resolve(emptyCashFlowYear(y)));
  apiFns.listCreditCards.mockResolvedValue({
    cards: [{ id: 1 }],
    total_period_debt: "10500", total_debt: "21000", total_current_period_debt: "10500",
    display_currency: "USD", total_period_debt_display: "300", total_debt_display: "600",
  });
  apiFns.getForecast.mockResolvedValue({ year: YYYY, months: [], year_total: "0" });
  apiFns.getBudgetComparison.mockResolvedValue([]);
  apiFns.getGoal.mockResolvedValue({ progress_pct: null, passive_income_tl: null });

  // Yatırım (TL) — ağır kartlar artık /portfolio/live cache'inden gelir.
  // Sadece TEFAS dolu: 35000 TL → USD 1000 (grand total / Money testi için).
  apiFns.getLivePortfolio.mockResolvedValue({
    status: "ok",
    refreshed_at: "2026-06-13T10:00:00Z",
    stale: false,
    total_value_tl: "35000",
    rates: { TRY: "1", USD: "35" },
    health_issues: [],
    error: null,
    sections: {
      tefas: { positions: [{ code: "AFA", total_value_tl: "35000" }] },
      crypto: { positions: [], errors: {} },
      wallets: { positions: [], errors: {} },
      stocks: { positions: [] },
      commodities: { positions: [], total_value_tl: "0" },
      manual_crypto: { positions: [], total_value_tl: "0" },
    },
  });
  apiFns.refreshPortfolio.mockResolvedValue({ status: "ok", refreshed_at: "2026-06-13T10:05:00Z" });

  // Hafif kartlardan bazıları hâlâ ayrı endpoint'ten — boş döndür.
  apiFns.getBesHoldings.mockResolvedValue([]);
  apiFns.listCash.mockResolvedValue({ holdings: [], total_tl: "0" });

  apiFns.getPendingRealizations.mockResolvedValue({ items: [] });
  apiFns.getCreditCardReminders.mockResolvedValue({ pending_statements: [], due_payments: [] });
});

afterEach(() => {
  localStorage.clear();
});

describe("DashboardPage — finans değerleri backend *_display'inden (çift-çevrim yok)", () => {
  it("USD kullanıcı: gelir/gider/KK toplamları display değerini DOĞRUDAN gösterir (bölme yok)", async () => {
    render(<DashboardPage />);

    // Gelir total_display=1000 USD → "1.000,00 $" (round-trip olsaydı 1000/35≈28,57).
    // (Toplam Portföy de 1000 olduğu için birden çok eşleşme olabilir → findAll.)
    expect((await screen.findAllByText("1.000,00 $")).length).toBeGreaterThanOrEqual(1);
    // Gider total_display=500 USD → "500,00 $".
    expect(await screen.findByText("500,00 $")).toBeInTheDocument();
    // KK toplam borç display=600 USD → "600,00 $".
    expect(await screen.findByText("600,00 $")).toBeInTheDocument();
    // KK dönem borcu display=300 USD (footer içinde) → "300,00 $".
    expect(await screen.findByText("300,00 $")).toBeInTheDocument();
    // Gelir yıl sonu beklentisi display=2000 USD → "2.000,00 $".
    expect(await screen.findByText("2.000,00 $")).toBeInTheDocument();

    // Hatalı round-trip değerleri ASLA görünmemeli (1000/35≈28,57 vb).
    expect(screen.queryByText(/28,57/)).not.toBeInTheDocument();
    expect(screen.queryByText(/14,29/)).not.toBeInTheDocument();
  });

  it("finans net (bu ay) net_display'i doğrudan gösterir", async () => {
    render(<DashboardPage />);
    // net_display=250 USD → "+250,00 $" (net=8750 TL'ye round-trip olsaydı 250).
    expect(await screen.findByText("+250,00 $")).toBeInTheDocument();
  });

  it("grand total yatırım toplamını güncel kurla görüntüleme birimine çevirir (Money)", async () => {
    render(<DashboardPage />);
    // TEFAS 35000 TL → USD 1000 (35000/35). Toplam Portföy "1.000,00 $".
    // (Birden çok "1.000,00 $" olabilir: gelir kartı da 1000; en az bir tane yeterli.)
    await waitFor(() =>
      expect(screen.getAllByText("1.000,00 $").length).toBeGreaterThanOrEqual(1),
    );
  });

  it("görüntüleme para birimi değişince finans fetch'leri yeniden çalışır", async () => {
    render(<DashboardPage />);
    // İlk mount: displayCurrency "TRY"→"USD" geçişiyle effect 2 kez koşabilir; ilk
    // çağrılar bitsin diye finans toplamı ekrana gelene kadar bekle, sayacı yakala.
    expect(await screen.findByText("500,00 $")).toBeInTheDocument();
    const incomeBefore = apiFns.getIncomeSummary.mock.calls.length;
    const expenseBefore = apiFns.getExpenseSummary.mock.calls.length;
    const ccBefore = apiFns.listCreditCards.mock.calls.length;
    const remindersBefore = apiFns.getCreditCardReminders.mock.calls.length;

    // Para birimini değiştir → DISPLAY_CURRENCY_CHANGED olayı.
    await act(async () => {
      localStorage.setItem("kfinans_default_currency", "EUR");
      globalThis.dispatchEvent(new CustomEvent(DISPLAY_CURRENCY_CHANGED));
    });

    // useDisplayCurrency güncellenir → fetch effect (dep: displayCurrency) tekrar koşar.
    await waitFor(() =>
      expect(apiFns.getIncomeSummary.mock.calls.length).toBeGreaterThan(incomeBefore),
    );
    expect(apiFns.getExpenseSummary.mock.calls.length).toBeGreaterThan(expenseBefore);
    expect(apiFns.listCreditCards.mock.calls.length).toBeGreaterThan(ccBefore);
    // Reminders günde 1 kez popup için ayrı effect — currency dep'i yok (tekrar çağrılmaz).
    expect(apiFns.getCreditCardReminders.mock.calls.length).toBe(remindersBefore);
  });
});

describe("DashboardPage — sunucu-cache canlı portföy (ağır kartlar)", () => {
  it("ağır kart değerleri /portfolio/live section'ından gelir (TEFAS 35000 TL → 1.000,00 $)", async () => {
    render(<DashboardPage />);
    // Heavy card Money ile TL→USD: 35000/35 = 1000.
    await waitFor(() =>
      expect(screen.getAllByText("1.000,00 $").length).toBeGreaterThanOrEqual(1),
    );
    // Ağır kartlar için ayrı tefas/crypto/wallet endpoint'leri ARTIK çağrılmaz.
    expect(apiFns.getTefasHoldings).not.toHaveBeenCalled();
    expect(apiFns.getCryptoPositions).not.toHaveBeenCalled();
    expect(apiFns.getWalletPositions).not.toHaveBeenCalled();
    // Tek canlı çağrı yeterli (status ok → poll yok).
    expect(apiFns.getLivePortfolio).toHaveBeenCalled();
  });

  it("mount'ta otomatik dış-refetch YOK — sadece getLivePortfolio okunur", async () => {
    render(<DashboardPage />);
    await waitFor(() => expect(apiFns.getLivePortfolio).toHaveBeenCalled());
    // refreshPortfolio mount'ta tetiklenmez (login layout'ta tetiklenir, dashboard'da değil).
    expect(apiFns.refreshPortfolio).not.toHaveBeenCalled();
  });

  it("'Yenile' butonu refreshPortfolio(true) çağırır", async () => {
    render(<DashboardPage />);
    await waitFor(() => expect(apiFns.getLivePortfolio).toHaveBeenCalled());

    // LivePortfolioBar butonu i18n key'i gösterir (t stub identity).
    const refreshBtn = await screen.findByText("dashboard.live.refresh");
    await act(async () => {
      refreshBtn.click();
    });
    await waitFor(() => expect(apiFns.refreshPortfolio).toHaveBeenCalledWith(true));
  });
});
