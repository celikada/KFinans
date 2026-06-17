"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/app/_components/PageHeader";
import { MonthSelector } from "@/app/dashboard/expenses/_components/MonthSelector";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { MonthlyBuckets } from "./_components/MonthlyBuckets";
import { MonthNotePanel } from "./_components/MonthNotePanel";
import { BudgetGrid } from "./_components/BudgetGrid";
import { BudgetProjection } from "./_components/BudgetProjection";
import { PersonalDebts } from "./_components/PersonalDebts";
import { BucketSettingsModal } from "./_components/BucketSettingsModal";
import { ClassicBudgetSection } from "./_components/ClassicBudgetSection";

type Tab = "monthly" | "grid" | "projection" | "debts";
const TABS: Tab[] = ["monthly", "grid", "projection", "debts"];

function tabFrom(value: string | null): Tab {
  return TABS.includes(value as Tab) ? (value as Tab) : "monthly";
}

function YearSelector({ year, onChange }: { readonly year: number; readonly onChange: (y: number) => void }) {
  const current = new Date().getFullYear();
  const years = [current - 2, current - 1, current, current + 1];
  return (
    <select
      value={year}
      onChange={(e) => onChange(Number.parseInt(e.target.value))}
      className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white"
      aria-label="Yıl"
    >
      {years.map((y) => (
        <option key={y} value={y}>{y}</option>
      ))}
    </select>
  );
}

export default function BudgetPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const now = new Date();
  const [tab, setTab] = useState<Tab>(tabFrom(searchParams.get("tab")));
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // MonthlyBuckets'ı ayar kaydından sonra yeniden mount etmek için anahtar.
  const [refreshKey, setRefreshKey] = useState(0);

  function changeTab(next: Tab) {
    setTab(next);
    router.replace(`/dashboard/budget?tab=${next}`, { scroll: false });
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.budget")} />

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Sekmeler + ayar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
            {TABS.map((tb) => (
              <button
                key={tb}
                type="button"
                onClick={() => changeTab(tb)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                  tab === tb ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {t(`content.budgetV2.tab${tb.charAt(0).toUpperCase() + tb.slice(1)}`)}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            {tab === "monthly" && (
              <MonthSelector year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />
            )}
            {(tab === "grid" || tab === "projection") && <YearSelector year={year} onChange={setYear} />}
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white hover:bg-gray-50"
              title={t("content.budgetV2.settings.title")}
              aria-label={t("content.budgetV2.settings.title")}
            >
              ⚙️
            </button>
          </div>
        </div>

        {tab === "monthly" && (
          <div className="space-y-6" key={`monthly-${refreshKey}`}>
            <MonthlyBuckets year={year} month={month} />
            <MonthNotePanel year={year} month={month} />
            <ClassicBudgetSection year={year} month={month} />
          </div>
        )}
        {tab === "grid" && <BudgetGrid year={year} key={`grid-${refreshKey}`} />}
        {tab === "projection" && <BudgetProjection year={year} />}
        {tab === "debts" && <PersonalDebts />}
      </main>

      {settingsOpen && (
        <BucketSettingsModal
          onClose={() => setSettingsOpen(false)}
          onSaved={() => setRefreshKey((k) => k + 1)}
        />
      )}
    </div>
  );
}
