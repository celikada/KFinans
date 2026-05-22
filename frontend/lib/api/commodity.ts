import type { CommodityDTO, CommodityInput, CommoditySummaryDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

export const commodityApi = {
  // Kıymetli madenler
  getCommodities: () => request<CommoditySummaryDTO>("/portfolio/commodities"),
  createCommodity: (payload: CommodityInput) =>
    request<CommodityDTO>("/portfolio/commodities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCommodity: (id: number, payload: { quantity?: number; notes?: string | null }) =>
    request<CommodityDTO>(`/portfolio/commodities/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteCommodity: (id: number) => request<void>(`/portfolio/commodities/${id}`, { method: "DELETE" }),
  exportCommodities: () => downloadBlob("/portfolio/commodities/export", "altin-gumus.xlsx"),
  importCommodities: (file: File) => uploadForm<CommodityDTO[]>("/portfolio/commodities/import", file),
};
