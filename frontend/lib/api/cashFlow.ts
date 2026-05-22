import type { CashFlowYearDTO } from "./types";
import { request } from "./_client";

export const cashFlowApi = {
  // Yıllık nakit akış (geçmiş + gelecek)
  getCashFlow: (year: number) => request<CashFlowYearDTO>(`/cash-flow?year=${year}`),
};
