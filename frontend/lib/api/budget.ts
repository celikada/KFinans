import type { BudgetComparisonDTO, BudgetDTO } from "./types";
import { request } from "./_client";

export const budgetApi = {
  // Bütçe vs. Gerçekleşen
  listBudgets: () => request<BudgetDTO[]>("/budgets"),
  upsertBudget: (category: string, amount: number) =>
    request<BudgetDTO>(`/budgets/${category}`, {
      method: "PUT",
      body: JSON.stringify({ amount }),
    }),
  deleteBudget: (category: string) => request<void>(`/budgets/${category}`, { method: "DELETE" }),
  getBudgetComparison: (year: number, month: number) =>
    request<BudgetComparisonDTO[]>(`/budgets/comparison?year=${year}&month=${month}`),
};
