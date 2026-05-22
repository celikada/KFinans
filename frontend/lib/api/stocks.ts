import type { StockHoldingDTO, StockPositionDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const stocksApi = {
  getStockHoldings: () => request<StockHoldingDTO[]>("/portfolio/stocks/holdings"),
  saveStockHoldings: (holdings: StockHoldingDTO[]) =>
    request<StockHoldingDTO[]>("/portfolio/stocks/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),
  stockPreview: (holdings: StockHoldingDTO[]) =>
    request<StockPositionDTO[]>("/portfolio/stocks/preview", {
      method: "POST",
      body: JSON.stringify(holdings),
    }),
  exportStockHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/stocks/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hisse-senedi.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importStockMkk: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/stocks/import-mkk`, {
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
  importStockHoldings: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/stocks/import`, {
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
