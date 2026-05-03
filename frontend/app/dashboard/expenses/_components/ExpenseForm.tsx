"use client";
import { useState } from "react";
import {
  api,
  ExpenseCategory,
  EXPENSE_CATEGORIES,
  EXPENSE_CATEGORY_LABELS,
  ExpenseDTO,
} from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";

interface Props {
  onAdded: (expense: ExpenseDTO) => void;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ExpenseForm({ onAdded }: Props) {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState<ExpenseCategory>("groceries");
  const [date, setDate] = useState(todayIso());
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const value = parseFloat(amount);
    if (!value || value <= 0) { setError("Geçerli bir tutar girin"); return; }
    setSaving(true);
    try {
      const added = await api.createExpense({
        amount: value,
        category,
        date,
        description: description.trim() || null,
      });
      onAdded(added);
      setAmount("");
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Yeni Harcama</h2>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Tutar (₺)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0,00"
            className={`w-full text-right ${INPUT_CLS}`}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Kategori</label>
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
          <label className="block text-xs text-gray-500 mb-1">Tarih</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={`w-full ${INPUT_CLS}`}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Açıklama</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Opsiyonel"
            maxLength={500}
            className={`w-full ${INPUT_CLS}`}
          />
        </div>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="mt-4 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {saving ? "Ekleniyor..." : "Ekle"}
      </button>
    </form>
  );
}
