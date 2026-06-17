import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.setConfig({ testTimeout: 30000 });

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: number | string) => `₺${Number(v).toFixed(2)}`,
  useDisplayCurrency: () => "TRY",
}));

const getGrid = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getBudgetGrid: (...a: unknown[]) => getGrid(...a),
    upsertBudgetLine: vi.fn(),
    deleteBudgetLine: vi.fn(),
  },
  EXPENSE_CATEGORY_LABELS: { groceries: "Market", food: "Yiyecek" },
}));

import { BudgetGrid } from "@/app/dashboard/budget/_components/BudgetGrid";

function cells(plannedMay: string | null, actualMay: string) {
  return Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    planned: i === 4 ? plannedMay : null,
    planned_currency: i === 4 ? "TRY" : null,
    planned_display: i === 4 ? plannedMay : null,
    actual_display: i === 4 ? actualMay : "0",
  }));
}

const GRID = {
  year: 2026,
  display_currency: "TRY",
  rows: [
    { category: "groceries", bucket: "fundamental", cells: cells("5000", "4200"), planned_total_display: "5000", actual_total_display: "4200" },
    { category: "food", bucket: "fun", cells: cells(null, "0"), planned_total_display: "0", actual_total_display: "0" },
  ],
  monthly_planned_display: Array.from({ length: 12 }, (_, i) => (i === 4 ? "5000" : "0")),
  monthly_actual_display: Array.from({ length: 12 }, (_, i) => (i === 4 ? "4200" : "0")),
  planned_total_display: "5000",
  actual_total_display: "4200",
};

describe("BudgetGrid", () => {
  beforeEach(() => {
    getGrid.mockReset().mockResolvedValue(GRID);
  });

  it("renders category rows + planned totals", async () => {
    render(<BudgetGrid year={2026} />);
    await waitFor(() => expect(screen.getByText("Market")).toBeInTheDocument());
    expect(screen.getByText("Yiyecek")).toBeInTheDocument();
    // Planlanan değer hücresi + satır toplamı
    expect(screen.getAllByText("₺5000.00").length).toBeGreaterThan(0);
  });

  it("loads grid for the given year", async () => {
    render(<BudgetGrid year={2026} />);
    await waitFor(() => expect(getGrid).toHaveBeenCalledWith(2026));
  });
});
