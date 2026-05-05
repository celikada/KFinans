"use client";
import { useState } from "react";
import {
  api,
  RecurringIncomeDTO,
  RECURRING_INCOME_CATEGORY_LABELS,
  RECURRING_RECURRENCE_LABELS,
} from "@/lib/api";
import { fmtTL } from "@/lib/format";

interface Props {
  items: RecurringIncomeDTO[];
  onDeleted: (id: number) => void;
}

const MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export function RecurringIncomeTable({ items, onDeleted }: Props) {
  const [deleting, setDeleting] = useState<number | null>(null);

  async function handleDelete(id: number, title: string) {
    if (!confirm(`"${title}" periyodik gelir kaydı silinsin mi?`)) return;
    setDeleting(id);
    try {
      await api.deleteRecurringIncome(id);
      onDeleted(id);
    } catch {
      alert("Silinemedi");
    } finally {
      setDeleting(null);
    }
  }

  if (!items.length) {
    return <p className="text-center text-sm text-gray-400 py-8">Henüz periyodik gelir kaydı yok.</p>;
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
            <th className="px-4 py-3 text-left">Başlık</th>
            <th className="px-4 py-3 text-left">Kategori</th>
            <th className="px-4 py-3 text-left">Periyot</th>
            <th className="px-4 py-3 text-left">Tarih aralığı</th>
            <th className="px-4 py-3 text-right">Tutar</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {items.map((it) => {
            const monthsLabel = it.recurrence === "custom" && it.months?.length
              ? it.months.map((m) => MONTH_NAMES[m - 1]).join(", ")
              : null;
            return (
              <tr key={it.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{it.title}</p>
                  {it.notes && <p className="text-xs text-gray-400 mt-0.5">{it.notes}</p>}
                </td>
                <td className="px-4 py-3 text-gray-600">{RECURRING_INCOME_CATEGORY_LABELS[it.category]}</td>
                <td className="px-4 py-3 text-gray-600">
                  {RECURRING_RECURRENCE_LABELS[it.recurrence]}
                  {monthsLabel && <span className="block text-xs text-gray-400">{monthsLabel}</span>}
                  <span className="block text-xs text-gray-400">{it.day_of_month}. gün</span>
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">
                  {it.start_date}
                  <br />
                  {it.end_date ? `→ ${it.end_date}` : "→ süresiz"}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-emerald-600 tabular-nums">
                  {fmtTL(parseFloat(it.amount))} ₺
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleDelete(it.id, it.title)}
                    disabled={deleting === it.id}
                    className="text-gray-400 hover:text-red-500 text-sm disabled:opacity-50"
                    title="Sil"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
