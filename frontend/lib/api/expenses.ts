import type { ExpenseDTO, ExpenseInput, ExpenseSummaryDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

export const expensesApi = {
  // Harcama (Faz 3 MVP — manuel giris)
  listExpenses: (params: { year?: number; month?: number; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.year !== undefined) q.set("year", String(params.year));
    if (params.month !== undefined) q.set("month", String(params.month));
    if (params.category) q.set("category", params.category);
    const qs = q.toString();
    return request<ExpenseDTO[]>(`/expenses${qs ? `?${qs}` : ""}`);
  },

  createExpense: (payload: ExpenseInput) =>
    request<ExpenseDTO>("/expenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateExpense: (id: number, payload: Partial<ExpenseInput>) =>
    request<ExpenseDTO>(`/expenses/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deleteExpense: (id: number) => request<void>(`/expenses/${id}`, { method: "DELETE" }),

  getExpenseSummary: (year: number, month: number) =>
    request<ExpenseSummaryDTO>(`/expenses/summary?year=${year}&month=${month}`),

  // Harcama Excel export/import
  exportExpenses: (year?: number, month?: number) => {
    const q = new URLSearchParams();
    if (year !== undefined) q.set("year", String(year));
    if (month !== undefined) q.set("month", String(month));
    const qs = q.toString();
    return downloadBlob(`/expenses/export${qs ? `?${qs}` : ""}`, "harcamalar.xlsx");
  },

  importExpenses: (file: File) => uploadForm<ExpenseDTO[]>("/expenses/import", file),
};
