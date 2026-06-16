import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/api", () => ({}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

// fmtCurrency saf bir formatter; deterministik çıktı için stub'la.
vi.mock("@/app/_components/Money", () => ({
  fmtCurrency: (v: string | number, c: string) => `${v} ${c}`,
}));

import { SubscriptionsAsPlanned } from "@/app/dashboard/expenses/_components/SubscriptionsAsPlanned";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const sub = (over: Record<string, unknown> = {}): any => ({
  id: 1,
  provider_code: "esgaz",
  provider_name: "ESGAZ",
  category: "gas",
  subscriber_no: "12345",
  label: "Ev",
  budget_amount: "500",
  currency: "TRY",
  start_date: "2026-01-01",
  active: true,
  current_status: "budget",
  current_amount: "500",
  ...over,
});

describe("SubscriptionsAsPlanned", () => {
  it("aktif aboneliğin yokken null render eder (boş)", () => {
    const { container } = render(
      <SubscriptionsAsPlanned items={[sub({ active: false })]} onGoToSubscriptions={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("aktif aboneliği bütçe tutarıyla salt-okunur listeler", () => {
    render(<SubscriptionsAsPlanned items={[sub()]} onGoToSubscriptions={vi.fn()} />);
    expect(screen.getByText("content.subscriptions.asPlannedTitle")).toBeInTheDocument();
    expect(screen.getByText("Ev")).toBeInTheDocument();
    expect(screen.getByText("500 TRY")).toBeInTheDocument();
  });

  it("satıra tıklayınca onGoToSubscriptions çağrılır", async () => {
    const go = vi.fn();
    render(<SubscriptionsAsPlanned items={[sub()]} onGoToSubscriptions={go} />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByText("Ev"));
    expect(go).toHaveBeenCalled();
  });
});
