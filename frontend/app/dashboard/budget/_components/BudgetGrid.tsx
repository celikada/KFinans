"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { BudgetGridResponse, CurrencyType } from "@/lib/api";
import { fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryLabel } from "./budgetUtils";

interface Props {
  readonly year: number;
}

// Ay numaraları (1-12) — index yerine değerle key'lemek için (S6479).
const MONTH_NUMS: number[] = Array.from({ length: 12 }, (_, i) => i + 1);

export function BudgetGrid({ year }: Props) {
  const { t } = useTranslation();
  const ccy = useDisplayCurrency();
  const [data, setData] = useState<BudgetGridResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<{ category: string; month: number } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getBudgetGrid(year));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [year, t, ccy]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function commit(category: string, month: number, currency: CurrencyType | null) {
    setSaving(true);
    setError("");
    try {
      const raw = editValue.trim().replace(",", ".");
      const amount = Number.parseFloat(raw);
      if (raw === "" || !Number.isFinite(amount) || amount <= 0) {
        await api.deleteBudgetLine(year, month, category).catch(() => undefined);
      } else {
        await api.upsertBudgetLine(year, month, category, amount, currency ?? undefined);
      }
      setEditing(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-400 text-center py-6">{t("common.loading")}</p>;
  if (error && !data) return <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>;
  if (!data) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-400">{t("content.budgetV2.grid.editHint")}</p>
      {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-2 rounded-xl">{error}</p>}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-xs border-b border-gray-100">
              <th className="text-left font-medium px-3 py-2 sticky left-0 bg-white z-10">
                {t("content.budgetV2.grid.category")}
              </th>
              {MONTH_NUMS.map((m) => (
                <th key={m} className="text-right font-medium px-2 py-2 whitespace-nowrap">
                  {t(`months.${m}`)}
                </th>
              ))}
              <th className="text-right font-medium px-3 py-2 whitespace-nowrap">{t("content.budgetV2.grid.yearTotal")}</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.category} className="border-b border-gray-50 hover:bg-gray-50/50">
                <td className="text-left px-3 py-1.5 font-medium text-gray-700 sticky left-0 bg-white z-10 whitespace-nowrap">
                  {categoryLabel(row.category, t)}
                </td>
                {row.cells.map((cell) => {
                  const isEditing = editing?.category === row.category && editing?.month === cell.month;
                  const planned = cell.planned_display ? Number.parseFloat(cell.planned_display) : null;
                  const actual = Number.parseFloat(cell.actual_display);
                  return (
                    <td key={cell.month} className="px-1 py-1 text-right align-top">
                      {isEditing ? (
                        <input
                          type="number"
                          step="0.01"
                          autoFocus
                          disabled={saving}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={() => commit(row.category, cell.month, cell.planned_currency as CurrencyType | null)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commit(row.category, cell.month, cell.planned_currency as CurrencyType | null);
                            if (e.key === "Escape") setEditing(null);
                          }}
                          className="w-20 px-1 py-0.5 text-right border border-blue-400 rounded text-xs"
                          aria-label={`${categoryLabel(row.category, t)} ${cell.month}`}
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setEditing({ category: row.category, month: cell.month });
                            setEditValue(cell.planned ?? "");
                          }}
                          className="w-full text-right px-1 py-0.5 rounded hover:bg-blue-50 group"
                        >
                          <span className={`block text-xs tabular-nums ${planned ? "text-gray-800" : "text-gray-300"}`}>
                            {planned ? fmtCurrency(planned, ccy) : "—"}
                          </span>
                          {actual > 0 && (
                            <span className="block text-[10px] tabular-nums text-gray-400">{fmtCurrency(actual, ccy)}</span>
                          )}
                        </button>
                      )}
                    </td>
                  );
                })}
                <td className="px-3 py-1.5 text-right font-semibold text-gray-800 tabular-nums whitespace-nowrap">
                  {fmtCurrency(Number.parseFloat(row.planned_total_display), ccy)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-200 font-semibold text-gray-700 bg-gray-50/50">
              <td className="text-left px-3 py-2 sticky left-0 bg-gray-50 z-10">{t("content.budgetV2.grid.monthlyTotal")}</td>
              {MONTH_NUMS.map((m) => (
                <td key={m} className="px-1 py-2 text-right text-xs tabular-nums whitespace-nowrap">
                  {fmtCurrency(Number.parseFloat(data.monthly_planned_display[m - 1]), ccy)}
                </td>
              ))}
              <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                {fmtCurrency(Number.parseFloat(data.planned_total_display), ccy)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
