import type { BesHoldingDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const besApi = {
  getBesHoldings: () => request<BesHoldingDTO[]>("/portfolio/bes/holdings"),

  saveBesHoldings: (holdings: BesHoldingDTO[]) =>
    request<BesHoldingDTO[]>("/portfolio/bes/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  exportBesHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/bes/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bes-holdingleri.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importBesHoldings: async (file: File): Promise<BesHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/bes/import`, {
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
