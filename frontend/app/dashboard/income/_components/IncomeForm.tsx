"use client";
import { useState } from "react";
import { api, IncomeInput, IncomeDTO, INCOME_CATEGORIES, INCOME_CATEGORY_LABELS } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";

interface Props {
  onAdded: (inc: IncomeDTO) => void;
}

const TODAY = new Date().toISOString().slice(0, 10);

export function IncomeForm({ onAdded }: Props) {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState<IncomeInput["category"]>("salary");
  const [date, setDate] = useState(TODAY);
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const result = await api.createIncome({
        amount: parseFloat(amount),
        category,
        date,
        description: description.trim() || null,
      });
      onAdded(result);
      setAmount("");
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Gelir ekle</h3>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
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
        <div>
          <label className="block text-xs text-gray-500 mb-1">Kategori</label>
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
          <label className="block text-xs text-gray-500 mb-1">Tarih</label>
          <input
            type="date"
            required
            className={INPUT_CLS}
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Açıklama</label>
          <input
            className={INPUT_CLS}
            placeholder="opsiyonel"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
          />
        </div>
      </div>
      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="mt-4 text-sm bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
      >
        {saving ? "Kaydediliyor..." : "Ekle"}
      </button>
    </form>
  );
}
