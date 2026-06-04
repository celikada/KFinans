import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const realizeRecurringPeriod = vi.fn();
const realizePlannedPeriod = vi.fn();
const skipRecurring = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    realizeRecurringPeriod: (...a: unknown[]) => realizeRecurringPeriod(...a),
    realizePlannedPeriod: (...a: unknown[]) => realizePlannedPeriod(...a),
    skipRecurring: (...a: unknown[]) => skipRecurring(...a),
  },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { PendingRealizeModal } from "@/app/dashboard/_components/PendingRealizeModal";
import type { PendingItemDTO } from "@/lib/api";

const ITEMS: PendingItemDTO[] = [
  { kind: "income", ref_id: 1, title: "Maaş", category: "salary", amount: "40000", period_year: 2026, period_month: 1, occurrence_date: "2026-01-01" },
  { kind: "expense", ref_id: 2, title: "Kira", category: "rent", amount: "5000", period_year: 2026, period_month: 1, occurrence_date: "2026-01-01" },
];

describe("PendingRealizeModal", () => {
  beforeEach(() => {
    realizeRecurringPeriod.mockReset().mockResolvedValue({ realized: 1, skipped: 0 });
    realizePlannedPeriod.mockReset().mockResolvedValue({ realized: 1, skipped: 0 });
    skipRecurring.mockReset().mockResolvedValue({ id: 99 });
    // jsdom <dialog>.showModal/close desteklemez → native Modal için mock'la.
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("gelir 'Gerçekleşti' → realizeRecurringPeriod çağrılır + satır düşer", async () => {
    const onClose = vi.fn();
    render(<PendingRealizeModal items={ITEMS} onClose={onClose} />);
    const user = userEvent.setup({ delay: null });

    expect(screen.getByText("Maaş")).toBeInTheDocument();
    // İlk satır (gelir) "Gerçekleşti" butonu
    const realizeButtons = screen.getAllByText("content.pending.realized");
    await user.click(realizeButtons[0]);

    await waitFor(() => expect(realizeRecurringPeriod).toHaveBeenCalledWith(1, 2026, 1));
    await waitFor(() => expect(screen.queryByText("Maaş")).not.toBeInTheDocument());
    expect(onClose).not.toHaveBeenCalled(); // hâlâ gider satırı var
  });

  it("gider 'Gerçekleşmeyecek' → skipRecurring çağrılır", async () => {
    const onClose = vi.fn();
    render(<PendingRealizeModal items={ITEMS} onClose={onClose} />);
    const user = userEvent.setup({ delay: null });

    const skipButtons = screen.getAllByText("content.pending.skip");
    await user.click(skipButtons[1]); // gider satırı

    await waitFor(() => expect(skipRecurring).toHaveBeenCalledWith("expense", 2, 2026, 1));
    await waitFor(() => expect(screen.queryByText("Kira")).not.toBeInTheDocument());
  });

  it("son satır işlenince onClose çağrılır", async () => {
    const onClose = vi.fn();
    render(<PendingRealizeModal items={[ITEMS[0]]} onClose={onClose} />);
    const user = userEvent.setup({ delay: null });

    await user.click(screen.getByText("content.pending.realized"));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
