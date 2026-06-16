import type {
  ProviderDTO,
  SubscriptionBillDTO,
  SubscriptionBillIssueInput,
  SubscriptionBillPayInput,
  SubscriptionDTO,
  SubscriptionInput,
  SubscriptionPeriodDTO,
  SubscriptionRemindersDTO,
  SubscriptionSummaryDTO,
} from "./types";
import { request } from "./_client";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export const subscriptionsApi = {
  // Abonelikler / fatura takibi (utility) — feature/subscriptions-utility.
  getProviders: () => request<ProviderDTO[]>("/subscriptions/providers"),

  listSubscriptions: () => request<SubscriptionDTO[]>("/subscriptions"),

  createSubscription: (payload: SubscriptionInput) =>
    request<SubscriptionDTO>("/subscriptions", { method: "POST", body: JSON.stringify(payload) }),

  updateSubscription: (id: number, payload: Partial<SubscriptionInput>) =>
    request<SubscriptionDTO>(`/subscriptions/${id}`, { method: "PUT", body: JSON.stringify(payload) }),

  deleteSubscription: (id: number) => request<void>(`/subscriptions/${id}`, { method: "DELETE" }),

  // Özet (display param → görüntüleme para biriminde tahminler)
  getSubscriptionSummary: (display: string = getDefaultCurrency()) =>
    request<SubscriptionSummaryDTO>(`/subscriptions/summary?display=${display}`),

  // Dönem listesi (en yeni üstte; bu ay fatura yoksa sentezlenmiş budget satırı başta)
  listSubscriptionBills: (id: number) =>
    request<SubscriptionPeriodDTO[]>(`/subscriptions/${id}/bills`),

  // budget → issued (aynı dönem varsa günceller)
  issueSubscriptionBill: (id: number, payload: SubscriptionBillIssueInput) =>
    request<SubscriptionBillDTO>(`/subscriptions/${id}/bills/issue`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // issued → paid (payment_method=credit_card ise credit_card_id ZORUNLU)
  paySubscriptionBill: (id: number, billId: number, payload: SubscriptionBillPayInput) =>
    request<SubscriptionBillDTO>(`/subscriptions/${id}/bills/${billId}/pay`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // paid → issued (bağlı gider silinir)
  unpaySubscriptionBill: (id: number, billId: number) =>
    request<SubscriptionBillDTO>(`/subscriptions/${id}/bills/${billId}/unpay`, { method: "POST" }),

  // issued → budget (ödenmişse 409; önce unpay)
  deleteSubscriptionBill: (id: number, billId: number) =>
    request<void>(`/subscriptions/${id}/bills/${billId}`, { method: "DELETE" }),

  // Girişte hatırlatmalar: ödenecek faturalar + fatura girilecek dönemler
  getSubscriptionReminders: () => request<SubscriptionRemindersDTO>("/subscriptions/reminders"),
};
