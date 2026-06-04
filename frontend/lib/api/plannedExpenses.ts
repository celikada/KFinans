import type { ForecastResultDTO, PeriodsResultDTO, PlannedExpenseDTO, PlannedExpenseInput, RealizeResultDTO, UnrealizeResultDTO } from "./types";
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

  // Dönem durumları (pending/realized/skipped) — realize/skip geri alma ekrani icin
  getPlannedPeriods: (id: number) => request<PeriodsResultDTO>(`/planned-expenses/${id}/periods`),

  // Realize geri al: o döneme ait gerçek harcama kaydini sil
  unrealizePlannedPeriod: (id: number, year: number, month: number) =>
    request<UnrealizeResultDTO>(`/planned-expenses/${id}/unrealize`, {
      method: "POST",
      body: JSON.stringify({ year, month }),
    }),
};
