import type { UserMeDTO } from "./types";
import { request } from "./_client";

export const userApi = {
  getMe: () => request<UserMeDTO>("/user/me"),

  updateProfile: (risk_profile: string) =>
    request<UserMeDTO>("/user/profile", {
      method: "PUT",
      body: JSON.stringify({ risk_profile }),
    }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("/user/password", {
      method: "PUT",
      body: JSON.stringify({ current_password, new_password }),
    }),

  deleteAccount: () => request<{ detail: string }>("/user/me", { method: "DELETE" }),
};
