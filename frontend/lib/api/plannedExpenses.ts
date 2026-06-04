import type { ForecastResultDTO, PlannedExpenseDTO, PlannedExpenseInput, RealizeResultDTO } from "./types";
import { request } from "./_client";

export const plannedExpensesApi = {
  // Planlı ödemeler (Faz 3)
  listPlannedExpenses: () => request<PlannedExpenseDTO[]>("/planned-expenses"),

  createPlannedExpense: (payload: PlannedExpenseInput) =>
    request<PlannedExpenseDTO>("/planned-expenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updatePlannedExpense: (id: number, payload: Partial<PlannedExpenseInput>) =>
    request<PlannedExpenseDTO>(`/planned-expenses/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deletePlannedExpense: (id: number) => request<void>(`/planned-expenses/${id}`, { method: "DELETE" }),

  getForecast: (year: number) => request<ForecastResultDTO>(`/planned-expenses/forecast?year=${year}`),

  // Periyodik gider gerçekleştirme (income realize paraleli)
  realizePlannedPeriod: (id: number, year: number, month: number) =>
    request<RealizeResultDTO>(`/planned-expenses/${id}/realize`, {
      method: "POST",
      body: JSON.stringify({ year, month }),
    }),
  realizePlannedPast: (id: number) => request<RealizeResultDTO>(`/planned-expenses/${id}/realize-past`, { method: "POST" }),
};
