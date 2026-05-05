"use client";
import { useEffect, useState } from "react";
import {
  api,
  RecurringIncomeDTO,
  RecurringIncomeInput,
  RecurringIncomeCategory,
  RecurringRecurrence,
  RECURRING_INCOME_CATEGORY_LABELS,
  RECURRING_RECURRENCE_LABELS,
} from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";

interface Props {
  onSaved: (ri: RecurringIncomeDTO) => void;
  /** Doluysa edit modunda; boşsa create */
  existing?: RecurringIncomeDTO | null;
  onCancel?: () => void;
}

const TODAY = new Date().toISOString().slice(0, 10);
const CATEGORIES: RecurringIncomeCategory[] = ["salary", "rental", "dividend", "bonus", "freelance", "other"];
const RECURRENCES: RecurringRecurrence[] = ["one_time", "monthly", "quarterly", "biannual", "yearly", "custom"];
const MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export function RecurringIncomeForm({ onSaved, existing, onCancel }: Props) {
  const isEdit = !!existing;
  const [title, setTitle] = useState(existing?.title ?? "");
  const [amount, setAmount] = useState(existing?.amount ?? "");
  const [category, setCategory] = useState<RecurringIncomeCategory>(existing?.category ?? "salary");
  const [recurrence, setRecurrence] = useState<RecurringRecurrence>(existing?.recurrence ?? "monthly");
  const [months, setMonths] = useState<number[]>(existing?.months ?? []);
  const [dayOfMonth, setDayOfMonth] = useState(existing?.day_of_month?.toString() ?? "1");
  const [startDate, setStartDate] = useState(existing?.start_date ?? TODAY);
  const [endDate, setEndDate] = useState(existing?.end_date ?? "");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // existing değişirse formu yenile
  useEffect(() => {
    if (existing) {
      setTitle(existing.title);
      setAmount(existing.amount);
      setCategory(existing.category);
      setRecurrence(existing.recurrence);
      setMonths(existing.months ?? []);
      setDayOfMonth(existing.day_of_month.toString());
      setStartDate(existing.start_date);
      setEndDate(existing.end_date ?? "");
      setNotes(existing.notes ?? "");
    }
  }, [existing]);

  function toggleMonth(m: number) {
    setMonths((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m].sort((a, b) => a - b)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Başlık zorunlu");
      return;
    }
    if (recurrence === "custom" && months.length === 0) {
      setError("Özel aylar için en az bir ay seç");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: RecurringIncomeInput = {
        title: title.trim(),
        amount: parseFloat(amount),
        category,
        recurrence,
        months: recurrence === "custom" ? months : null,
        day_of_month: parseInt(dayOfMonth) || 1,
        start_date: startDate,
        end_date: endDate || null,
        notes: notes.trim() || null,
      };
      const result = isEdit && existing
        ? await api.updateRecurringIncome(existing.id, payload)
        : await api.createRecurringIncome(payload);
      onSaved(result);
      if (!isEdit) {
        setTitle("");
        setAmount("");
        setMonths([]);
        setDayOfMonth("1");
        setEndDate("");
        setNotes("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-700">{isEdit ? "Periyodik gelir düzenle" : "Periyodik gelir ekle"}</h3>
        <p className="text-xs text-gray-500 mt-0.5">Maaş, kira, temettü gibi düzenli gelirler. Yıl sonu beklentisi bunlardan hesaplanır.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">Başlık</label>
          <input
            required
            className={INPUT_CLS}
            placeholder="Maaş — XYZ A.Ş."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Tutar (₺)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            required
            className={INPUT_CLS}
            placeholder="50000"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Kategori</label>
          <select
            className={INPUT_CLS}
            value={category}
            onChange={(e) => setCategory(e.target.value as RecurringIncomeCategory)}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{RECURRING_INCOME_CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Periyot</label>
          <select
            className={INPUT_CLS}
            value={recurrence}
            onChange={(e) => setRecurrence(e.target.value as RecurringRecurrence)}
          >
            {RECURRENCES.map((r) => (
              <option key={r} value={r}>{RECURRENCE_LABELS_LOCAL[r]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Ayın günü (1-28)</label>
          <input
            type="number"
            min="1"
            max="28"
            className={INPUT_CLS}
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(e.target.value)}
          />
        </div>
      </div>

      {recurrence === "custom" && (
        <div>
          <label className="block text-xs text-gray-500 mb-2">Hangi aylar?</label>
          <div className="grid grid-cols-6 sm:grid-cols-12 gap-1">
            {MONTH_NAMES.map((name, i) => {
              const m = i + 1;
              const isOn = months.includes(m);
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => toggleMonth(m)}
                  className={`text-xs px-2 py-1.5 rounded border ${
                    isOn ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
                  }`}
                >
                  {name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Başlangıç</label>
          <input
            type="date"
            required
            className={INPUT_CLS}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Bitiş (opsiyonel — boş = süresiz)</label>
          <input
            type="date"
            className={INPUT_CLS}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">Notlar (opsiyonel)</label>
        <input
          className={INPUT_CLS}
          placeholder="Bordro, vergi sonrası net..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={500}
        />
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}
      {(() => {
        let submitLabel: string;
        if (saving) submitLabel = "Kaydediliyor...";
        else if (isEdit) submitLabel = "Güncelle";
        else submitLabel = "Ekle";
        return (
      <div className="flex items-center gap-2">
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
            İptal
          </button>
        )}
      </div>
        );
      })()}
    </form>
  );
}

const RECURRENCE_LABELS_LOCAL: Record<RecurringRecurrence, string> = RECURRING_RECURRENCE_LABELS;
