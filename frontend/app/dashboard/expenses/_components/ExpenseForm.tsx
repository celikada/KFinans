"use client";
import { useEffect, useState } from "react";
import {
  api,
  CreditCardDTO,
  ExpenseCategory,
  EXPENSE_CATEGORIES,
  EXPENSE_CATEGORY_LABELS,
  ExpenseDTO,
} from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  onSaved: (expense: ExpenseDTO) => void;
  /** Doluysa edit modu */
  existing?: ExpenseDTO | null;
  onCancel?: () => void;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ExpenseForm({ onSaved, existing, onCancel }: Readonly<Props>) {
  const { t } = useTranslation();
  const isEdit = !!existing;
  const [amount, setAmount] = useState(existing?.amount ?? "");
  const [category, setCategory] = useState<ExpenseCategory>(existing?.category ?? "groceries");
  const [date, setDate] = useState(existing?.date ?? todayIso());
  const [description, setDescription] = useState(existing?.description ?? "");
  const [creditCardId, setCreditCardId] = useState<string>(existing?.credit_card_id ? existing.credit_card_id.toString() : "");
  const [cards, setCards] = useState<CreditCardDTO[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Mevcut kartları çek (tek seferlik)
  useEffect(() => {
    api.listCreditCards().then((s) => setCards(s.cards)).catch(() => {});
  }, []);

  // existing değişirse formu yenile
  useEffect(() => {
    if (existing) {
      setAmount(existing.amount);
      setCategory(existing.category);
      setDate(existing.date);
      setDescription(existing.description ?? "");
      setCreditCardId(existing.credit_card_id ? existing.credit_card_id.toString() : "");
    }
  }, [existing]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const value = Number.parseFloat(amount);
    if (!value || value <= 0) { setError(t("form.amountInvalid")); return; }
    setSaving(true);
    try {
      const payload = {
        amount: value,
        category,
        date,
        description: description.trim() || null,
        credit_card_id: creditCardId ? Number.parseInt(creditCardId) : null,
        is_paid: true,
      };
      const result = isEdit && existing
        ? await api.updateExpense(existing.id, payload)
        : await api.createExpense(payload);
      onSaved(result);
      if (!isEdit) {
        setAmount("");
        setDescription("");
        setCreditCardId("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">{isEdit ? t("form.expenseEdit") : t("form.expenseNew")}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("form.amountTL")}</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={t("form.amountPlaceholder")}
            className={`w-full text-right ${INPUT_CLS}`}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.category")}</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as ExpenseCategory)}
            className={`w-full ${INPUT_CLS}`}
          >
            {EXPENSE_CATEGORIES.map((c) => (
              <option key={c} value={c}>{EXPENSE_CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.date")}</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={`w-full ${INPUT_CLS}`}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.description")}</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("form.optional")}
            maxLength={500}
            className={`w-full ${INPUT_CLS}`}
          />
        </div>
      </div>

      {/* Kredi kartı seçimi (opsiyonel) */}
      {cards.length > 0 && (
        <div className="mt-3">
          <label className="block text-xs text-gray-500 mb-1">
            {t("form.paymentMethod")}
            <span className="ml-1 text-[10px] text-gray-400">{t("form.paymentMethodHint")}</span>
          </label>
          <select
            value={creditCardId}
            onChange={(e) => setCreditCardId(e.target.value)}
            className={`w-full sm:w-1/2 ${INPUT_CLS}`}
          >
            <option value="">{t("form.cashOrTransfer")}</option>
            {cards.map((c) => (
              <option key={c.id} value={c.id}>
                💳 {c.name}{c.last_4 ? ` (**** ${c.last_4})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
      )}

      {(() => {
        let submitLabel: string;
        if (saving) submitLabel = t("form.saving");
        else if (isEdit) submitLabel = t("form.update");
        else submitLabel = t("form.add");
        return (
          <div className="mt-4 flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {submitLabel}
            </button>
            {isEdit && onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-sm border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50"
              >
                {t("common.cancel")}
              </button>
            )}
          </div>
        );
      })()}
    </form>
  );
}
