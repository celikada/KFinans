"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, IncomeDTO, IncomeSummaryDTO, INCOME_CATEGORY_LABELS } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { MonthSelector } from "@/app/dashboard/expenses/_components/MonthSelector";
import { IncomeForm } from "./_components/IncomeForm";
import { IncomeTable } from "./_components/IncomeTable";

export default function IncomePage() {
  const router = useRouter();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [incomes, setIncomes] = useState<IncomeDTO[]>([]);
  const [summary, setSummary] = useState<IncomeSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, sum] = await Promise.all([
        api.listIncomes({ year, month }),
        api.getIncomeSummary(year, month),
      ]);
      setIncomes(list);
      setSummary(sum);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [year, month, router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    refresh();
  }, [refresh, router]);

  function handleAdded(inc: IncomeDTO) {
    const addedMonth = parseInt(inc.date.slice(5, 7));
    const addedYear = parseInt(inc.date.slice(0, 4));
    if (addedYear === year && addedMonth === month) {
      setIncomes((prev) => [inc, ...prev]);
    }
    refresh();
  }

  function handleDeleted(id: number) {
    setIncomes((prev) => prev.filter((i) => i.id !== id));
    refresh();
  }

  const total = summary ? parseFloat(summary.total) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Gelir Takibi" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Üst panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-wrap items-center gap-4 justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">Bu ay toplam gelir</p>
            <p className="text-3xl font-bold text-emerald-600">{fmtTL(total)} ₺</p>
            {summary && summary.count > 0 && (
              <p className="text-xs text-gray-400 mt-1">{summary.count} kayıt</p>
            )}
          </div>
          <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
        </div>

        {/* Kategori özeti */}
        {summary && summary.by_category.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Kategori dağılımı</h3>
            <div className="space-y-3">
              {summary.by_category.map((b) => {
                const pct = total > 0 ? (parseFloat(b.total) / total) * 100 : 0;
                return (
                  <div key={b.category}>
                    <div className="flex justify-between text-xs text-gray-600 mb-1">
                      <span>{INCOME_CATEGORY_LABELS[b.category as keyof typeof INCOME_CATEGORY_LABELS] ?? b.category}</span>
                      <span className="font-semibold">{fmtTL(parseFloat(b.total))} ₺ <span className="text-gray-400">(%{pct.toFixed(0)})</span></span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                      <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <IncomeForm onAdded={handleAdded} />

        {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && <IncomeTable incomes={incomes} onDeleted={handleDeleted} />}
      </main>
    </div>
  );
}
