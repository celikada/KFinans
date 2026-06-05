import type { CryptoPositionDTO, SnapshotHealthIssue, SnapshotHistoryDTO } from "./types";
import { request } from "./_client";

export const portfolioApi = {
  getCryptoPositions: () => request<{ positions: CryptoPositionDTO[]; errors: Record<string, string> }>("/portfolio/crypto"),

  previewSnapshot: () =>
    request<{
      total_value_tl: string;
      asset_count: number;
      issues: SnapshotHealthIssue[];
      usd_try_rate: string | null;
      saved: boolean;
    }>("/portfolio/snapshot/preview", { method: "POST" }),

  createSnapshot: (force = false) =>
    request<{
      id: string;
      snapshot_date: string;
      total_value_tl: string;
      usd_try_rate?: string | null;
      health_issues?: SnapshotHealthIssue[] | null;
      asset_positions: unknown[];
    }>(`/portfolio/snapshot${force ? "?force=true" : ""}`, { method: "POST" }),

  getPortfolioHistory: (params: { limit?: number; year?: number } = {}) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(params.limit ?? 100));
    if (params.year !== undefined) qs.set("year", String(params.year));
    return request<SnapshotHistoryDTO[]>(`/portfolio/history?${qs}`);
  },

  getPortfolioHistoryYears: () => request<number[]>("/portfolio/history/years"),

  deleteSnapshot: (snapshotDate: string) => request<void>(`/portfolio/snapshot/${snapshotDate}`, { method: "DELETE" }),

  getUsdRate: () => request<{ usd_try: string }>("/portfolio/usd-rate"),

  // v0.3.0 görüntüleme para birimi: tüm desteklenen kurlar (1 birim = X TL)
  getRates: () => request<{ rates: Record<string, string> }>("/portfolio/rates"),
};
