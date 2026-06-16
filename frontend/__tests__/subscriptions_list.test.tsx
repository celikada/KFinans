import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const deleteSubscription = vi.fn();
const listCreditCards = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    deleteSubscription: (...a: unknown[]) => deleteSubscription(...a),
    listCreditCards: (...a: unknown[]) => listCreditCards(...a),
  },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

const confirmMock = vi.fn();
vi.mock("@/app/_components/ConfirmDialog", () => ({ useConfirm: () => confirmMock }));

import { SubscriptionList } from "@/app/dashboard/expenses/_components/SubscriptionList";
import type { SubscriptionDTO } from "@/lib/api";

function makeSub(over: Partial<SubscriptionDTO> = {}): SubscriptionDTO {
  return {
    id: 1,
    provider_code: "esgaz",
    provider_name: "ESGAZ",
    category: "gas",
    subscriber_no: "12345",
    label: "Ev",
    budget_amount: "500",
    currency: "TRY",
    start_date: "2026-01-01",
    billing_day: null,
    due_day: 20,
    active: true,
    notes: null,
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
    current_status: "budget",
    current_amount: "500",
    current_bill_id: null,
    ...over,
  };
}

describe("SubscriptionList", () => {
  beforeEach(() => {
    deleteSubscription.mockReset().mockResolvedValue(undefined);
    listCreditCards.mockReset().mockResolvedValue({ cards: [] });
    confirmMock.mockReset().mockResolvedValue(true);
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("boş listede empty mesajı gösterir", () => {
    render(<SubscriptionList items={[]} onChanged={vi.fn()} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    expect(screen.getByText("content.subscriptions.empty")).toBeInTheDocument();
  });

  it("abonelik satırını + budget rozetini gösterir; budget durumda 'Fatura geldi' var, 'Ödendi' yok", () => {
    render(<SubscriptionList items={[makeSub()]} onChanged={vi.fn()} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    expect(screen.getByText("Ev")).toBeInTheDocument();
    expect(screen.getByText("ESGAZ")).toBeInTheDocument();
    // Budget durumda fatura girilebilir, ödeme henüz yok.
    expect(screen.getByText("content.subscriptions.issueAction")).toBeInTheDocument();
    expect(screen.queryByText("content.subscriptions.payAction")).not.toBeInTheDocument();
  });

  it("issued + current_bill_id varsa 'Ödendi' butonu görünür", () => {
    const sub = makeSub({ current_status: "issued", current_amount: "612.40", current_bill_id: 9 });
    render(<SubscriptionList items={[sub]} onChanged={vi.fn()} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    expect(screen.getByText("content.subscriptions.payAction")).toBeInTheDocument();
  });

  it("'Sil' → onay sonrası deleteSubscription + onDeleted çağrılır", async () => {
    const onDeleted = vi.fn();
    render(<SubscriptionList items={[makeSub()]} onChanged={vi.fn()} onDeleted={onDeleted} onEdit={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("common.delete"));
    expect(confirmMock).toHaveBeenCalled();
    await vi.waitFor(() => expect(deleteSubscription).toHaveBeenCalledWith(1));
    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalledWith(1));
  });
});
