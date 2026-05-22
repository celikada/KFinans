import type { CommodityDTO, CommodityInput, CommoditySummaryDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

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
  exportCommodities: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/commodities/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "altin-gumus.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importCommodities: async (file: File): Promise<CommodityDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/commodities/import`, {
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
