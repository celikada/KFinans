import type { CashFlowMonthDetailDTO, CashFlowYearDTO } from "./types";
import { request } from "./_client";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export const cashFlowApi = {
  // Yıllık nakit akış (geçmiş + gelecek). Faz B: display param → *_display alanları.
  getCashFlow: (year: number) => request<CashFlowYearDTO>(`/cash-flow?year=${year}&display=${getDefaultCurrency()}`),
  // Tek bir ayın gelir/gider kalem dökümü (popup detayı)
  getCashFlowMonthDetail: (year: number, month: number) =>
    request<CashFlowMonthDetailDTO>(`/cash-flow/${year}/${month}/detail?display=${getDefaultCurrency()}`),
};
