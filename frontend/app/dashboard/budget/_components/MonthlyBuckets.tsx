"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { MonthlyBudgetResponse, BucketBlock } from "@/lib/api";
import { fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryLabel, bucketLabel, BUCKET_STYLES } from "./budgetUtils";

interface Props {
  readonly year: number;
  readonly month: number;
}

function BucketCard({ block }: { readonly block: BucketBlock }) {
  const { t } = useTranslation();
  const ccy = useDisplayCurrency();
  const style = BUCKET_STYLES[block.bucket];
  const budget = Number.parseFloat(block.budget_total_display);
  const actual = Number.parseFloat(block.actual_total_display);
  const pct = budget > 0 ? Math.min((actual / budget) * 100, 100) : 0;
  const overBudget = actual > budget && budget > 0;
  const actualRatioPct = block.actual_ratio === null ? null : Math.round(block.actual_ratio * 100);
  const targetPct = Math.round(block.target_ratio * 100);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className={`font-semibold ${style.text}`}>{bucketLabel(block.bucket, t)}</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${style.chip}`}>
          {t("content.budgetV2.target")}: {targetPct}%
          {actualRatioPct !== null && <> · {actualRatioPct}%</>}
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-1">
        <span className={`text-2xl font-bold ${overBudget ? "text-red-600" : "text-gray-900"}`}>
          {fmtCurrency(actual, ccy)}
        </span>
        <span className="text-sm text-gray-400">/ {fmtCurrency(budget, ccy)}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-4">
        <div className={`h-full ${overBudget ? "bg-red-500" : style.bar}`} style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-1.5 text-sm">
        {block.categories.length === 0 && <li className="text-gray-400 text-xs">—</li>}
        {block.categories.map((c, idx) => {
          const cBudget = Number.parseFloat(c.budget_display);
          const cActual = Number.parseFloat(c.actual_display);
          return (
            <li key={`${c.category}-${idx}`} className="flex items-center justify-between gap-2">
              <span className="text-gray-600 truncate flex items-center gap-1">
                {categoryLabel(c.category, t)}
                {c.weighted && (
                  <span
                    className="text-[10px] px-1 py-0.5 rounded bg-gray-100 text-gray-500"
                    title={t("content.budgetV2.weightedHint")}
                  >
                    ⚖️ {t("content.budgetV2.weighted")}
                  </span>
                )}
              </span>
              <span className="tabular-nums whitespace-nowrap">
                <span className={c.over_budget ? "text-red-600 font-medium" : "text-gray-800"}>
                  {fmtCurrency(cActual, ccy)}
                </span>
                <span className="text-gray-300"> / </span>
                <span className="text-gray-400">{fmtCurrency(cBudget, ccy)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function MonthlyBuckets({ year, month }: Props) {
  const { t } = useTranslation();
  const ccy = useDisplayCurrency();
  const [data, setData] = useState<MonthlyBudgetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getMonthlyBudget(year, month));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [year, month, t, ccy]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (loading) return <p className="text-sm text-gray-400 text-center py-6">{t("common.loading")}</p>;
  if (error) return <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>;
  if (!data) return null;

  const income = Number.parseFloat(data.income_display);
  const expense = Number.parseFloat(data.expense_total_display);
  const net = Number.parseFloat(data.net_display);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.income")}</p>
          <p className="text-xl font-bold text-emerald-600">{fmtCurrency(income, ccy)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.expenses")}</p>
          <p className="text-xl font-bold text-red-600">{fmtCurrency(expense, ccy)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.net")}</p>
          <p className={`text-xl font-bold ${net >= 0 ? "text-gray-900" : "text-red-600"}`}>{fmtCurrency(net, ccy)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.buckets.map((b) => (
          <BucketCard key={b.bucket} block={b} />
        ))}
      </div>
    </div>
  );
}
