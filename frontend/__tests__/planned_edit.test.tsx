import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const updatePlannedExpense = vi.fn();
const createPlannedExpense = vi.fn();
const deletePlannedExpense = vi.fn();
const listCreditCards = vi.fn();
const getUsdRate = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      updatePlannedExpense: (...a: unknown[]) => updatePlannedExpense(...a),
      createPlannedExpense: (...a: unknown[]) => createPlannedExpense(...a),
      deletePlannedExpense: (...a: unknown[]) => deletePlannedExpense(...a),
      listCreditCards: (...a: unknown[]) => listCreditCards(...a),
      getUsdRate: (...a: unknown[]) => getUsdRate(...a),
    },
  };
});

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

// useConfirm → her zaman onaylar (silme testi için)
vi.mock("@/app/_components/ConfirmDialog", () => ({
  useConfirm: () => () => Promise.resolve(true),
}));

// Dönemler modalı testi kapsamı dışı — basit stub
vi.mock("@/app/dashboard/planned/_components/PlannedPeriodsModal", () => ({
  PlannedPeriodsModal: () => null,
}));

import { PlannedForm } from "@/app/dashboard/planned/_components/PlannedForm";
import { PlannedList } from "@/app/dashboard/planned/_components/PlannedList";
import type { PlannedExpenseDTO } from "@/lib/api";

const PE: PlannedExpenseDTO = {
  id: 42,
  title: "Ev Aidatı",
  amount: "1500",
  is_estimated: false,
  category: "rent",
  recurrence: "monthly",
  months: null,
  day_of_month: 5,
  start_date: "2026-01-05",
  end_date: null,
  remaining_count: null,
  notes: null,
  credit_card_id: null,
  is_paid: false,
  currency: "TRY",
};

describe("PlannedForm edit modu", () => {
  beforeEach(() => {
    updatePlannedExpense.mockReset().mockResolvedValue({ ...PE, title: "Ev Aidatı (güncel)" });
    createPlannedExpense.mockReset().mockResolvedValue(PE);
    listCreditCards.mockReset().mockResolvedValue({ cards: [] });
    getUsdRate.mockReset().mockResolvedValue(null);
  });

  it("existing dolu → form ön-doldurulur ve submit updatePlannedExpense çağırır", async () => {
    const onSaved = vi.fn();
    render(<PlannedForm existing={PE} onSaved={onSaved} onCancel={vi.fn()} />);

    // Edit modunda form doğrudan açık — başlık değeri yüklü
    const titleInput = (await screen.findByDisplayValue("Ev Aidatı")) as HTMLInputElement;
    expect(titleInput).toBeTruthy();
    expect(screen.getByDisplayValue("1500")).toBeTruthy();

    // Güncelle butonu (form.update key'i stub'lanır)
    await userEvent.click(screen.getByRole("button", { name: "form.update" }));

    await waitFor(() => expect(updatePlannedExpense).toHaveBeenCalledTimes(1));
    expect(updatePlannedExpense.mock.calls[0][0]).toBe(42);
    expect(createPlannedExpense).not.toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("onCancel düzenlemeyi iptal eder", async () => {
    const onCancel = vi.fn();
    render(<PlannedForm existing={PE} onSaved={vi.fn()} onCancel={onCancel} />);
    await screen.findByDisplayValue("Ev Aidatı");
    await userEvent.click(screen.getByRole("button", { name: "common.cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe("PlannedList düzenleme butonu", () => {
  beforeEach(() => {
    getUsdRate.mockReset().mockResolvedValue(null);
  });

  it("Düzenle butonu onEdit'i ilgili kayıtla çağırır", async () => {
    const onEdit = vi.fn();
    render(<PlannedList items={[PE]} onDeleted={vi.fn()} onEdit={onEdit} />);

    await userEvent.click(screen.getByRole("button", { name: "common.edit" }));
    expect(onEdit).toHaveBeenCalledWith(PE);
  });
});
