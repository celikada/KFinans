import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const getProviders = vi.fn();
const createSubscription = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getProviders: (...a: unknown[]) => getProviders(...a),
    createSubscription: (...a: unknown[]) => createSubscription(...a),
  },
  // Form, CURRENCIES sabitini de tüketir.
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/lib/defaultCurrency", () => ({ getDefaultCurrency: () => "TRY" }));

import { SubscriptionForm } from "@/app/dashboard/expenses/_components/SubscriptionForm";

describe("SubscriptionForm", () => {
  beforeEach(() => {
    getProviders.mockReset().mockResolvedValue([
      { code: "esgaz", name: "ESGAZ", category: "gas" },
      { code: "ttnet", name: "TTNET", category: "internet" },
    ]);
    createSubscription.mockReset().mockResolvedValue({ id: 5 });
  });

  it("create modunda toggle ile açılır ve provider'ları yükler", async () => {
    render(<SubscriptionForm onSaved={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.subscriptions.toggleOpen"));
    await waitFor(() => expect(getProviders).toHaveBeenCalled());
    // Provider opsiyonları render edilir (kategori adıyla birlikte).
    expect(await screen.findByText(/ESGAZ/)).toBeInTheDocument();
    expect(screen.getByText(/TTNET/)).toBeInTheDocument();
  });

  it("form doldurup gönderince createSubscription doğru payload ile çağrılır", async () => {
    const onSaved = vi.fn();
    render(<SubscriptionForm onSaved={onSaved} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("content.subscriptions.toggleOpen"));
    await waitFor(() => expect(getProviders).toHaveBeenCalled());

    await user.selectOptions(screen.getByLabelText("content.subscriptions.providerLabel"), "esgaz");
    await user.type(screen.getByLabelText("content.subscriptions.subscriberNoLabel"), "98765");
    await user.type(screen.getByPlaceholderText("form.amountPlaceholder"), "450");
    await user.click(screen.getByText("form.save"));

    await waitFor(() => expect(createSubscription).toHaveBeenCalled());
    const payload = createSubscription.mock.calls[0][0];
    expect(payload.provider_code).toBe("esgaz");
    expect(payload.subscriber_no).toBe("98765");
    expect(payload.budget_amount).toBe(450);
    expect(payload.currency).toBe("TRY");
    expect(onSaved).toHaveBeenCalledWith({ id: 5 });
  });
});
