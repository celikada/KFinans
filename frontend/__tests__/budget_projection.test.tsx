import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.setConfig({ testTimeout: 30000 });

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: number | string) => `₺${Number(v).toFixed(2)}`,
  useDisplayCurrency: () => "TRY",
}));

// recharts → jsdom'da render etmesin.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}));

const getCashFlow = vi.fn();
vi.mock("@/lib/api", () => ({ api: { getCashFlow: (...a: unknown[]) => getCashFlow(...a) } }));

import { BudgetProjection } from "@/app/dashboard/budget/_components/BudgetProjection";

function months() {
  return Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    income_total_display: i === 0 ? "30000" : "10000",
    expense_total_display: "8000",
    net_display: i === 0 ? "22000" : "2000",
    is_past: i === 0,
  }));
}

const CF = {
  year: 2026,
  months: months(),
  display_currency: "TRY",
  total_income_display: "140000",
  total_expense_display: "96000",
  total_net_display: "44000",
};

describe("BudgetProjection", () => {
  beforeEach(() => {
    getCashFlow.mockReset().mockResolvedValue(CF);
  });

  it("renders projection table + cumulative year-end balance", async () => {
    render(<BudgetProjection year={2026} />);
    // Kümülatif yıl sonu = 22000 + 11×2000 = 44000
    await waitFor(() => expect(screen.getAllByText("₺44000.00").length).toBeGreaterThan(0));
    // Aylık tabloda gelir/gider değerleri görünür
    expect(screen.getAllByText("₺8000.00").length).toBeGreaterThan(0);
  });

  it("fetches cash flow for the year", async () => {
    render(<BudgetProjection year={2026} />);
    await waitFor(() => expect(getCashFlow).toHaveBeenCalledWith(2026));
  });
});
