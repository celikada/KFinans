"use client";
import { api, IncomeDTO, INCOME_CATEGORY_LABELS } from "@/lib/api";
import { fmtTL, fmtDate } from "@/lib/format";

interface Props {
  incomes: IncomeDTO[];
  onDeleted: (id: number) => void;
}

export function IncomeTable({ incomes, onDeleted }: Props) {
  if (incomes.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <p className="text-sm text-gray-400 text-center py-4">Bu ay gelir kaydı yok.</p>
      </div>
    );
  }

  const runningTotal = incomes.reduce((s, i) => s + parseFloat(i.amount), 0);

  async function handleDelete(id: number) {
    if (!confirm("Bu gelir kaydı silinsin mi?")) return;
    await api.deleteIncome(id);
    onDeleted(id);
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex justify-between items-center">
        <h3 className="text-sm font-semibold text-gray-700">Gelir kayıtları</h3>
        <span className="text-sm font-bold text-emerald-600">{fmtTL(runningTotal)} ₺</span>
      </div>
      <ul className="divide-y divide-gray-50">
        {incomes.map((inc) => (
          <li key={inc.id} className="px-6 py-3 flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                  {INCOME_CATEGORY_LABELS[inc.category] ?? inc.category}
                </span>
                <span className="text-xs text-gray-400">{fmtDate(inc.date)}</span>
              </div>
              {inc.description && (
                <p className="text-xs text-gray-500 mt-0.5 truncate">{inc.description}</p>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-sm font-semibold text-gray-900 tabular-nums">
                +{fmtTL(parseFloat(inc.amount))} ₺
              </span>
              <button
                onClick={() => handleDelete(inc.id)}
                className="text-xs text-red-400 hover:text-red-600 transition-colors"
              >
                Sil
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
