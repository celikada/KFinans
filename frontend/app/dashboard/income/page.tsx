"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  api, IncomeDTO, IncomeSummaryDTO, IncomeDashboardDTO,
  RecurringIncomeDTO, INCOME_CATEGORY_LABELS,
} from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL, TOOLBAR_BTN_CLS } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { MonthSelector } from "@/app/dashboard/expenses/_components/MonthSelector";
import { IncomeForm } from "./_components/IncomeForm";
import { IncomeTable } from "./_components/IncomeTable";
import { RecurringIncomeForm } from "./_components/RecurringIncomeForm";
import { RecurringIncomeTable } from "./_components/RecurringIncomeTable";

type Tab = "actual" | "recurring";

export default function IncomePage() {
  const router = useRouter();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [tab, setTab] = useState<Tab>("actual");

  const [incomes, setIncomes] = useState<IncomeDTO[]>([]);
  const [summary, setSummary] = useState<IncomeSummaryDTO | null>(null);
  const [dashboard, setDashboard] = useState<IncomeDashboardDTO | null>(null);
  const [recurring, setRecurring] = useState<RecurringIncomeDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, sum, dash, rec] = await Promise.all([
        api.listIncomes({ year, month }),
        api.getIncomeSummary(year, month),
        api.getIncomeDashboard(year, month),
        api.listRecurringIncomes(),
      ]);
      setIncomes(list);
      setSummary(sum);
      setDashboard(dash);
      setRecurring(rec);
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

  function handleRecurringAdded(ri: RecurringIncomeDTO) {
    setRecurring((prev) => [ri, ...prev]);
    refresh();
  }

  function handleRecurringDeleted(id: number) {
    setRecurring((prev) => prev.filter((r) => r.id !== id));
    refresh();
  }

  async function handleExport() {
    try {
      await api.exportIncomes(year, month);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export başarısız");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      await api.importIncomes(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  const monthTotal = dashboard ? parseFloat(dashboard.this_month_actual) : 0;
  const ytdTotal = dashboard ? parseFloat(dashboard.ytd_actual) : 0;
  const yearEstimate = dashboard ? parseFloat(dashboard.year_total_estimate) : 0;
  const remainingRecurring = dashboard ? parseFloat(dashboard.remaining_year_recurring) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Gelir Takibi" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* 3 metrik kartı */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Bu ay (gerçekleşen)</p>
            <TLValue tl={monthTotal} className="text-2xl font-bold text-emerald-600" usdClassName="block text-xs text-gray-400 font-normal mt-1 tabular-nums" />
            {summary && summary.count > 0 && (
              <p className="text-xs text-gray-400 mt-1">{summary.count} kayıt</p>
            )}
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Yıl içi (gerçekleşen)</p>
            <TLValue tl={ytdTotal} className="text-2xl font-bold text-blue-600" usdClassName="block text-xs text-gray-400 font-normal mt-1 tabular-nums" />
            <p className="text-xs text-gray-400 mt-1">{year} yıl başından</p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <p className="text-xs text-gray-400 mb-1">Yıl sonu beklentisi</p>
            <TLValue tl={yearEstimate} className="text-2xl font-bold text-purple-600" usdClassName="block text-xs text-gray-400 font-normal mt-1 tabular-nums" />
            {remainingRecurring > 0 && (
              <p className="text-xs text-gray-400 mt-1">+{fmtTL(remainingRecurring)} ₺ kalan periyodik</p>
            )}
          </div>
        </div>

        {/* Toolbar: ay seçici + Excel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-wrap items-center gap-3 justify-between">
          <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
          <div className="flex items-center gap-2">
            <button onClick={handleExport} className={TOOLBAR_BTN_CLS}>
              Excel İndir
            </button>
            <button
              onClick={() => importRef.current?.click()}
              disabled={importing}
              className={TOOLBAR_BTN_CLS}
            >
              {importing ? "Yükleniyor..." : "Excel Yükle"}
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

        {/* Sekmeler */}
        <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
          <button
            onClick={() => setTab("actual")}
            className={`px-4 py-2 font-medium transition-colors ${
              tab === "actual" ? "bg-emerald-600 text-white" : "bg-white text-gray-600 hover:text-gray-900"
            }`}
          >
            Gerçekleşen Gelirler
          </button>
          <button
            onClick={() => setTab("recurring")}
            className={`px-4 py-2 font-medium transition-colors ${
              tab === "recurring" ? "bg-emerald-600 text-white" : "bg-white text-gray-600 hover:text-gray-900"
            }`}
          >
            Periyodik (Maaş, Kira...)
          </button>
        </div>

        {/* Sekme içerikleri */}
        {tab === "actual" && (
          <>
            {/* Kategori dağılımı (gerçekleşen) */}
            {summary && summary.by_category.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Bu ay kategori dağılımı</h3>
                <div className="space-y-3">
                  {summary.by_category.map((b) => {
                    const pct = monthTotal > 0 ? (parseFloat(b.total) / monthTotal) * 100 : 0;
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
          </>
        )}

        {tab === "recurring" && (
          <>
            <RecurringIncomeForm onAdded={handleRecurringAdded} />
            {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}
            {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
            {!loading && <RecurringIncomeTable items={recurring} onDeleted={handleRecurringDeleted} />}
          </>
        )}
      </main>
    </div>
  );
}
