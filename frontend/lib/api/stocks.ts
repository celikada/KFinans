import type { StockHoldingDTO, StockPositionDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

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
  exportStockHoldings: () => downloadBlob("/portfolio/stocks/export", "hisse-senedi.xlsx"),
  importStockMkk: (file: File) => uploadForm<StockHoldingDTO[]>("/portfolio/stocks/import-mkk", file),
  importStockHoldings: (file: File) => uploadForm<StockHoldingDTO[]>("/portfolio/stocks/import", file),
};
