import type { CreditCardDetailDTO, CreditCardDTO, CreditCardInput, CreditCardSummaryDTO, InstallmentDTO, InstallmentInput, StatementDTO, StatementInput } from "./types";
import { request } from "./_client";

export const creditCardsApi = {
  // Kredi kartları (Faz 3 — manuel giriş)
  listCreditCards: () => request<CreditCardSummaryDTO>("/credit-cards"),
  createCreditCard: (payload: CreditCardInput) =>
    request<CreditCardDTO>("/credit-cards", { method: "POST", body: JSON.stringify(payload) }),
  updateCreditCard: (id: number, payload: Partial<CreditCardInput>) =>
    request<CreditCardDTO>(`/credit-cards/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCreditCard: (id: number) => request<void>(`/credit-cards/${id}`, { method: "DELETE" }),
  getCreditCardDetail: (id: number) => request<CreditCardDetailDTO>(`/credit-cards/${id}`),

  // Ekstreler
  createStatement: (cardId: number, payload: StatementInput) =>
    request<StatementDTO>(`/credit-cards/${cardId}/statements`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateStatement: (cardId: number, statementId: number, payload: Partial<StatementInput>) =>
    request<StatementDTO>(`/credit-cards/${cardId}/statements/${statementId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteStatement: (cardId: number, statementId: number) =>
    request<void>(`/credit-cards/${cardId}/statements/${statementId}`, { method: "DELETE" }),

  // Taksitler
  createInstallment: (cardId: number, payload: InstallmentInput) =>
    request<InstallmentDTO>(`/credit-cards/${cardId}/installments`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateInstallment: (cardId: number, installmentId: number, payload: Partial<InstallmentInput>) =>
    request<InstallmentDTO>(`/credit-cards/${cardId}/installments/${installmentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteInstallment: (cardId: number, installmentId: number) =>
    request<void>(`/credit-cards/${cardId}/installments/${installmentId}`, { method: "DELETE" }),
};
