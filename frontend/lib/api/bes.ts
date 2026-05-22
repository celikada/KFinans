import type { BesHoldingDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

export const besApi = {
  getBesHoldings: () => request<BesHoldingDTO[]>("/portfolio/bes/holdings"),

  saveBesHoldings: (holdings: BesHoldingDTO[]) =>
    request<BesHoldingDTO[]>("/portfolio/bes/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  exportBesHoldings: () => downloadBlob("/portfolio/bes/export", "bes-holdingleri.xlsx"),
  importBesHoldings: (file: File) => uploadForm<BesHoldingDTO[]>("/portfolio/bes/import", file),
};
