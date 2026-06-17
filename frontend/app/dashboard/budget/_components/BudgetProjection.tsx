"use client";
import { useEffect, useState, useCallback, useMemo } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { CashFlowYearDTO } from "@/lib/api";
import { fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly year: number;
}

export function BudgetProjection({ year }: Props) {
  const { t } = useTranslation();
  const ccy = useDisplayCurrency();
  const [data, setData] = useState<CashFlowYearDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getCashFlow(year));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [year, t, ccy]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Kümülatif bakiye (butce26 "Yıllık Bütçeden Kalan Aylık Bakiye"): aylık net'lerin koşan toplamı.
  const chartData = useMemo(() => {
    if (!data) return [];
    let cumulative = 0;
    return data.months.map((m) => {
      const net = Number.parseFloat(m.net_display);
      cumulative += net;
      return {
        month: t(`months.${m.month}`),
        income: Number.parseFloat(m.income_total_display),
        expense: Number.parseFloat(m.expense_total_display),
        net,
        cumulative,
      };
    });
  }, [data, t]);

  if (loading) return <p className="text-sm text-gray-400 text-center py-6">{t("common.loading")}</p>;
  if (error) return <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>;
  if (!data) return null;

  const yearEnd = chartData.length ? chartData[chartData.length - 1].cumulative : 0;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <div className="flex items-baseline justify-between mb-4">
          <p className="text-xs text-gray-400">{t("content.budgetV2.projection.yearEnd")}</p>
          <p className={`text-xl font-bold ${yearEnd >= 0 ? "text-emerald-600" : "text-red-600"}`}>
            {fmtCurrency(yearEnd, ccy)}
          </p>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={70} tickFormatter={(v) => fmtCurrency(v as number, ccy)} />
            <Tooltip formatter={(v) => fmtCurrency(v as number, ccy)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="income" name={t("content.budgetV2.projection.income")} fill="#10b981" radius={[3, 3, 0, 0]} />
            <Bar dataKey="expense" name={t("content.budgetV2.projection.expense")} fill="#ef4444" radius={[3, 3, 0, 0]} />
            <Line
              type="monotone"
              dataKey="cumulative"
              name={t("content.budgetV2.projection.cumulative")}
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-xs border-b border-gray-100">
              <th className="text-left font-medium px-3 py-2">{t("content.budgetV2.projection.month")}</th>
              <th className="text-right font-medium px-3 py-2">{t("content.budgetV2.projection.income")}</th>
              <th className="text-right font-medium px-3 py-2">{t("content.budgetV2.projection.expense")}</th>
              <th className="text-right font-medium px-3 py-2">{t("content.budgetV2.projection.net")}</th>
              <th className="text-right font-medium px-3 py-2">{t("content.budgetV2.projection.cumulative")}</th>
            </tr>
          </thead>
          <tbody>
            {chartData.map((row) => (
              <tr key={row.month} className="border-b border-gray-50">
                <td className="text-left px-3 py-1.5 text-gray-700">{row.month}</td>
                <td className="text-right px-3 py-1.5 tabular-nums text-emerald-600">{fmtCurrency(row.income, ccy)}</td>
                <td className="text-right px-3 py-1.5 tabular-nums text-red-600">{fmtCurrency(row.expense, ccy)}</td>
                <td className={`text-right px-3 py-1.5 tabular-nums ${row.net >= 0 ? "text-gray-800" : "text-red-600"}`}>
                  {fmtCurrency(row.net, ccy)}
                </td>
                <td className={`text-right px-3 py-1.5 tabular-nums font-medium ${row.cumulative >= 0 ? "text-blue-700" : "text-red-600"}`}>
                  {fmtCurrency(row.cumulative, ccy)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
