"use client";
import { useEffect, useState } from "react";
import { api, IncomeInput, IncomeDTO, INCOME_CATEGORIES, INCOME_CATEGORY_LABELS } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  onSaved: (inc: IncomeDTO) => void;
  /** Doluysa edit modu */
  existing?: IncomeDTO | null;
  onCancel?: () => void;
}

const TODAY = new Date().toISOString().slice(0, 10);

export function IncomeForm({ onSaved, existing, onCancel }: Readonly<Props>) {
  const { t } = useTranslation();
  const isEdit = !!existing;
  const [amount, setAmount] = useState(existing?.amount ?? "");
  const [category, setCategory] = useState<IncomeInput["category"]>(existing?.category ?? "salary");
  const [date, setDate] = useState(existing?.date ?? TODAY);
  const [description, setDescription] = useState(existing?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (existing) {
      setAmount(existing.amount);
      setCategory(existing.category);
      setDate(existing.date);
      setDescription(existing.description ?? "");
    }
  }, [existing]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        amount: Number.parseFloat(amount),
        category,
        date,
        description: description.trim() || null,
      };
      const result = isEdit && existing
        ? await api.updateIncome(existing.id, payload)
        : await api.createIncome(payload);
      onSaved(result);
      if (!isEdit) {
        setAmount("");
        setDescription("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">{isEdit ? t("form.incomeEdit") : t("form.incomeNew")}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("form.amountTL")}</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            required
            className={INPUT_CLS}
            placeholder={t("form.amountPlaceholder")}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.category")}</label>
          <select
            className={INPUT_CLS}
            value={category}
            onChange={(e) => setCategory(e.target.value as IncomeInput["category"])}
          >
            {INCOME_CATEGORIES.map((c) => (
              <option key={c} value={c}>{INCOME_CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.date")}</label>
          <input
            type="date"
            required
            className={INPUT_CLS}
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t("table.description")}</label>
          <input
            className={INPUT_CLS}
            placeholder={t("form.optional")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
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
          className="text-sm bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          {submitLabel}
        </button>
        {isEdit && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-sm px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50"
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
