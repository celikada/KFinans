"use client";
import { useEffect, useState } from "react";
import {
  api,
  CreditCardDTO,
  PlannedExpenseInput,
  PlannedExpenseDTO,
  PLANNED_CATEGORIES,
  PLANNED_CATEGORY_LABELS,
  PLANNED_RECURRENCES,
  PLANNED_RECURRENCE_LABELS,
  MONTH_NAMES,
} from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  onAdded: (pe: PlannedExpenseDTO) => void;
}

const TODAY = new Date().toISOString().slice(0, 10);

export function PlannedForm({ onAdded }: Readonly<Props>) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState<PlannedExpenseInput["category"]>("loan");
  const [recurrence, setRecurrence] = useState<PlannedExpenseInput["recurrence"]>("monthly");
  const [isEstimated, setIsEstimated] = useState(false);
  const [startDate, setStartDate] = useState(TODAY);
  const [endDate, setEndDate] = useState("");
  const [remainingCount, setRemainingCount] = useState("");
  const [dayOfMonth, setDayOfMonth] = useState("1");
  const [customMonths, setCustomMonths] = useState<number[]>([]);
  const [notes, setNotes] = useState("");
  const [creditCardId, setCreditCardId] = useState<string>("");
  const [isPaid, setIsPaid] = useState(false);
  const [cards, setCards] = useState<CreditCardDTO[]>([]);

  useEffect(() => {
    api.listCreditCards().then((s) => setCards(s.cards)).catch(() => {});
  }, []);

  function toggleMonth(m: number) {
    setCustomMonths((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m].sort((a, b) => a - b)
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload: PlannedExpenseInput = {
        title: title.trim(),
        amount: Number.parseFloat(amount),
        category,
        recurrence,
        is_estimated: isEstimated,
        start_date: startDate,
        day_of_month: Number.parseInt(dayOfMonth),
        end_date: endDate || null,
        remaining_count: remainingCount ? Number.parseInt(remainingCount) : null,
        months: recurrence === "custom" ? customMonths : null,
        notes: notes.trim() || null,
        credit_card_id: creditCardId ? Number.parseInt(creditCardId) : null,
        is_paid: isPaid,
      };
      const result = await api.createPlannedExpense(payload);
      onAdded(result);
      // reset
      setTitle(""); setAmount(""); setNotes(""); setEndDate(""); setRemainingCount("");
      setIsEstimated(false); setCustomMonths([]); setOpen(false);
      setCreditCardId(""); setIsPaid(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
      >
        {open ? t("form.plannedToggleClose") : t("form.plannedToggleOpen")}
      </button>

      {open && (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">{t("form.titleLabel")}</label>
              <input
                className={INPUT_CLS}
                placeholder={t("content.planned.titlePlaceholder")}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                maxLength={100}
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("form.amountTL")}</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                className={INPUT_CLS}
                placeholder={t("form.amountPlaceholder")}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("table.category")}</label>
              <select
                className={INPUT_CLS}
                value={category}
                onChange={(e) => setCategory(e.target.value as PlannedExpenseInput["category"])}
              >
                {PLANNED_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{PLANNED_CATEGORY_LABELS[c]}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("form.recurrence")}</label>
              <select
                className={INPUT_CLS}
                value={recurrence}
                onChange={(e) => setRecurrence(e.target.value as PlannedExpenseInput["recurrence"])}
              >
                {PLANNED_RECURRENCES.map((r) => (
                  <option key={r} value={r}>{PLANNED_RECURRENCE_LABELS[r]}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("form.dayOfMonth")}</label>
              <input
                type="number"
                min="1"
                max="28"
                className={INPUT_CLS}
                value={dayOfMonth}
                onChange={(e) => setDayOfMonth(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("form.startDate")}</label>
              <input
                type="date"
                className={INPUT_CLS}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>

            {recurrence === "monthly" && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("form.remainingInstallments")}</label>
                <input
                  type="number"
                  min="1"
                  className={INPUT_CLS}
                  placeholder={t("form.optional")}
                  value={remainingCount}
                  onChange={(e) => setRemainingCount(e.target.value)}
                />
              </div>
            )}

            {recurrence !== "monthly" && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("form.endDate")}</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  placeholder={t("form.optional")}
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            )}

            {recurrence === "custom" && (
              <div className="sm:col-span-2">
                <label className="block text-xs text-gray-500 mb-2">{t("form.whichMonths")}</label>
                <div className="flex flex-wrap gap-2">
                  {MONTH_NAMES.map((name, idx) => {
                    const m = idx + 1;
                    const active = customMonths.includes(m);
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => toggleMonth(m)}
                        className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                          active
                            ? "bg-indigo-600 text-white border-indigo-600"
                            : "bg-white text-gray-600 border-gray-200 hover:border-indigo-300"
                        }`}
                      >
                        {name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="sm:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">{t("form.notes")}</label>
              <input
                className={INPUT_CLS}
                placeholder={t("form.optional")}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
              />
            </div>

            <div className="sm:col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                id="is_estimated"
                checked={isEstimated}
                onChange={(e) => setIsEstimated(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="is_estimated" className="text-xs text-gray-500">
                {t("form.amountEstimated")}
              </label>
            </div>

            {/* Kredi kartı + ödendi durumu */}
            {cards.length > 0 && (
              <div className="sm:col-span-2 space-y-2">
                <div>
                  <label htmlFor="credit_card" className="block text-xs text-gray-500 mb-1">
                    {t("form.paymentMethod")}
                    <span className="ml-1 text-[10px] text-gray-400">
                      {t("form.paymentMethodHintPlanned")}
                    </span>
                  </label>
                  <select
                    id="credit_card"
                    value={creditCardId}
                    onChange={(e) => setCreditCardId(e.target.value)}
                    className={INPUT_CLS}
                  >
                    <option value="">{t("form.cashOrTransfer")}</option>
                    {cards.map((c) => (
                      <option key={c.id} value={c.id}>
                        💳 {c.name}{c.last_4 ? ` (**** ${c.last_4})` : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_paid"
                    checked={isPaid}
                    onChange={(e) => setIsPaid(e.target.checked)}
                    className="rounded"
                  />
                  <label htmlFor="is_paid" className="text-xs text-gray-500">
                    {t("form.paidLabel")}
                  </label>
                </div>
              </div>
            )}
          </div>

          {error && <p className="text-xs text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saving ? t("form.saving") : t("form.save")}
          </button>
        </form>
      )}
    </div>
  );
}
