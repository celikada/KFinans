"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { BudgetComparisonDTO } from "@/lib/api";
import { useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { BudgetForm } from "./BudgetForm";
import { ComparisonTable } from "./ComparisonTable";

interface Props {
  readonly year: number;
  readonly month: number;
}

/**
 * Klasik düz kategori-limiti bütçesi (eski `budgets` tablosu). Dashboard ve
 * Giderler sayfasındaki "X kategori aşıldı" uyarıları bu limitleri okur; bu yüzden
 * limit girişi korunur. Yeni ızgara/kova planlamasının yanında basit uyarı eşiği
 * olarak çalışır — daraltılabilir bölümde.
 */
export function ClassicBudgetSection({ year, month }: Props) {
  const { t } = useTranslation();
  const displayCurrency = useDisplayCurrency();
  const [rows, setRows] = useState<BudgetComparisonDTO[]>([]);

  const refresh = useCallback(async () => {
    try {
      setRows(await api.getBudgetComparison(year, month));
    } catch {
      setRows([]);
    }
  }, [year, month, displayCurrency]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(category: string) {
    await api.deleteBudget(category).catch(() => undefined);
    refresh();
  }

  return (
    <details className="bg-white rounded-2xl border border-gray-100 shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-gray-600">
        {t("content.budgetV2.classic.title")}
      </summary>
      <div className="px-5 pb-5 space-y-4">
        <p className="text-xs text-gray-400">{t("content.budgetV2.classic.hint")}</p>
        <BudgetForm onSaved={refresh} />
        <ComparisonTable rows={rows} onDelete={handleDelete} />
      </div>
    </details>
  );
}
