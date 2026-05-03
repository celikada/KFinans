"use client";
import { api, BudgetComparisonDTO, EXPENSE_CATEGORY_LABELS } from "@/lib/api";
import { fmtTL } from "@/lib/format";

interface Props {
  rows: BudgetComparisonDTO[];
  onDelete: (category: string) => void;
}

export function ComparisonTable({ rows, onDelete }: Props) {
  if (rows.length === 0) {
    return (
      <p className="text-center text-sm text-gray-400 py-8">
        Henüz bütçe veya harcama yok.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {rows.map((row) => {
        const actual = parseFloat(row.actual_amount);
        const budget = row.budget_amount !== null ? parseFloat(row.budget_amount) : null;
        const pct = row.pct_used ?? 0;
        const barPct = Math.min(pct, 100);
        const label = EXPENSE_CATEGORY_LABELS[row.category as keyof typeof EXPENSE_CATEGORY_LABELS] ?? row.category;

        return (
          <div key={row.category} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-sm font-semibold text-gray-800">{label}</span>
                {row.over_budget && (
                  <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                    Aşıldı
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-sm">
                {budget !== null && (
                  <span className="text-gray-500 text-xs">Limit: {fmtTL(budget)} ₺</span>
                )}
                <span className={`font-semibold ${row.over_budget ? "text-red-600" : "text-gray-900"}`}>
                  {fmtTL(actual)} ₺
                </span>
                {budget !== null && (
                  <button
                    onClick={() => onDelete(row.category)}
                    className="text-gray-400 hover:text-red-500 text-sm font-medium transition-colors"
                    title="Bütçeyi kaldır"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {budget !== null ? (
              <>
                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden mb-1">
                  <div
                    className={`h-full rounded-full transition-all ${row.over_budget ? "bg-red-500" : pct > 80 ? "bg-amber-400" : "bg-emerald-500"}`}
                    style={{ width: `${barPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>%{pct.toFixed(0)} kullanıldı</span>
                  {row.remaining !== null && (
                    <span className={row.over_budget ? "text-red-500 font-medium" : "text-emerald-600"}>
                      {row.over_budget ? `${fmtTL(Math.abs(parseFloat(row.remaining)))} ₺ aşım` : `${fmtTL(parseFloat(row.remaining))} ₺ kaldı`}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <p className="text-xs text-gray-400">Bütçe tanımlanmamış — yalnızca harcama var</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
