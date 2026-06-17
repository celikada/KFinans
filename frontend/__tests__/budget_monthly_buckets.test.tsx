import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.setConfig({ testTimeout: 30000 });

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: number | string) => `₺${Number(v).toFixed(2)}`,
  useDisplayCurrency: () => "TRY",
}));

const getMonthly = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { getMonthlyBudget: (...a: unknown[]) => getMonthly(...a) },
  EXPENSE_CATEGORY_LABELS: { groceries: "Market", food: "Yiyecek" },
}));

import { MonthlyBuckets } from "@/app/dashboard/budget/_components/MonthlyBuckets";

const RESPONSE = {
  year: 2026,
  month: 5,
  display_currency: "TRY",
  income_display: "50000",
  expense_total_display: "8000",
  net_display: "42000",
  buckets: [
    {
      bucket: "fundamental",
      target_ratio: 0.5,
      budget_total_display: "5000",
      actual_total_display: "8000",
      difference_display: "-3000",
      actual_ratio: 1.0,
      categories: [
        { category: "groceries", budget_display: "5000", actual_display: "8000", difference_display: "-3000", pct_used: 160, over_budget: true, weighted: false },
        { category: "Kasko", budget_display: "1000", actual_display: "0", difference_display: "1000", pct_used: null, over_budget: false, weighted: true },
      ],
    },
    { bucket: "fun", target_ratio: 0.3, budget_total_display: "0", actual_total_display: "0", difference_display: "0", actual_ratio: 0, categories: [] },
    { bucket: "future", target_ratio: 0.2, budget_total_display: "0", actual_total_display: "0", difference_display: "0", actual_ratio: 0, categories: [] },
  ],
};

describe("MonthlyBuckets", () => {
  beforeEach(() => {
    getMonthly.mockReset().mockResolvedValue(RESPONSE);
  });

  it("renders income/expense/net + 3 bucket labels", async () => {
    render(<MonthlyBuckets year={2026} month={5} />);
    await waitFor(() => expect(screen.getByText("content.budgetV2.buckets.fundamental")).toBeInTheDocument());
    expect(screen.getByText("content.budgetV2.buckets.fun")).toBeInTheDocument();
    expect(screen.getByText("content.budgetV2.buckets.future")).toBeInTheDocument();
    // Net = 42000
    expect(screen.getByText("₺42000.00")).toBeInTheDocument();
  });

  it("shows weighted badge for non-monthly periodic rows", async () => {
    render(<MonthlyBuckets year={2026} month={5} />);
    await waitFor(() => expect(screen.getByText("Kasko")).toBeInTheDocument());
    // weighted satır rozeti
    expect(screen.getByText(/content.budgetV2.weighted/)).toBeInTheDocument();
  });

  it("calls getMonthlyBudget with year/month", async () => {
    render(<MonthlyBuckets year={2026} month={5} />);
    await waitFor(() => expect(getMonthly).toHaveBeenCalledWith(2026, 5));
  });
});
