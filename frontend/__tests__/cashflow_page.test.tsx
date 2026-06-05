import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor, within } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
const replaceMock = vi.fn();
const pushMock = vi.fn();
const routerStub = { replace: replaceMock, push: pushMock, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

// STABIL i18n — yeni `t` referansi useCallback([..., t]) refresh'i sonsuz tetikler.
const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));

// PageHeader → sade baslik (LanguageSwitcher + router karmasasi olmadan).
vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// recharts → jsdom'da render etmesin.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div data-testid="composed-chart">{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}));

const getCashFlow = vi.fn();
const downloadReport = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getCashFlow: (...a: unknown[]) => getCashFlow(...a),
    downloadReport: (...a: unknown[]) => downloadReport(...a),
    getRates: () => Promise.resolve({ rates: { TRY: "1", USD: "35", EUR: "38", GBP: "44", CHF: "40", JPY: "0.23" } }),
  },
}));

import CashFlowPage from "@/app/dashboard/cash-flow/page";

const CURRENT_YEAR = new Date().getFullYear();

function month(m: number, opts: Partial<{
  income_actual: string; income_forecast: string;
  expense_actual: string; expense_forecast: string;
  income_total: string; expense_total: string; net: string; is_past: boolean;
}> = {}) {
  return {
    month: m,
    income_actual: opts.income_actual ?? "0",
    income_forecast: opts.income_forecast ?? "0",
    expense_actual: opts.expense_actual ?? "0",
    expense_forecast: opts.expense_forecast ?? "0",
    income_total: opts.income_total ?? "1000",
    expense_total: opts.expense_total ?? "600",
    net: opts.net ?? "400",
    is_past: opts.is_past ?? false,
  };
}

function yearData(year: number) {
  return {
    year,
    months: [
      month(1, { is_past: true, income_actual: "1000", expense_actual: "600", net: "400" }),
      month(2, { is_past: false, income_forecast: "1500", expense_forecast: "900", net: "600", income_total: "1500", expense_total: "900" }),
      month(3, { is_past: false, net: "-200", income_total: "300", expense_total: "500" }),
    ],
    total_income: "2800",
    total_expense: "2000",
    total_net: "800",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getCashFlow.mockResolvedValue(yearData(CURRENT_YEAR));
  downloadReport.mockResolvedValue(undefined);
});

describe("CashFlowPage — yukleme + render", () => {
  it("ilk renderda bu yili (currentYear) ceker + metrik kartlari", async () => {
    render(<CashFlowPage />);

    await waitFor(() => expect(getCashFlow).toHaveBeenCalledWith(CURRENT_YEAR));
    // 3 metrik kart basligi.
    expect(await screen.findByText("content.cashFlow.totalIncome")).toBeInTheDocument();
    expect(screen.getByText("content.cashFlow.totalExpense")).toBeInTheDocument();
    // table.net hem metrik kartinda hem tablo basliginda gecer.
    expect(screen.getAllByText("table.net").length).toBeGreaterThan(0);
    // Toplam gelir 2800 → "2.800,00" (tr-TR). Hem kart hem tfoot'ta gecer.
    expect(screen.getAllByText(/2\.800,00 ₺/).length).toBeGreaterThan(0);
  });

  it("yuklendiginde grafik + 12 aylik tablo + tfoot toplam gorunur", async () => {
    render(<CashFlowPage />);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("composed-chart")).toBeInTheDocument();
    // Tablo basliklari.
    expect(screen.getByText("table.month")).toBeInTheDocument();
    expect(screen.getByText("table.actualIncome")).toBeInTheDocument();
    expect(screen.getByText("table.forecastExpense")).toBeInTheDocument();
    // tfoot yil toplami satiri.
    expect(screen.getByText("content.cashFlow.yearTotal")).toBeInTheDocument();
    // Net negatif ay (mart, -200) → tabloda "-200,00 ₺".
    expect(screen.getByText(/-200,00 ₺/)).toBeInTheDocument();
  });

  it("net pozitif → '+' isareti, net negatif → '+' yok", async () => {
    render(<CashFlowPage />);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    // total_net 800 pozitif → "+800,00 ₺" en az bir yerde (kart + tfoot).
    expect(screen.getAllByText(/\+800,00 ₺/).length).toBeGreaterThan(0);
  });

  it("gelecek aylar 'forecast' rozeti gosterir", async () => {
    render(<CashFlowPage />);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    // is_past=false aylar icin forecast etiketi (subat + mart = 2 satir + yil secici).
    expect(screen.getAllByText("content.cashFlow.forecast").length).toBeGreaterThan(0);
  });
});

describe("CashFlowPage — yil secici", () => {
  it("gecmis yil secimi → getCashFlow yeni yil ile cagrilir", async () => {
    getCashFlow.mockImplementation((y: number) => Promise.resolve(yearData(y)));
    render(<CashFlowPage />);
    await waitFor(() => expect(getCashFlow).toHaveBeenCalledWith(CURRENT_YEAR));
    const user = userEvent.setup();

    // Yil secici: currentYear-1, currentYear, currentYear+1 butonlari (metin yil + etiket).
    const prevBtn = screen.getByRole("button", { name: new RegExp(`^${CURRENT_YEAR - 1}`) });
    await user.click(prevBtn);
    await waitFor(() => expect(getCashFlow).toHaveBeenLastCalledWith(CURRENT_YEAR - 1));

    const nextBtn = screen.getByRole("button", { name: new RegExp(`^${CURRENT_YEAR + 1}`) });
    await user.click(nextBtn);
    await waitFor(() => expect(getCashFlow).toHaveBeenLastCalledWith(CURRENT_YEAR + 1));
  });

  it("gecmis/bu/gelecek yil etiketleri gorunur", async () => {
    render(<CashFlowPage />);
    // Veri yuklensin (tablo + grafik gelsin).
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    // Yil secici etiketleri "(...)" parantezleriyle span icinde → esnek matcher.
    expect(
      screen.getByText((c) => c === "(content.cashFlow.past)"),
    ).toBeInTheDocument();
    expect(
      screen.getByText((c) => c === "(content.cashFlow.thisYear)"),
    ).toBeInTheDocument();
    // forecast: yil secicide "(...)" parantezli, tablo satirlarinda duz → ikisini de
    // kapsayan icerik matcher'i.
    expect(
      screen.getAllByText((c) => c.includes("content.cashFlow.forecast")).length,
    ).toBeGreaterThan(0);
  });
});

describe("CashFlowPage — rapor indirme", () => {
  it("Excel butonu → downloadReport dogru xlsx path ile cagrilir", async () => {
    render(<CashFlowPage />);
    expect(await screen.findByText("content.cashFlow.totalIncome")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    expect(downloadReport).toHaveBeenCalledWith(
      `/cash-flow/report.xlsx?year=${CURRENT_YEAR}`,
      `content.cashFlow.fileSlug-${CURRENT_YEAR}.xlsx`,
    );
  });

  it("PDF butonu → downloadReport dogru pdf path ile cagrilir", async () => {
    render(<CashFlowPage />);
    expect(await screen.findByText("content.cashFlow.totalIncome")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "content.cashFlow.pdfDownload" }));
    expect(downloadReport).toHaveBeenCalledWith(
      `/cash-flow/report.pdf?year=${CURRENT_YEAR}`,
      `content.cashFlow.fileSlug-${CURRENT_YEAR}.pdf`,
    );
  });
});

describe("CashFlowPage — hata + bos durum", () => {
  it("load 401 → login'e yonlendirir, hata gosterilmez", async () => {
    getCashFlow.mockRejectedValue(new Error("Request failed 401"));
    render(<CashFlowPage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByTestId("composed-chart")).not.toBeInTheDocument();
  });

  it("load 401 disi hata → hata mesaji", async () => {
    getCashFlow.mockRejectedValue(new Error("sunucu hatasi"));
    render(<CashFlowPage />);
    expect(await screen.findByText("sunucu hatasi")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("load Error olmayan deger → fallback ceviri mesaji", async () => {
    getCashFlow.mockRejectedValue("string hata");
    render(<CashFlowPage />);
    expect(await screen.findByText("content.cashFlow.loadFailed")).toBeInTheDocument();
  });

  it("data null iken (hata) grafik ve tablo cizilmez", async () => {
    getCashFlow.mockRejectedValue(new Error("bir sorun"));
    render(<CashFlowPage />);
    expect(await screen.findByText("bir sorun")).toBeInTheDocument();
    expect(screen.queryByTestId("composed-chart")).not.toBeInTheDocument();
    expect(screen.queryByText("table.month")).not.toBeInTheDocument();
    // Metrik kartlari yine cizilir (data yoksa 0 gosterir).
    expect(screen.getByText("content.cashFlow.totalIncome")).toBeInTheDocument();
  });
});

describe("CashFlowPage — tablo icerigi", () => {
  it("ay satirlari gercek/tahmin gelir-gider degerlerini gosterir", async () => {
    render(<CashFlowPage />);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    const table = screen.getByRole("table");
    // Ocak: actual gelir 1000 → "1.000,00 ₺".
    expect(within(table).getByText(/1\.000,00 ₺/)).toBeInTheDocument();
    // Subat: forecast gelir 1500 → "1.500,00 ₺".
    expect(within(table).getByText(/1\.500,00 ₺/)).toBeInTheDocument();
  });
});
