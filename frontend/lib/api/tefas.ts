import type { TefasHoldingDTO, TefasPosition } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const tefasApi = {
  getTefasHoldings: () => request<TefasHoldingDTO[]>("/portfolio/tefas/holdings"),

  saveTefasHoldings: (holdings: TefasHoldingDTO[]) =>
    request<TefasHoldingDTO[]>("/portfolio/tefas/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  tefasPreview: (holdings: TefasHoldingDTO[]) =>
    request<TefasPosition[]>("/portfolio/tefas/preview", {
      method: "POST",
      body: JSON.stringify(holdings),
    }),

  exportTefasHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/tefas/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tefas-holdingleri.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importTefasHoldings: async (file: File): Promise<TefasHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/tefas/import`, {
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

  importTefasMkk: async (file: File): Promise<TefasHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/tefas/import-mkk`, {
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
