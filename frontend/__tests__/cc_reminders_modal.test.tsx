import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const routerPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }) }));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

const payStatement = vi.fn();
vi.mock("@/lib/api", () => ({ api: { payStatement: (...a: unknown[]) => payStatement(...a) } }));

import { CreditCardRemindersModal } from "@/app/dashboard/_components/CreditCardRemindersModal";
import type { CreditCardRemindersDTO } from "@/lib/api";

const DATA: CreditCardRemindersDTO = {
  pending_statements: [
    { card_id: 1, name: "Garanti Bonus", bank_name: "Garanti", last_4: "1234", period_year: 2026, period_month: 5, cutoff_date: "2026-05-15" },
  ],
  due_payments: [
    { card_id: 2, card_name: "Akbank Axess", bank_name: "Akbank", statement_id: 9, period_year: 2026, period_month: 5, due_date: "2026-06-08", statement_amount: "1704.50", days_until_due: 3 },
  ],
};

describe("CreditCardRemindersModal", () => {
  beforeEach(() => {
    routerPush.mockReset();
    payStatement.mockReset().mockResolvedValue({ id: 9, statement_amount: "1704.50", paid_at: "x", paid_amount: "1704.50" });
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("ekstresi eksik kartı ve ödeme hatırlatmasını gösterir", () => {
    render(<CreditCardRemindersModal data={DATA} onClose={vi.fn()} />);
    expect(screen.getByText("Garanti Bonus")).toBeInTheDocument();
    expect(screen.getByText("Akbank Axess")).toBeInTheDocument();
    // Tutar gösterimi
    expect(screen.getByText(/1\.704,50/)).toBeInTheDocument();
  });

  it("'Ekstre yükle' → kart detayına yönlendirir + kapanır", async () => {
    const onClose = vi.fn();
    render(<CreditCardRemindersModal data={DATA} onClose={onClose} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.ccReminders.uploadBtn"));
    expect(routerPush).toHaveBeenCalledWith("/dashboard/credit-cards/1");
    expect(onClose).toHaveBeenCalled();
  });

  it("Google Takvim linki doğru tarih + render URL içerir", () => {
    render(<CreditCardRemindersModal data={DATA} onClose={vi.fn()} />);
    const link = screen.getByText(/content\.ccReminders\.addToCalendar/).closest("a");
    expect(link).toHaveAttribute("href", expect.stringContaining("calendar.google.com/calendar/render"));
    expect(link?.getAttribute("href")).toContain("20260608"); // due_date YYYYMMDD
    expect(link?.getAttribute("href")).toContain("20260609"); // end (next day)
  });

  it("'Ödendi' → ödeme modal'ı açılır; tam ödeme payStatement çağırır + satır düşer", async () => {
    render(<CreditCardRemindersModal data={DATA} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    // "Ödendi" → StatementPayModal aç (henüz payStatement çağrılmaz)
    await user.click(screen.getByText(/content\.ccReminders\.markPaid/));
    expect(payStatement).not.toHaveBeenCalled();
    // Modal başlığı görünür; tam ödeme varsayılan → "Öde" ile gönder
    expect(await screen.findByText("content.creditCards.pay.title")).toBeInTheDocument();
    await user.click(screen.getByText("content.creditCards.pay.submit"));
    await waitFor(() =>
      expect(payStatement).toHaveBeenCalledWith(2, 9, {
        paid_amount: 1704.5,
        paid_at: expect.any(String),
      }),
    );
    // Ödeme satırı (Akbank Axess) listeden düşer
    await waitFor(() => expect(screen.queryByText("Akbank Axess")).not.toBeInTheDocument());
  });
});
