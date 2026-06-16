import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const issueSubscriptionBill = vi.fn();
const paySubscriptionBill = vi.fn();
const listCreditCards = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    issueSubscriptionBill: (...a: unknown[]) => issueSubscriptionBill(...a),
    paySubscriptionBill: (...a: unknown[]) => paySubscriptionBill(...a),
    listCreditCards: (...a: unknown[]) => listCreditCards(...a),
  },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { SubscriptionBillModal } from "@/app/dashboard/expenses/_components/SubscriptionBillModal";

const SUB = {
  id: 7,
  provider_code: "esgaz",
  provider_name: "ESGAZ",
  category: "gas",
  subscriber_no: "123",
  label: "Ev",
  budget_amount: "500",
  currency: "TRY",
  active: true,
  current_status: "budget",
  current_amount: "500",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any;

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn();
  HTMLDialogElement.prototype.close = vi.fn();
  issueSubscriptionBill.mockReset().mockResolvedValue({ id: 1, status: "issued" });
  paySubscriptionBill.mockReset().mockResolvedValue({ id: 1, status: "paid" });
  listCreditCards.mockReset().mockResolvedValue({ cards: [{ id: 3, name: "Bonus", last_4: "1234" }] });
});

describe("SubscriptionBillModal — issue", () => {
  it("ön-doldurulmuş alanlarla gönderince issueSubscriptionBill çağrılır", async () => {
    const onDone = vi.fn();
    render(<SubscriptionBillModal sub={SUB} mode="issue" onClose={vi.fn()} onDone={onDone} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("common.save"));
    await waitFor(() => expect(issueSubscriptionBill).toHaveBeenCalled());
    expect(issueSubscriptionBill.mock.calls[0][0]).toBe(7);
    const payload = issueSubscriptionBill.mock.calls[0][1];
    expect(payload.bill_amount).toBe(500);
    expect(onDone).toHaveBeenCalled();
  });
});

describe("SubscriptionBillModal — pay", () => {
  it("nakit ödeme paySubscriptionBill'i cash ile çağırır", async () => {
    const onDone = vi.fn();
    render(<SubscriptionBillModal sub={SUB} mode="pay" billId={42} onClose={vi.fn()} onDone={onDone} />);
    await waitFor(() => expect(listCreditCards).toHaveBeenCalled());
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("common.save"));
    await waitFor(() => expect(paySubscriptionBill).toHaveBeenCalled());
    expect(paySubscriptionBill.mock.calls[0][0]).toBe(7);
    expect(paySubscriptionBill.mock.calls[0][1]).toBe(42);
    expect(paySubscriptionBill.mock.calls[0][2].payment_method).toBe("cash");
    expect(paySubscriptionBill.mock.calls[0][2].credit_card_id).toBeNull();
  });

  it("kredi kartı seçilince pay credit_card + kart id ile çağrılır", async () => {
    render(<SubscriptionBillModal sub={SUB} mode="pay" billId={42} onClose={vi.fn()} onDone={vi.fn()} />);
    await waitFor(() => expect(listCreditCards).toHaveBeenCalled());
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByDisplayValue("credit_card"));
    await user.selectOptions(screen.getByLabelText("content.subscriptions.bill.selectCard"), "3");
    await user.click(screen.getByText("common.save"));
    await waitFor(() => expect(paySubscriptionBill).toHaveBeenCalled());
    expect(paySubscriptionBill.mock.calls[0][2].payment_method).toBe("credit_card");
    expect(paySubscriptionBill.mock.calls[0][2].credit_card_id).toBe(3);
  });
});
