import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const getRecurringPeriods = vi.fn();
const realizeRecurringPeriod = vi.fn();
const unrealizeRecurringPeriod = vi.fn();
const skipRecurring = vi.fn();
const unskipRecurring = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getRecurringPeriods: (...a: unknown[]) => getRecurringPeriods(...a),
    realizeRecurringPeriod: (...a: unknown[]) => realizeRecurringPeriod(...a),
    unrealizeRecurringPeriod: (...a: unknown[]) => unrealizeRecurringPeriod(...a),
    skipRecurring: (...a: unknown[]) => skipRecurring(...a),
    unskipRecurring: (...a: unknown[]) => unskipRecurring(...a),
  },
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { RecurringPeriodsModal } from "@/app/dashboard/income/_components/RecurringPeriodsModal";
import type { RecurringIncomeDTO, RecurringPeriodStatusDTO } from "@/lib/api";

const RI = { id: 5, title: "Maaş", amount: "50000", category: "salary", recurrence: "monthly" } as unknown as RecurringIncomeDTO;

function periods(): RecurringPeriodStatusDTO[] {
  return [
    { year: 2026, month: 3, target_date: "2026-03-01", status: "skipped", income_id: null, skip_id: 11 },
    { year: 2026, month: 2, target_date: "2026-02-01", status: "realized", income_id: 88, skip_id: null },
    { year: 2026, month: 1, target_date: "2026-01-01", status: "pending", income_id: null, skip_id: null },
  ];
}

describe("RecurringPeriodsModal", () => {
  beforeEach(() => {
    getRecurringPeriods.mockReset().mockResolvedValue({ periods: periods() });
    realizeRecurringPeriod.mockReset().mockResolvedValue({ realized: 1, skipped: 0 });
    unrealizeRecurringPeriod.mockReset().mockResolvedValue({ removed: 1 });
    skipRecurring.mockReset().mockResolvedValue({ id: 11 });
    unskipRecurring.mockReset().mockResolvedValue(undefined);
    HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
      this.open = false;
    });
  });

  it("dönemleri yükler ve durumları gösterir", async () => {
    render(<RecurringPeriodsModal ri={RI} onClose={vi.fn()} />);
    await waitFor(() => expect(getRecurringPeriods).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/periods\.realized$/)).toBeInTheDocument();
    expect(screen.getByText(/periods\.skipped$/)).toBeInTheDocument();
    expect(screen.getByText(/periods\.pending$/)).toBeInTheDocument();
  });

  it("realized dönemde 'Geri al' → unrealizeRecurringPeriod çağrılır", async () => {
    render(<RecurringPeriodsModal ri={RI} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.realized$/);
    // DOM sırası newest-first: [skipped 2026-3, realized 2026-2]. undos[1] realized.
    const undos = screen.getAllByText("content.planned.periods.undo");
    await user.click(undos[1]);
    await waitFor(() => expect(unrealizeRecurringPeriod).toHaveBeenCalledWith(5, 2026, 2));
  });

  it("skipped dönemde 'Geri al' → unskipRecurring(skip_id) çağrılır", async () => {
    render(<RecurringPeriodsModal ri={RI} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.realized$/);
    const undos = screen.getAllByText("content.planned.periods.undo");
    await user.click(undos[0]);
    await waitFor(() => expect(unskipRecurring).toHaveBeenCalledWith(11));
  });

  it("pending dönemde 'Gerçekleşti' → realizeRecurringPeriod çağrılır", async () => {
    render(<RecurringPeriodsModal ri={RI} onClose={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    await screen.findByText(/periods\.pending$/);
    await user.click(screen.getByText("content.planned.periods.markRealized"));
    await waitFor(() => expect(realizeRecurringPeriod).toHaveBeenCalledWith(5, 2026, 1));
  });
});
