import type { IncomeDTO, IncomeDashboardDTO, IncomeInput, IncomeSummaryDTO, RealizeResultDTO, RecurringIncomeDTO, RecurringIncomeInput } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const incomesApi = {
  // Gelir takibi
  listIncomes: (params: { year?: number; month?: number; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.year !== undefined) q.set("year", String(params.year));
    if (params.month !== undefined) q.set("month", String(params.month));
    if (params.category) q.set("category", params.category);
    const qs = q.toString();
    return request<IncomeDTO[]>(`/income${qs ? `?${qs}` : ""}`);
  },
  createIncome: (payload: IncomeInput) => request<IncomeDTO>("/income", { method: "POST", body: JSON.stringify(payload) }),
  updateIncome: (id: number, payload: Partial<IncomeInput>) => request<IncomeDTO>(`/income/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteIncome: (id: number) => request<void>(`/income/${id}`, { method: "DELETE" }),
  getIncomeSummary: (year: number, month: number) => request<IncomeSummaryDTO>(`/income/summary?year=${year}&month=${month}`),

  // Periyodik gelir (recurring_incomes)
  getIncomeDashboard: (year: number, month: number) => request<IncomeDashboardDTO>(`/income/dashboard?year=${year}&month=${month}`),
  listRecurringIncomes: () => request<RecurringIncomeDTO[]>("/income/recurring"),
  createRecurringIncome: (payload: RecurringIncomeInput) => request<RecurringIncomeDTO>("/income/recurring", { method: "POST", body: JSON.stringify(payload) }),
  updateRecurringIncome: (id: number, payload: Partial<RecurringIncomeInput>) =>
    request<RecurringIncomeDTO>(`/income/recurring/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteRecurringIncome: (id: number) => request<void>(`/income/recurring/${id}`, { method: "DELETE" }),
  realizeRecurringPeriod: (id: number, year: number, month: number) =>
    request<RealizeResultDTO>(`/income/recurring/${id}/realize`, {
      method: "POST",
      body: JSON.stringify({ year, month }),
    }),
  realizeRecurringPast: (id: number) => request<RealizeResultDTO>(`/income/recurring/${id}/realize-past`, { method: "POST" }),
  realizeAllRecurringPast: () => request<RealizeResultDTO>(`/income/recurring/realize-all-past`, { method: "POST" }),

  // Gelir Excel export/import
  exportIncomes: async (year?: number, month?: number) => {
    const token = getAccessToken();
    const q = new URLSearchParams();
    if (year !== undefined) q.set("year", String(year));
    if (month !== undefined) q.set("month", String(month));
    const qs = q.toString();
    const res = await fetch(`${BASE}/income/export${qs ? `?${qs}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "gelirler.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importIncomes: async (file: File): Promise<IncomeDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/income/import`, {
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
