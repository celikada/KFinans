import type { AssetCatalogItem, LinkedSource, ManualCryptoCreateInput, ManualCryptoDTO, ManualCryptoSummaryDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

export const manualCryptoApi = {
  // Manuel kripto (API'siz borsalar — BinanceTR / iCrypex vs.)
  listManualCrypto: () => request<ManualCryptoSummaryDTO>("/manual-crypto"),
  createManualCrypto: (payload: ManualCryptoCreateInput) =>
    request<ManualCryptoDTO>("/manual-crypto", { method: "POST", body: JSON.stringify(payload) }),
  updateManualCrypto: (id: number, payload: Partial<ManualCryptoCreateInput>) =>
    request<ManualCryptoDTO>(`/manual-crypto/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteManualCrypto: (id: number) => request<void>(`/manual-crypto/${id}`, { method: "DELETE" }),

  exportManualCrypto: () => downloadBlob("/manual-crypto/export", "manuel-kripto.xlsx"),
  importManualCrypto: (file: File) => uploadForm<{ imported: number; errors: string[] }>("/manual-crypto/import", file),

  searchAssetCatalog: (params: { q?: string; source?: LinkedSource; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q !== undefined) qs.set("q", params.q);
    if (params.source) qs.set("source", params.source);
    if (params.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AssetCatalogItem[]>(`/asset-catalog${suffix}`);
  },
};
