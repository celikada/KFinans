import type { CashFlowMonthDetailDTO, CashFlowYearDTO } from "./types";
import { request } from "./_client";

export const cashFlowApi = {
  // Yıllık nakit akış (geçmiş + gelecek)
  getCashFlow: (year: number) => request<CashFlowYearDTO>(`/cash-flow?year=${year}`),
  // Tek bir ayın gelir/gider kalem dökümü (popup detayı)
  getCashFlowMonthDetail: (year: number, month: number) =>
    request<CashFlowMonthDetailDTO>(`/cash-flow/${year}/${month}/detail`),
};
