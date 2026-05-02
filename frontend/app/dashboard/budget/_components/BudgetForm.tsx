"use client";
import { useState } from "react";
import { api, EXPENSE_CATEGORIES, EXPENSE_CATEGORY_LABELS } from "@/lib/api";

interface Props {
  onSaved: () => void;
}

export function BudgetForm({ onSaved }: Props) {
  const [category, setCategory] = useState<string>(EXPENSE_CATEGORIES[0]);
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const val = parseFloat(amount);
    if (!val || val <= 0) { setError("Geçerli bir tutar girin"); return; }
    setSaving(true);
    setError("");
    try {
      await api.upsertBudget(category, val);
      setAmount("");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Bütçe Limiti Belirle</h2>
      <div className="flex flex-wrap gap-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="flex-1 min-w-[160px] border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {EXPENSE_CATEGORIES.map((c) => (
            <option key={c} value={c}>{EXPENSE_CATEGORY_LABELS[c]}</option>
          ))}
        </select>
        <div className="flex items-center border border-gray-200 rounded-xl px-3 py-2 flex-1 min-w-[140px]">
          <input
            type="number"
            min="1"
            step="0.01"
            placeholder="Aylık limit (₺)"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="flex-1 text-sm focus:outline-none"
          />
          <span className="text-gray-400 text-sm ml-1">₺</span>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-xl transition-colors"
        >
          {saving ? "Kaydediliyor..." : "Kaydet"}
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
    </form>
  );
}
