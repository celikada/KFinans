import type { PendingResponseDTO, RecurringKind } from "./types";
import { request } from "./_client";

export const recurringApi = {
  // Dashboard popup: tarihi geçmiş + işaretlenmemiş periyodik gelir/gider dönemleri
  getPendingRealizations: () => request<PendingResponseDTO>("/recurring/pending"),
  // Bir dönemi "gerçekleşmeyecek" işaretle
  skipRecurring: (kind: RecurringKind, refId: number, year: number, month: number) =>
    request<{ id: number }>("/recurring/skips", {
      method: "POST",
      body: JSON.stringify({ kind, ref_id: refId, year, month }),
    }),
};
