import type { CashCreateInput, CashDTO, CashSummaryDTO } from "./types";
import { request } from "./_client";

export const cashApi = {
  // Nakit (Faz 3 — manuel giriş)
  listCash: () => request<CashSummaryDTO>("/cash"),
  createCash: (payload: CashCreateInput) => request<CashDTO>("/cash", { method: "POST", body: JSON.stringify(payload) }),
  updateCash: (id: number, payload: Partial<CashCreateInput>) =>
    request<CashDTO>(`/cash/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCash: (id: number) => request<void>(`/cash/${id}`, { method: "DELETE" }),
};
