import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const getPlannedPeriods = vi.fn();
const realizePlannedPeriod = vi.fn();
const unrealizePlannedPeriod = vi.fn();
const skipRecurring = vi.fn();
const unskipRecurring = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getPlannedPeriods: (...a: unknown[]) => getPlannedPeriods(...a),
    realizePlannedPeriod: (...a: unknown[]) => realizePlannedPeriod(...a),
    unrealizePlannedPeriod: (...a: unknown[]) => unrealizePlannedPeriod(...a),
    skipRecurring: (...a: unknown[]) => skipRecurring(...a),
    unskipRecurring: (...a: unknown[]) => unskipRecurring(...a),
  },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { PlannedPeriodsModal } from "@/app/dashboard/planned/_components/PlannedPeriodsModal";
import type { PlannedExpenseDTO, PeriodStatusDTO } from "@/lib/api";

const PE = { id: 7, title: "Kira", amount: "5000", category: "rent", recurrence: "monthly" } as unknown as PlannedExpenseDTO;

function periods(): PeriodStatusDTO[] {
  return [
    { year: 2026, month: 3, target_date: "2026-03-15", status: "skipped", expense_id: null, skip_id: 9 },
    { year: 2026, month: 2, target_date: "2026-02-15", status: "realized", expense_id: 42, skip_id: null },
    { year: 2026, month: 1, target_date: "2026-01-15", status: "pending", expense_id: null, skip_id: null },
  ];
}

describe("PlannedPeriodsModal", () => {
  beforeEach(() => {
    getPlannedPeriods.mockReset().mockResolvedValue({ periods: periods() });
    realizePlannedPeriod.mockReset().mockResolvedValue({ realized: 1, skipped: 0 });
    unrealizePlannedPeriod.mockReset().mockResolvedValue({ removed: 1 });
    skipRecurring.mockReset().mockResolvedValue({ id: 9 });
    unskipRecurring.mockReset().mockResolvedValue(undefined);
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("dönemleri yükler ve durumları gösterir", async () => {
    render(<PlannedPeriodsModal pe={PE} onClose={vi.fn()} />);
    await waitFor(() => expect(getPlannedPeriods).toHaveBeenCalledWith(7));
    // realized + skipped + pending durum metinleri görünür (✓/✕/• prefix'li)
    expect(await screen.findByText(/periods\.realized$/)).toBeInTheDocument();
    expect(screen.getByText(/periods\.skipped$/)).toBeInTheDocument();
    expect(screen.getByText(/periods\.pending$/)).toBeInTheDocument();
  });

  it("realized dönemde 'Geri al' → unrealizePlannedPeriod çağrılır", async () => {
    render(<PlannedPeriodsModal pe={PE} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.realized$/);

    // DOM sırası newest-first: [skipped 2026-3, realized 2026-2]. undos[1] realized.
    const undos = screen.getAllByText("content.planned.periods.undo");
    await user.click(undos[1]);
    await waitFor(() => expect(unrealizePlannedPeriod).toHaveBeenCalledWith(7, 2026, 2));
  });

  it("skipped dönemde 'Geri al' → unskipRecurring(skip_id) çağrılır", async () => {
    render(<PlannedPeriodsModal pe={PE} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.realized$/);

    const undos = screen.getAllByText("content.planned.periods.undo");
    // İlk "Geri al" skipped döneme ait (2026-3, skip_id=9)
    await user.click(undos[0]);
    await waitFor(() => expect(unskipRecurring).toHaveBeenCalledWith(9));
  });

  it("pending dönemde 'Gerçekleşti' → realizePlannedPeriod çağrılır", async () => {
    render(<PlannedPeriodsModal pe={PE} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.pending$/);

    await user.click(screen.getByText("content.planned.periods.markRealized"));
    await waitFor(() => expect(realizePlannedPeriod).toHaveBeenCalledWith(7, 2026, 1));
  });
});
