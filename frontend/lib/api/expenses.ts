import type { ExpenseDTO, ExpenseInput, ExpenseSummaryDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

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
  exportExpenses: async (year?: number, month?: number) => {
    const token = getAccessToken();
    const q = new URLSearchParams();
    if (year !== undefined) q.set("year", String(year));
    if (month !== undefined) q.set("month", String(month));
    const qs = q.toString();
    const res = await fetch(`${BASE}/expenses/export${qs ? `?${qs}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "harcamalar.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importExpenses: async (file: File): Promise<ExpenseDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/expenses/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },
};
