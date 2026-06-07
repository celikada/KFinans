"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  Bar,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, CashFlowYearDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { DisplayMoney, fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { CashFlowMonthDetailModal } from "./_components/CashFlowMonthDetailModal";

export default function CashFlowPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const displayCurrency = useDisplayCurrency();
  const MONTH_NAMES = t("content.cashFlow.monthsShort").split(",");
  const now = new Date();
  const currentYear = now.getFullYear();
  const [year, setYear] = useState(currentYear);
  const [data, setData] = useState<CashFlowYearDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detailMonth, setDetailMonth] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getCashFlow(year));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : t("content.cashFlow.loadFailed"));
    } finally {
      setLoading(false);
    }
    // displayCurrency dep: para birimi değişince backend yeni *_display ile yeniden çekilir.
  }, [year, router, t, displayCurrency]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Grafik için data hazırla — Faz B: değerler ZATEN görüntüleme para biriminde
  // (*_display, actual=tarihsel/forecast=güncel kur); grafik/eksen/tooltip BÖLMEZ.
  const chartData = (data?.months ?? []).map((m) => ({
    name: MONTH_NAMES[m.month - 1],
    income: Number.parseFloat(m.income_total_display),
    expense: Number.parseFloat(m.expense_total_display),
    net: Number.parseFloat(m.net_display),
    is_past: m.is_past,
  }));

  const totalIncome = data ? Number.parseFloat(data.total_income_display) : 0;
  const totalExpense = data ? Number.parseFloat(data.total_expense_display) : 0;
  const totalNet = data ? Number.parseFloat(data.total_net_display) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.cashFlow")} />

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Yıl seçici + indir butonları */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
            {[currentYear - 1, currentYear, currentYear + 1].map((y) => (
              <button
                key={y}
                onClick={() => setYear(y)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  year === y
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-600 hover:text-gray-900"
                }`}
              >
                {y}
                {y < currentYear && <span className="ml-1 text-xs opacity-70">({t("content.cashFlow.past")})</span>}
                {y === currentYear && <span className="ml-1 text-xs opacity-70">({t("content.cashFlow.thisYear")})</span>}
                {y > currentYear && <span className="ml-1 text-xs opacity-70">({t("content.cashFlow.forecast")})</span>}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => api.downloadReport(`/cash-flow/report.xlsx?year=${year}`, `${t("content.cashFlow.fileSlug")}-${year}.xlsx`)}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              {t("form.excelDownload")}
            </button>
            <button
              type="button"
              onClick={() => api.downloadReport(`/cash-flow/report.pdf?year=${year}`, `${t("content.cashFlow.fileSlug")}-${year}.pdf`)}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              {t("content.cashFlow.pdfDownload")}
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400">
          {t("content.cashFlow.explainer")}
        </p>

        {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}

        {/* 3 metrik özet */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">{t("content.cashFlow.totalIncome")}</p>
            <DisplayMoney value={totalIncome} currency={displayCurrency} className="text-2xl font-bold text-emerald-600 tabular-nums" />
            <p className="text-xs text-gray-400 mt-1">{year} {t("content.cashFlow.yearTotalHint")}</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">{t("content.cashFlow.totalExpense")}</p>
            <DisplayMoney value={totalExpense} currency={displayCurrency} className="text-2xl font-bold text-rose-600 tabular-nums" />
            <p className="text-xs text-gray-400 mt-1">{t("content.cashFlow.expenseHint")}</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">{t("table.net")}</p>
            <p className={`text-2xl font-bold tabular-nums ${totalNet >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {totalNet >= 0 ? "+" : ""}{fmtCurrency(totalNet, displayCurrency)}
            </p>
            <p className="text-xs text-gray-400 mt-1">{t("content.cashFlow.netHint")}</p>
          </div>
        </div>

        {/* Grafik */}
        {!loading && data && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">{t("content.cashFlow.monthlyChartTitle")}</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={chartData}
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  onClick={(state) => {
                    const idx = state?.activeTooltipIndex;
                    if (typeof idx === "number" && idx >= 0 && idx < 12) setDetailMonth(idx + 1);
                  }}
                  className="cursor-pointer"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" fontSize={11} stroke="#9ca3af" />
                  <YAxis
                    // Değerler zaten görüntüleme para biriminde — sadece binlik kısalt (K).
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                    fontSize={11}
                    stroke="#9ca3af"
                  />
                  <Tooltip
                    formatter={(v) => fmtCurrency(v as number, displayCurrency)}
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="income" name={t("content.cashFlow.income")} fill="#10b981" />
                  <Bar dataKey="expense" name={t("content.cashFlow.expense")} fill="#ef4444" />
                  <Line type="monotone" dataKey="net" name={t("table.net")} stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Aylık tablo */}
        {!loading && data && (
          <p className="text-xs text-gray-400 -mb-2">{t("content.cashFlow.rowDetailHint")}</p>
        )}
        {!loading && data && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">{t("table.month")}</th>
                  <th className="px-4 py-3 text-right">{t("table.actualIncome")}</th>
                  <th className="px-4 py-3 text-right">{t("table.forecastIncome")}</th>
                  <th className="px-4 py-3 text-right">{t("table.actualExpense")}</th>
                  <th className="px-4 py-3 text-right">{t("table.forecastExpense")}</th>
                  <th className="px-4 py-3 text-right">{t("table.net")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.months.map((m) => {
                  // Faz C: backend *_display alanları ZATEN görüntüleme biriminde
                  // (actual=tarihsel kur, forecast=güncel kur) → BÖLME YOK.
                  const net = Number.parseFloat(m.net_display);
                  return (
                    <tr key={m.month} className={m.is_past ? "" : "bg-gray-50/30"}>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setDetailMonth(m.month)}
                          className="font-medium text-blue-700 hover:text-blue-900 hover:underline focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none rounded"
                        >
                          {MONTH_NAMES[m.month - 1]}
                        </button>
                        {!m.is_past && <span className="ml-2 text-[10px] text-gray-400">{t("content.cashFlow.forecast")}</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-emerald-600 tabular-nums">{fmtCurrency(m.income_actual_display, displayCurrency)}</td>
                      <td className="px-4 py-3 text-right text-emerald-400 tabular-nums">{fmtCurrency(m.income_forecast_display, displayCurrency)}</td>
                      <td className="px-4 py-3 text-right text-rose-600 tabular-nums">{fmtCurrency(m.expense_actual_display, displayCurrency)}</td>
                      <td className="px-4 py-3 text-right text-rose-400 tabular-nums">{fmtCurrency(m.expense_forecast_display, displayCurrency)}</td>
                      <td className={`px-4 py-3 text-right font-semibold tabular-nums ${net >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                        {net >= 0 ? "+" : ""}{fmtCurrency(net, displayCurrency)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-gray-50 font-semibold">
                <tr>
                  <td className="px-4 py-3 text-gray-700">{t("content.cashFlow.yearTotal")}</td>
                  <td colSpan={2} className="px-4 py-3 text-right text-emerald-600 tabular-nums">{fmtCurrency(totalIncome, displayCurrency)}</td>
                  <td colSpan={2} className="px-4 py-3 text-right text-rose-600 tabular-nums">{fmtCurrency(totalExpense, displayCurrency)}</td>
                  <td className={`px-4 py-3 text-right tabular-nums ${totalNet >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {totalNet >= 0 ? "+" : ""}{fmtCurrency(totalNet, displayCurrency)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        {loading && <p className="text-sm text-gray-400 text-center py-8">{t("common.loading")}</p>}
      </main>

      {detailMonth !== null && (
        <CashFlowMonthDetailModal
          year={year}
          month={detailMonth}
          monthName={MONTH_NAMES[detailMonth - 1]}
          onClose={() => setDetailMonth(null)}
        />
      )}
    </div>
  );
}
