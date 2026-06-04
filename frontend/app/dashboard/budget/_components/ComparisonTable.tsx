"use client";
import { BudgetComparisonDTO, EXPENSE_CATEGORY_LABELS } from "@/lib/api";
import { fmtTL } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly rows: BudgetComparisonDTO[];
  readonly onDelete: (category: string) => void;
}

export function ComparisonTable({ rows, onDelete }: Props) {
  const { t } = useTranslation();
  if (rows.length === 0) {
    return (
      <p className="text-center text-sm text-gray-400 py-8">
        {t("content.budget.noBudgetOrSpend")}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {rows.map((row) => {
        const actual = Number.parseFloat(row.actual_amount);
        const budget = row.budget_amount === null ? null : Number.parseFloat(row.budget_amount);
        const pct = row.pct_used ?? 0;
        const barPct = Math.min(pct, 100);
        const label = EXPENSE_CATEGORY_LABELS[row.category as keyof typeof EXPENSE_CATEGORY_LABELS] ?? row.category;

        let barColor: string;
        if (row.over_budget) barColor = "bg-red-500";
        else if (pct > 80) barColor = "bg-amber-400";
        else barColor = "bg-emerald-500";

        return (
          <div key={row.category} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-sm font-semibold text-gray-800">{label}</span>
                {row.over_budget && (
                  <span className="ml-2 text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                    {t("content.budget.exceeded")}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-sm">
                {budget !== null && (
                  <span className="text-gray-500 text-xs">{t("content.budget.limit")}: {fmtTL(budget)} {row.currency ?? "TRY"}</span>
                )}
                <TLValue
                  tl={actual}
                  className={`font-semibold ${row.over_budget ? "text-red-600" : "text-gray-900"}`}
                  usdClassName="block text-[10px] text-gray-400 font-normal mt-0.5 tabular-nums text-right"
                />
                {budget !== null && (
                  <button
                    onClick={() => onDelete(row.category)}
                    className="text-gray-400 hover:text-red-500 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                    title={t("content.budget.removeBudget")}
                    aria-label={`${label} — ${t("content.budget.removeBudget")}`}
                  >
                    <span aria-hidden="true">✕</span>
                  </button>
                )}
              </div>
            </div>

            {budget === null ? (
              <p className="text-xs text-gray-400">{t("content.budget.noBudgetDefined")}</p>
            ) : (
              <>
                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden mb-1">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${barPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>%{pct.toFixed(0)} {t("content.budget.used")}</span>
                  {row.remaining !== null && (
                    <span className={row.over_budget ? "text-red-500 font-medium" : "text-emerald-600"}>
                      {row.over_budget ? `${fmtTL(Math.abs(Number.parseFloat(row.remaining)))} ₺ ${t("content.budget.over")}` : `${fmtTL(Number.parseFloat(row.remaining))} ₺ ${t("content.budget.remaining")}`}
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
