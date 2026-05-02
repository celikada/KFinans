"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, ExpenseDTO, ExpenseSummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { ExpenseForm } from "./_components/ExpenseForm";
import { ExpenseTable } from "./_components/ExpenseTable";
import { CategoryPieChart } from "./_components/CategoryPieChart";
import { MonthSelector } from "./_components/MonthSelector";

export default function ExpensesPage() {
  const router = useRouter();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [expenses, setExpenses] = useState<ExpenseDTO[]>([]);
  const [summary, setSummary] = useState<ExpenseSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, sum] = await Promise.all([
        api.listExpenses({ year, month }),
        api.getExpenseSummary(year, month),
      ]);
      setExpenses(list);
      setSummary(sum);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { handle401(); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [year, month, handle401]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    refresh();
  }, [refresh, router]);

  function handleAdded(added: ExpenseDTO) {
    // Yeni harcama secili ay'a ait mi? Evet ise listeye ekle, summary'i yenile.
    const addedMonth = parseInt(added.date.slice(5, 7));
    const addedYear = parseInt(added.date.slice(0, 4));
    if (addedYear === year && addedMonth === month) {
      setExpenses((prev) => [added, ...prev]);
    }
    refresh();
  }

  function handleDeleted(id: number) {
    setExpenses((prev) => prev.filter((e) => e.id !== id));
    refresh();
  }

  const total = summary ? parseFloat(summary.total) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Harcamalar" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Üst panel: ay seçici + toplam */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-wrap items-center gap-4 justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">Bu ay toplam</p>
            <p className="text-3xl font-bold text-gray-900">{fmtTL(total)} ₺</p>
            {summary && (
              <p className="text-xs text-gray-400 mt-1">{summary.count} kayıt</p>
            )}
          </div>
          <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
        </div>

        <ExpenseForm onAdded={handleAdded} />

        {error && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {loading && (
          <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>
        )}

        {!loading && summary && summary.by_category.length > 0 && (
          <CategoryPieChart data={summary.by_category} total={total} />
        )}

        {!loading && (
          <ExpenseTable expenses={expenses} onDeleted={handleDeleted} />
        )}
      </main>
    </div>
  );
}
