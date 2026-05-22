import type { AssetCatalogItem, LinkedSource, ManualCryptoCreateInput, ManualCryptoDTO, ManualCryptoSummaryDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const manualCryptoApi = {
  // Manuel kripto (API'siz borsalar — BinanceTR / iCrypex vs.)
  listManualCrypto: () => request<ManualCryptoSummaryDTO>("/manual-crypto"),
  createManualCrypto: (payload: ManualCryptoCreateInput) =>
    request<ManualCryptoDTO>("/manual-crypto", { method: "POST", body: JSON.stringify(payload) }),
  updateManualCrypto: (id: number, payload: Partial<ManualCryptoCreateInput>) =>
    request<ManualCryptoDTO>(`/manual-crypto/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteManualCrypto: (id: number) => request<void>(`/manual-crypto/${id}`, { method: "DELETE" }),

  exportManualCrypto: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/manual-crypto/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "manuel-kripto.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  searchAssetCatalog: (params: { q?: string; source?: LinkedSource; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q !== undefined) qs.set("q", params.q);
    if (params.source) qs.set("source", params.source);
    if (params.limit) qs.set("limit", String(params.limit));
    return request<AssetCatalogItem[]>(`/asset-catalog${qs.toString() ? `?${qs}` : ""}`);
  },

  importManualCrypto: async (file: File): Promise<{ imported: number; errors: string[] }> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/manual-crypto/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : res.statusText);
    }
    return res.json();
  },
};
