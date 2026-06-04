import type { CurrencyType, UserMeDTO } from "./types";
import { request } from "./_client";

export const userApi = {
  getMe: () => request<UserMeDTO>("/user/me"),

  // v0.3.0: default_currency opsiyonel — verilirse varsayilan para birimi guncellenir.
  updateProfile: (risk_profile: string, default_currency?: CurrencyType) =>
    request<UserMeDTO>("/user/profile", {
      method: "PUT",
      body: JSON.stringify({ risk_profile, ...(default_currency ? { default_currency } : {}) }),
    }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("/user/password", {
      method: "PUT",
      body: JSON.stringify({ current_password, new_password }),
    }),

  deleteAccount: () => request<{ detail: string }>("/user/me", { method: "DELETE" }),
};
