"use client";
import { useState } from "react";
import { api, EXPENSE_CATEGORY_LABELS, ExpenseDTO } from "@/lib/api";
import { fmtTL } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";

interface Props {
  expenses: ExpenseDTO[];
  onDeleted: (id: number) => void;
}

export function ExpenseTable({ expenses, onDeleted }: Props) {
  const [removing, setRemoving] = useState<number | null>(null);

  async function handleDelete(id: number) {
    if (!confirm("Bu harcamayı silmek istediğine emin misin?")) return;
    setRemoving(id);
    try {
      await api.deleteExpense(id);
      onDeleted(id);
    } catch {
      // sessiz fail — UI bir sonraki listeden duzeltir
    } finally {
      setRemoving(null);
    }
  }

  if (expenses.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 text-center text-sm text-gray-400">
        Bu ay için harcama kaydı yok.
      </div>
    );
  }

  const total = expenses.reduce((s, e) => s + parseFloat(e.amount), 0);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">Harcama Listesi</h2>
        <TLValue tl={total} className="text-lg font-bold text-gray-900" usdClassName="block text-xs text-gray-400 font-normal mt-0.5 tabular-nums text-right" />
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
            <th className="px-6 py-3 text-left">Tarih</th>
            <th className="px-6 py-3 text-left">Kategori</th>
            <th className="px-6 py-3 text-left">Açıklama</th>
            <th className="px-6 py-3 text-right">Tutar</th>
            <th className="px-6 py-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {expenses.map((exp) => (
            <tr key={exp.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-6 py-3 text-gray-600 tabular-nums">{exp.date}</td>
              <td className="px-6 py-3 text-gray-700">
                {EXPENSE_CATEGORY_LABELS[exp.category] ?? exp.category}
              </td>
              <td className="px-6 py-3 text-gray-500 truncate max-w-xs">
                {exp.description ?? <span className="text-gray-300">—</span>}
              </td>
              <td className="px-6 py-3 text-right font-semibold text-gray-900">
                {fmtTL(exp.amount)} ₺
              </td>
              <td className="px-6 py-3 text-right">
                <button
                  onClick={() => handleDelete(exp.id)}
                  disabled={removing === exp.id}
                  className="text-xs text-gray-300 hover:text-red-400 transition-colors disabled:opacity-40"
                >
                  {removing === exp.id ? "..." : "Sil"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
