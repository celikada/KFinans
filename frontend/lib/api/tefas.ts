import type { TefasHoldingDTO, TefasPosition } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

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

  exportTefasHoldings: () => downloadBlob("/portfolio/tefas/export", "tefas-holdingleri.xlsx"),
  importTefasHoldings: (file: File) => uploadForm<TefasHoldingDTO[]>("/portfolio/tefas/import", file),
  importTefasMkk: (file: File) => uploadForm<TefasHoldingDTO[]>("/portfolio/tefas/import-mkk", file),
};
