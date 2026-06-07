import type { BudgetComparisonDTO, BudgetDTO, CurrencyType } from "./types";
import { request } from "./_client";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export const budgetApi = {
  // Bütçe vs. Gerçekleşen
  listBudgets: () => request<BudgetDTO[]>("/budgets"),
  // v0.3.0: currency opsiyonel — verilmezse backend default (TRY).
  upsertBudget: (category: string, amount: number, currency?: CurrencyType) =>
    request<BudgetDTO>(`/budgets/${category}`, {
      method: "PUT",
      body: JSON.stringify({ amount, ...(currency ? { currency } : {}) }),
    }),
  deleteBudget: (category: string) => request<void>(`/budgets/${category}`, { method: "DELETE" }),
  // Faz B: display param → backend tarihsel-kur bazlı *_display alanları döner.
  getBudgetComparison: (year: number, month: number) =>
    request<BudgetComparisonDTO[]>(`/budgets/comparison?year=${year}&month=${month}&display=${getDefaultCurrency()}`),
};
