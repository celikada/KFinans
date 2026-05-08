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
import { fmtTL } from "@/lib/format";

const MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export default function CashFlowPage() {
  const router = useRouter();
  const now = new Date();
  const currentYear = now.getFullYear();
  const [year, setYear] = useState(currentYear);
  const [data, setData] = useState<CashFlowYearDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getCashFlow(year));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [year, router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Grafik için data hazırla
  const chartData = (data?.months ?? []).map((m) => ({
    name: MONTH_NAMES[m.month - 1],
    Gelir: parseFloat(m.income_total),
    Gider: parseFloat(m.expense_total),
    Net: parseFloat(m.net),
    is_past: m.is_past,
  }));

  const totalIncome = data ? parseFloat(data.total_income) : 0;
  const totalExpense = data ? parseFloat(data.total_expense) : 0;
  const totalNet = data ? parseFloat(data.total_net) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Nakit Akışı" />

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
                {y < currentYear && <span className="ml-1 text-xs opacity-70">(geçmiş)</span>}
                {y === currentYear && <span className="ml-1 text-xs opacity-70">(bu yıl)</span>}
                {y > currentYear && <span className="ml-1 text-xs opacity-70">(tahmin)</span>}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => api.downloadReport(`/cash-flow/report.xlsx?year=${year}`, `nakit-akis-${year}.xlsx`)}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              Excel İndir
            </button>
            <button
              type="button"
              onClick={() => api.downloadReport(`/cash-flow/report.pdf?year=${year}`, `nakit-akis-${year}.pdf`)}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              PDF İndir
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400">
          Geçmiş aylar gerçekleşen, gelecek aylar tahmin (recurring + planlı + taksit + ekstre).
        </p>

        {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}

        {/* 3 metrik özet */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Toplam Gelir</p>
            <p className="text-2xl font-bold text-emerald-600 tabular-nums">{fmtTL(totalIncome)} ₺</p>
            <p className="text-xs text-gray-400 mt-1">{year} yıl toplamı (gerçek + tahmin)</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Toplam Gider</p>
            <p className="text-2xl font-bold text-rose-600 tabular-nums">{fmtTL(totalExpense)} ₺</p>
            <p className="text-xs text-gray-400 mt-1">harcama + ekstre + taksit + planlı</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Net</p>
            <p className={`text-2xl font-bold tabular-nums ${totalNet >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {totalNet >= 0 ? "+" : ""}{fmtTL(totalNet)} ₺
            </p>
            <p className="text-xs text-gray-400 mt-1">gelir − gider</p>
          </div>
        </div>

        {/* Grafik */}
        {!loading && data && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Aylık Nakit Akışı</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" fontSize={11} stroke="#9ca3af" />
                  <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} fontSize={11} stroke="#9ca3af" />
                  <Tooltip
                    formatter={(v) => `${fmtTL(v as number)} ₺`}
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Gelir" fill="#10b981" />
                  <Bar dataKey="Gider" fill="#ef4444" />
                  <Line type="monotone" dataKey="Net" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Aylık tablo */}
        {!loading && data && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">Ay</th>
                  <th className="px-4 py-3 text-right">Gerçek Gelir</th>
                  <th className="px-4 py-3 text-right">Tahmini Gelir</th>
                  <th className="px-4 py-3 text-right">Gerçek Gider</th>
                  <th className="px-4 py-3 text-right">Tahmini Gider</th>
                  <th className="px-4 py-3 text-right">Net</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.months.map((m) => {
                  const incActual = parseFloat(m.income_actual);
                  const incForecast = parseFloat(m.income_forecast);
                  const expActual = parseFloat(m.expense_actual);
                  const expForecast = parseFloat(m.expense_forecast);
                  const net = parseFloat(m.net);
                  return (
                    <tr key={m.month} className={m.is_past ? "" : "bg-gray-50/30"}>
                      <td className="px-4 py-3">
                        <span className="font-medium text-gray-900">{MONTH_NAMES[m.month - 1]}</span>
                        {!m.is_past && <span className="ml-2 text-[10px] text-gray-400">tahmin</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-emerald-600 tabular-nums">{fmtTL(incActual)} ₺</td>
                      <td className="px-4 py-3 text-right text-emerald-400 tabular-nums">{fmtTL(incForecast)} ₺</td>
                      <td className="px-4 py-3 text-right text-rose-600 tabular-nums">{fmtTL(expActual)} ₺</td>
                      <td className="px-4 py-3 text-right text-rose-400 tabular-nums">{fmtTL(expForecast)} ₺</td>
                      <td className={`px-4 py-3 text-right font-semibold tabular-nums ${net >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                        {net >= 0 ? "+" : ""}{fmtTL(net)} ₺
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-gray-50 font-semibold">
                <tr>
                  <td className="px-4 py-3 text-gray-700">Yıl Toplamı</td>
                  <td colSpan={2} className="px-4 py-3 text-right text-emerald-600 tabular-nums">{fmtTL(totalIncome)} ₺</td>
                  <td colSpan={2} className="px-4 py-3 text-right text-rose-600 tabular-nums">{fmtTL(totalExpense)} ₺</td>
                  <td className={`px-4 py-3 text-right tabular-nums ${totalNet >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {totalNet >= 0 ? "+" : ""}{fmtTL(totalNet)} ₺
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        {loading && <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>}
      </main>
    </div>
  );
}
