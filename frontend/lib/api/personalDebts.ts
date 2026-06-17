import type { PersonalDebtDTO, PersonalDebtInput, PersonalDebtListDTO } from "./types";
import { request } from "./_client";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export const personalDebtsApi = {
  listPersonalDebts: (includeSettled = false) =>
    request<PersonalDebtListDTO>(
      `/personal-debts?include_settled=${includeSettled}&display=${getDefaultCurrency()}`,
    ),
  createPersonalDebt: (payload: PersonalDebtInput) =>
    request<PersonalDebtDTO>("/personal-debts", { method: "POST", body: JSON.stringify(payload) }),
  updatePersonalDebt: (id: number, payload: Partial<PersonalDebtInput>) =>
    request<PersonalDebtDTO>(`/personal-debts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  settlePersonalDebt: (id: number) =>
    request<PersonalDebtDTO>(`/personal-debts/${id}/settle`, { method: "POST" }),
  deletePersonalDebt: (id: number) => request<void>(`/personal-debts/${id}`, { method: "DELETE" }),
};
