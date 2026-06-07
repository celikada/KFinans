"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, ExpenseDTO, ExpenseSummaryDTO, BudgetComparisonDTO, EXPENSE_CATEGORY_LABELS } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { TOOLBAR_BTN_CLS } from "@/lib/format";
import { DisplayMoney, fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { ExpenseForm } from "./_components/ExpenseForm";
import { ExpenseTable } from "./_components/ExpenseTable";
import { CategoryPieChart } from "./_components/CategoryPieChart";
import { MonthSelector } from "./_components/MonthSelector";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function ExpensesPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const displayCurrency = useDisplayCurrency();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [expenses, setExpenses] = useState<ExpenseDTO[]>([]);
  const [summary, setSummary] = useState<ExpenseSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overBudget, setOverBudget] = useState<BudgetComparisonDTO[]>([]);
  const [importing, setImporting] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseDTO | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, sum, comparison] = await Promise.all([
        api.listExpenses({ year, month }),
        api.getExpenseSummary(year, month),
        api.getBudgetComparison(year, month),
      ]);
      setExpenses(list);
      setSummary(sum);
      setOverBudget(comparison.filter((r) => r.over_budget));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { handle401(); return; }
      setError(err instanceof Error ? err.message : t("content.expenses.loadFailed"));
    } finally {
      setLoading(false);
    }
    // displayCurrency dep: para birimi değişince backend yeni *_display ile yeniden çekilir.
  }, [year, month, handle401, t, displayCurrency]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function handleSaved() {
    setEditingExpense(null);
    refresh();
  }

  function handleDeleted(id: number) {
    setExpenses((prev) => prev.filter((e) => e.id !== id));
    refresh();
  }

  async function handleExport() {
    try {
      await api.exportExpenses(year, month);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.expenses.exportFailed"));
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      await api.importExpenses(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.expenses.importFailed"));
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  // Faz B: toplam backend tarihsel-kur bazlı total_display'den (çift-çevrim yok).
  const totalDisplay = summary?.total_display ?? "0";
  const totalDisplayNum = Number.parseFloat(totalDisplay);

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.expenses")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Üst panel: ay seçici + toplam + toolbar */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-wrap items-center gap-4 justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("content.expenses.monthTotal")}</p>
            <DisplayMoney value={totalDisplay} currency={displayCurrency} className="text-3xl font-bold text-gray-900" />
            {summary && (
              <p className="text-xs text-gray-400 mt-1">{summary.count} {t("content.expenses.records")}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
            <button onClick={handleExport} className={TOOLBAR_BTN_CLS}>
              {t("form.excelDownload")}
            </button>
            <button
              onClick={() => importRef.current?.click()}
              disabled={importing}
              className={TOOLBAR_BTN_CLS}
            >
              {importing ? t("common.loading") : t("form.excelUpload")}
            </button>
            <input
              ref={importRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={handleImport}
            />
          </div>
        </div>

        {/* Bütçe aşım uyarısı */}
        {overBudget.length > 0 && (
          <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-4">
            <p className="text-sm font-semibold text-red-700 mb-2">
              {overBudget.length} {t("content.expenses.categoriesOverBudget")}
            </p>
            <ul className="space-y-1">
              {overBudget.map((r) => {
                // Faz B: actual=tarihsel, budget=güncel kur — backend *_display verir.
                const actualD = Number.parseFloat(r.actual_amount_display);
                const budgetD = Number.parseFloat(r.budget_amount_display ?? "0");
                const excessD = actualD - budgetD;
                const label = EXPENSE_CATEGORY_LABELS[r.category as keyof typeof EXPENSE_CATEGORY_LABELS] ?? r.category;
                return (
                  <li key={r.category} className="flex justify-between text-xs text-red-600">
                    <span>{label}</span>
                    <span className="font-medium">{fmtCurrency(budgetD, displayCurrency)} {t("content.expenses.limit")} · {fmtCurrency(excessD, displayCurrency)} {t("content.expenses.over")}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <ExpenseForm
          onSaved={handleSaved}
          existing={editingExpense}
          onCancel={() => setEditingExpense(null)}
        />

        {error && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {loading && (
          <p className="text-sm text-gray-400 text-center py-4">{t("common.loading")}</p>
        )}

        {!loading && summary && summary.by_category.length > 0 && (
          <CategoryPieChart data={summary.by_category} total={totalDisplayNum} currency={displayCurrency} />
        )}

        {!loading && (
          <ExpenseTable expenses={expenses} onDeleted={handleDeleted} onEdit={setEditingExpense} />
        )}
      </main>
    </div>
  );
}
