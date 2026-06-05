import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.setConfig({ testTimeout: 30000 });

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

// Money: formatTlAs deterministik (TL değerini olduğu gibi string'e çevir).
vi.mock("@/app/_components/Money", () => ({
  formatTlAs: (tl: number) => `₺${tl.toFixed(2)}`,
  useRates: () => ({ USD: 35 }),
  useDisplayCurrency: () => "TRY",
}));

const getDetail = vi.fn();
vi.mock("@/lib/api", () => ({ api: { getCashFlowMonthDetail: (...a: unknown[]) => getDetail(...a) } }));

import { CashFlowMonthDetailModal } from "@/app/dashboard/cash-flow/_components/CashFlowMonthDetailModal";

const DETAIL = {
  year: 2026,
  month: 6,
  is_past: false,
  is_current: false,
  income_items: [
    { kind: "actual", category: "income", label: "Maaş", sub_label: "salary", date: "2026-06-01", amount: "30000", currency: "TRY", amount_tl: "30000" },
  ],
  expense_items: [
    { kind: "actual", category: "statement", label: "Garanti", sub_label: "05/2026 ekstresi", date: "2026-06-10", amount: "1200", currency: "TRY", amount_tl: "1200" },
    { kind: "forecast", category: "installment", label: "Garanti · Laptop", sub_label: "5/12 taksit kaldı · ilk vade 2026-06-01", date: null, amount: "1000", currency: "TRY", amount_tl: "1000" },
  ],
  income_total: "30000",
  expense_total: "2200",
  net: "27800",
};

describe("CashFlowMonthDetailModal", () => {
  beforeEach(() => {
    getDetail.mockReset().mockResolvedValue(DETAIL);
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("ayın gelir ve gider kalemlerini listeler", async () => {
    render(<CashFlowMonthDetailModal year={2026} month={6} monthName="Haz" onClose={vi.fn()} />);
    await waitFor(() => expect(getDetail).toHaveBeenCalledWith(2026, 6));
    expect(await screen.findByText("Maaş")).toBeInTheDocument();
    expect(screen.getByText("Garanti")).toBeInTheDocument();
    // Taksit kalemi kalan/toplam bilgisiyle gelir
    expect(screen.getByText("Garanti · Laptop")).toBeInTheDocument();
    expect(screen.getByText(/5\/12 taksit kaldı/)).toBeInTheDocument();
  });

  it("gelir/gider toplamı ve net gösterir", async () => {
    render(<CashFlowMonthDetailModal year={2026} month={6} monthName="Haz" onClose={vi.fn()} />);
    // gelir toplamı: hem bölüm başlığı hem tek kalem ₺30000.00 → en az 1 eşleşme
    expect((await screen.findAllByText("₺30000.00")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("₺2200.00")).toBeInTheDocument(); // gider toplamı (tek)
    expect(screen.getByText(/\+₺27800\.00/)).toBeInTheDocument(); // net (tek)
  });

  it("kapat butonu onClose çağırır", async () => {
    const onClose = vi.fn();
    render(<CashFlowMonthDetailModal year={2026} month={6} monthName="Haz" onClose={onClose} />);
    await screen.findByText("Maaş");
    screen.getByLabelText("common.close").click();
    expect(onClose).toHaveBeenCalled();
  });
});
