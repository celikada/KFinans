import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.setConfig({ testTimeout: 30000 });

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: number | string) => `₺${Number(v).toFixed(2)}`,
  useDisplayCurrency: () => "TRY",
}));

vi.mock("@/app/_components/ConfirmDialog", () => ({ useConfirm: () => async () => true }));
vi.mock("@/lib/defaultCurrency", () => ({ getDefaultCurrency: () => "TRY" }));

const listDebts = vi.fn();
const settleDebt = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    listPersonalDebts: (...a: unknown[]) => listDebts(...a),
    createPersonalDebt: vi.fn(),
    settlePersonalDebt: (...a: unknown[]) => settleDebt(...a),
    deletePersonalDebt: vi.fn(),
  },
  CURRENCIES: ["TRY", "USD", "EUR"],
}));

import { PersonalDebts } from "@/app/dashboard/budget/_components/PersonalDebts";

const DATA = {
  display_currency: "TRY",
  items: [
    { id: 1, counterparty: "Ezgi", kind: "debt", amount: "1500", currency: "TRY", due_date: "2026-07-01", note: "borç", settled_at: null, amount_display: "1500", created_at: "x", updated_at: "x" },
    { id: 2, counterparty: "İlkem", kind: "receivable", amount: "2000", currency: "TRY", due_date: null, note: null, settled_at: null, amount_display: "2000", created_at: "x", updated_at: "x" },
  ],
  total_debt_display: "1500",
  total_receivable_display: "2000",
  net_display: "500",
};

describe("PersonalDebts", () => {
  beforeEach(() => {
    listDebts.mockReset().mockResolvedValue(DATA);
    settleDebt.mockReset().mockResolvedValue(DATA.items[0]);
  });

  it("renders debt/receivable rows + summary totals", async () => {
    render(<PersonalDebts />);
    await waitFor(() => expect(screen.getByText("Ezgi")).toBeInTheDocument());
    expect(screen.getByText("İlkem")).toBeInTheDocument();
    // Özet: net 500 + toplam borç/alacak
    expect(screen.getByText("₺500.00")).toBeInTheDocument();
    expect(screen.getAllByText("₺2000.00").length).toBeGreaterThan(0);
  });

  it("fetches list on mount", async () => {
    render(<PersonalDebts />);
    await waitFor(() => expect(listDebts).toHaveBeenCalled());
  });
});
