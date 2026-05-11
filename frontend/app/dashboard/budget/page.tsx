"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, BudgetComparisonDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { MonthSelector } from "@/app/dashboard/expenses/_components/MonthSelector";
import { BudgetForm } from "./_components/BudgetForm";
import { ComparisonTable } from "./_components/ComparisonTable";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function BudgetPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [rows, setRows] = useState<BudgetComparisonDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getBudgetComparison(year, month);
      setRows(data);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [year, month, router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(category: string) {
    try {
      await api.deleteBudget(category);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silinemedi");
    }
  }

  const overBudgetCount = rows.filter((r) => r.over_budget).length;
  const totalBudget = rows.reduce((s, r) => s + (r.budget_amount ? parseFloat(r.budget_amount) : 0), 0);
  const totalActual = rows.reduce((s, r) => s + parseFloat(r.actual_amount), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.budget")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-wrap items-center gap-6 justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">Bu ay toplam harcama</p>
            <TLValue
              tl={totalActual}
              className={`text-3xl font-bold ${overBudgetCount > 0 ? "text-red-600" : "text-gray-900"}`}
              usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums"
            />
            {totalBudget > 0 && (
              <p className="text-xs text-gray-400 mt-1">
                {fmtTL(totalBudget)} ₺ toplam bütçe
                {overBudgetCount > 0 && (
                  <span className="ml-2 text-red-500 font-medium">{overBudgetCount} kategori aşıldı</span>
                )}
              </p>
            )}
          </div>
          <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
        </div>

        <BudgetForm onSaved={refresh} />

        {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && <ComparisonTable rows={rows} onDelete={handleDelete} />}
      </main>
    </div>
  );
}
