"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, PlannedExpenseDTO, ForecastResultDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { PlannedForm } from "./_components/PlannedForm";
import { PlannedList } from "./_components/PlannedList";
import { YearlyForecast } from "./_components/YearlyForecast";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function PlannedPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [items, setItems] = useState<PlannedExpenseDTO[]>([]);
  const [forecast, setForecast] = useState<ForecastResultDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, fc] = await Promise.all([
        api.listPlannedExpenses(),
        api.getForecast(year),
      ]);
      setItems(list);
      setForecast(fc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function handleAdded(pe: PlannedExpenseDTO) {
    setItems((prev) => [...prev, pe].sort((a, b) => a.start_date.localeCompare(b.start_date)));
    refresh();
  }

  function handleDeleted(id: number) {
    setItems((prev) => prev.filter((p) => p.id !== id));
    refresh();
  }

  const yearTotal = forecast ? parseFloat(forecast.year_total) : 0;
  const monthlyAvg = yearTotal > 0 ? yearTotal / 12 : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.planned")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Özet + yıl seçici */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-wrap items-center gap-6 justify-between">
          <div className="flex gap-8">
            <div>
              <p className="text-xs text-gray-400 mb-1">Yıllık toplam</p>
              <TLValue tl={yearTotal} className="text-3xl font-bold text-gray-900" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">Aylık ortalama</p>
              <p className="text-xl font-semibold text-gray-600">{fmtTL(monthlyAvg)} ₺</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setYear((y) => y - 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50"
            >
              ‹
            </button>
            <span className="text-sm font-semibold text-gray-700 w-12 text-center">{year}</span>
            <button
              onClick={() => setYear((y) => y + 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50"
            >
              ›
            </button>
          </div>
        </div>

        <PlannedForm onAdded={handleAdded} />

        {error && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {loading && (
          <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>
        )}

        {!loading && forecast && <YearlyForecast data={forecast} year={year} />}

        {!loading && <PlannedList items={items} onDeleted={handleDeleted} />}
      </main>
    </div>
  );
}
