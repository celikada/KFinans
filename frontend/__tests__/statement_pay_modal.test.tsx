import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const payStatement = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { payStatement: (...a: unknown[]) => payStatement(...a) },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { StatementPayModal } from "@/app/dashboard/credit-cards/_components/StatementPayModal";
import type { StatementDTO } from "@/lib/api";

const STATEMENT = {
  id: 9,
  card_id: 2,
  period_year: 2026,
  period_month: 5,
  statement_amount: "1000.00",
  statement_date: "2026-05-05",
  due_date: "2026-05-15",
  paid_at: null,
  paid_amount: null,
  notes: null,
  created_at: "2026-05-05T00:00:00Z",
} satisfies StatementDTO;

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.open = true;
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.open = false;
  });
  payStatement.mockReset().mockResolvedValue({ ...STATEMENT, paid_at: "x", paid_amount: "1000.00" });
});

describe("StatementPayModal", () => {
  it("varsayılan tam ödeme → paid_amount = statement_amount; onPaid çağrılır", async () => {
    const onPaid = vi.fn();
    render(<StatementPayModal cardId={2} statement={STATEMENT} onClose={vi.fn()} onPaid={onPaid} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.creditCards.pay.submit"));
    await waitFor(() => expect(payStatement).toHaveBeenCalled());
    expect(payStatement.mock.calls[0][0]).toBe(2);
    expect(payStatement.mock.calls[0][1]).toBe(9);
    expect(payStatement.mock.calls[0][2].paid_amount).toBe(1000);
    expect(payStatement.mock.calls[0][2].paid_at).toEqual(expect.any(String));
    await waitFor(() => expect(onPaid).toHaveBeenCalled());
  });

  it("kısmi ödeme → girilen tutar gönderilir + kalan notu görünür", async () => {
    const onPaid = vi.fn();
    render(<StatementPayModal cardId={2} statement={STATEMENT} onClose={vi.fn()} onPaid={onPaid} />);
    const user = userEvent.setup({ delay: null });
    // Kısmi moda geç
    await user.click(screen.getByDisplayValue("partial"));
    const input = screen.getByLabelText(/content\.creditCards\.pay\.amountLabel/);
    await user.clear(input);
    await user.type(input, "400");
    // Kalan notu: 1000 - 400 = 600
    expect(screen.getByText(/content\.creditCards\.pay\.remainderNote/)).toBeInTheDocument();
    await user.click(screen.getByText("content.creditCards.pay.submit"));
    await waitFor(() => expect(payStatement).toHaveBeenCalled());
    expect(payStatement.mock.calls[0][2].paid_amount).toBe(400);
  });

  it("tutar ekstreyi aşarsa → istemci tarafı doğrulama, payStatement çağrılmaz", async () => {
    render(<StatementPayModal cardId={2} statement={STATEMENT} onClose={vi.fn()} onPaid={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByDisplayValue("partial"));
    const input = screen.getByLabelText(/content\.creditCards\.pay\.amountLabel/) as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "5000");
    // input max=statement_amount native kısıtlaması submit'i bloklayabilir;
    // JS guard'ını doğrulamak için form'u doğrudan submit et.
    fireEvent.submit(input.closest("form")!);
    expect(payStatement).not.toHaveBeenCalled();
    expect(await screen.findByText("content.creditCards.pay.amountInvalid")).toBeInTheDocument();
  });

  it("backend 422 hatası → hata mesajı gösterilir", async () => {
    payStatement.mockRejectedValueOnce(new Error("422 tutar geçersiz"));
    render(<StatementPayModal cardId={2} statement={STATEMENT} onClose={vi.fn()} onPaid={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.creditCards.pay.submit"));
    expect(await screen.findByText("422 tutar geçersiz")).toBeInTheDocument();
  });
});
