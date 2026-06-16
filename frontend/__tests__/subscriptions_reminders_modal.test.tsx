import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: string | number, c: string) => `${v} ${c}`,
}));

import { SubscriptionRemindersModal } from "@/app/dashboard/_components/SubscriptionRemindersModal";

const DATA = {
  pending_bills: [
    { subscription_id: 1, provider_name: "ESGAZ", label: null, period_year: 2026, period_month: 6 },
  ],
  due_payments: [
    { subscription_id: 1, bill_id: 10, provider_name: "ESGAZ", label: "Ev", bill_amount: "500", currency: "TRY", due_date: "2026-06-20", days_until_due: 4 },
    { subscription_id: 2, bill_id: 11, provider_name: "TTNET", label: null, bill_amount: "100", currency: "TRY", due_date: "2026-06-10", days_until_due: -2 },
    { subscription_id: 3, bill_id: 12, provider_name: "Vodafone", label: null, bill_amount: "50", currency: "TRY", due_date: "2026-06-16", days_until_due: 0 },
  ],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any;

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn();
  HTMLDialogElement.prototype.close = vi.fn();
  push.mockReset();
});

describe("SubscriptionRemindersModal", () => {
  it("pending + due (overdue/today/future) kalemlerini render eder + takvim linki kurar", () => {
    const { container } = render(<SubscriptionRemindersModal data={DATA} onClose={vi.fn()} />);
    expect(screen.getByText("content.subReminders.pendingSection")).toBeInTheDocument();
    expect(screen.getByText("content.subReminders.dueSection")).toBeInTheDocument();
    expect(screen.getByText("Ev")).toBeInTheDocument();
    // due kalemleri için Google Takvim linkleri kurulur (3 due → 3 link)
    const calLinks = container.querySelectorAll("a[href*='calendar.google.com']");
    expect(calLinks.length).toBe(3);
    expect(calLinks[0].getAttribute("href")).toContain("action=TEMPLATE");
  });

  it("'Öde' butonu onClose + abonelik sekmesine yönlendirir", async () => {
    const onClose = vi.fn();
    render(<SubscriptionRemindersModal data={DATA} onClose={onClose} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getAllByText("content.subReminders.payBtn")[0]);
    expect(onClose).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/dashboard/expenses?tab=abonelikler");
  });

  it("'Fatura gir' butonu da yönlendirir", async () => {
    render(<SubscriptionRemindersModal data={DATA} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.subReminders.enterBillBtn"));
    expect(push).toHaveBeenCalledWith("/dashboard/expenses?tab=abonelikler");
  });
});
