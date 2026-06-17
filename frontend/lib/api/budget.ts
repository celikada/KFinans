import type {
  BudgetComparisonDTO,
  BudgetDTO,
  BudgetGridResponse,
  BudgetSettingsDTO,
  CurrencyType,
  MonthlyBudgetResponse,
  MonthNoteDTO,
} from "./types";
import { request } from "./_client";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export const budgetApi = {
  // Bütçe vs. Gerçekleşen (eski düz model — korunur)
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

  // ── Bütçe v2 (hibrit) ──
  // 12 aylık × kategori ızgara: planlanan (budget_lines) + gerçekleşen (expenses).
  getBudgetGrid: (year: number) =>
    request<BudgetGridResponse>(`/budgets/grid?year=${year}&display=${getDefaultCurrency()}`),
  upsertBudgetLine: (year: number, month: number, category: string, amount: number, currency?: CurrencyType) =>
    request<BudgetDTO>(`/budgets/grid/${year}/${month}/${category}`, {
      method: "PUT",
      body: JSON.stringify({ amount, ...(currency ? { currency } : {}) }),
    }),
  deleteBudgetLine: (year: number, month: number, category: string) =>
    request<void>(`/budgets/grid/${year}/${month}/${category}`, { method: "DELETE" }),

  // Aylık 3-kova (Fundamental/Fun/Future You) budget-vs-actual + gelir + NET.
  getMonthlyBudget: (year: number, month: number) =>
    request<MonthlyBudgetResponse>(`/budgets/monthly?year=${year}&month=${month}&display=${getDefaultCurrency()}`),

  // Kova ayarı (oranlar + kategori→kova override).
  getBudgetSettings: () => request<BudgetSettingsDTO>("/budgets/settings"),
  updateBudgetSettings: (payload: {
    fundamental_ratio: number;
    fun_ratio: number;
    future_ratio: number;
    category_buckets?: Record<string, string> | null;
  }) => request<BudgetSettingsDTO>("/budgets/settings", { method: "PUT", body: JSON.stringify(payload) }),

  // Aylık serbest metin (analiz + aksiyon planı).
  getMonthNote: (year: number, month: number) => request<MonthNoteDTO>(`/budgets/notes/${year}/${month}`),
  upsertMonthNote: (year: number, month: number, analysis: string | null, action_plan: string | null) =>
    request<MonthNoteDTO>(`/budgets/notes/${year}/${month}`, {
      method: "PUT",
      body: JSON.stringify({ analysis, action_plan }),
    }),
};
