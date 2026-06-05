import type { CreditCardDetailDTO, CreditCardDTO, CreditCardInput, CreditCardRemindersDTO, CreditCardSummaryDTO, InstallmentDTO, InstallmentInput, ParsedStatementDTO, StatementDTO, StatementImportCommitInput, StatementInput } from "./types";
import { request, uploadForm } from "./_client";

export const creditCardsApi = {
  // Kredi kartları (Faz 3 — manuel giriş)
  listCreditCards: () => request<CreditCardSummaryDTO>("/credit-cards"),
  // Girişte hatırlatmalar: ekstre yüklenmemiş kartlar + ödemesi yaklaşan ekstreler
  getCreditCardReminders: () => request<CreditCardRemindersDTO>("/credit-cards/reminders"),
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

  // Ekstre (PDF) import — preview (DB yazmaz) + commit (kalıcılaştır)
  previewStatementImport: (file: File) =>
    uploadForm<ParsedStatementDTO>("/credit-cards/import-statement/preview", file),
  commitStatementImport: (payload: StatementImportCommitInput) =>
    request<CreditCardDetailDTO>("/credit-cards/import-statement/commit", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
