import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = { setup: () => userEventLib.setup({ delay: null }) };

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/Money", () => ({
  Money: ({ tl }: { tl: number | string }) => <span>{String(tl)}</span>,
  DisplayMoney: ({ value }: { value: number | string }) => <span>{String(value)}</span>,
  fmtCurrency: (v: number | string) => `₺${Number(v).toFixed(2)}`,
  formatTlAs: (v: number) => `₺${v}`,
  useRates: () => null,
  useDisplayCurrency: () => "TRY",
}));

import { Card } from "@/app/dashboard/_components/DashboardCard";

const baseProps = {
  href: "/dashboard/manual-crypto",
  icon: "crypto" as const,
  color: "orange",
  title: "Manuel Kripto",
  total: 1000,
  top: [],
  placeholder: "—",
  onRefresh: vi.fn(),
};

describe("DashboardCard — uyarı ikonu (⚠)", () => {
  it("warnings boşsa ⚠ ikonu görünmez", () => {
    render(<Card {...baseProps} warnings={[]} />);
    expect(screen.queryByLabelText(/dashboard.cardWarning/)).not.toBeInTheDocument();
  });

  it("warnings doluysa ⚠ ikonu görünür; tıklayınca mesajlar açılır", async () => {
    const user = userEvent.setup();
    render(<Card {...baseProps} warnings={["XAGX: fiyatı çekilemedi/bulunamadı"]} />);

    const warnBtn = screen.getByLabelText(/dashboard.cardWarning/);
    expect(warnBtn).toBeInTheDocument();
    // hover ipucu (title) mesajı içerir
    expect(warnBtn).toHaveAttribute("title", expect.stringContaining("XAGX"));

    // popover kapalı
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.click(warnBtn);
    // popover açılır + mesaj görünür
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByText("XAGX: fiyatı çekilemedi/bulunamadı")).toBeInTheDocument();
  });
});
