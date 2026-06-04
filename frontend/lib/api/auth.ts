import type { LoginResponseDTO, MfaEnableResponse, MfaSetupResponse, MfaStatusResponse, MfaVerifyResponse, RegisterResponseDTO } from "./types";
import { BASE, formatErrorDetail, getRefreshToken, request } from "./_client";

export const authApi = {
  login: (email: string, password: string) =>
    request<LoginResponseDTO>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  // MFA (TOTP) — Audit #5
  mfaStatus: () => request<MfaStatusResponse>("/mfa/status"),

  mfaSetup: () => request<MfaSetupResponse>("/mfa/setup", { method: "POST" }),

  mfaEnable: (totp_code: string) =>
    request<MfaEnableResponse>("/mfa/enable", {
      method: "POST",
      body: JSON.stringify({ totp_code }),
    }),

  mfaDisable: (totp_code: string) =>
    request<{ detail: string }>("/mfa/disable", {
      method: "POST",
      body: JSON.stringify({ totp_code }),
    }),

  // pre_mfa_token Authorization header'inda yollanir — request() helper'i
  // localStorage'daki access_token'i kullanacagindan dogrudan fetch ile yapariz.
  mfaVerify: async (preMfaToken: string, payload: { totp_code?: string; recovery_code?: string }) => {
    const res = await fetch(`${BASE}/mfa/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${preMfaToken}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(formatErrorDetail(err.detail) || res.statusText);
    }
    return (await res.json()) as MfaVerifyResponse;
  },

  logout: (refreshToken?: string) => {
    // Saklı refresh token'ı blacklist'e gönder (FAZ C4 rotation + logout
    // birlikte → tüm token'lar iptal). Çağıran parametre verirse o öncelikli.
    const refresh = refreshToken ?? getRefreshToken();
    return request<{ detail: string }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refresh }),
    });
  },

  register: (
    email: string,
    password: string,
    risk_profile: string,
    age_confirmed: boolean,
    release_notes_opt_in = false,
    default_currency?: string,
  ) =>
    request<RegisterResponseDTO>("/auth/register", {
      method: "POST",
      // COMP-010 (FAZ H): age_confirmed zorunlu — backend False ise 422 doner.
      // release_notes_opt_in opsiyonel KVKK acik riza (varsayilan kapali).
      // v0.3.0: default_currency opsiyonel — verilmezse backend "TRY" varsayar.
      body: JSON.stringify({
        email,
        password,
        risk_profile,
        age_confirmed,
        release_notes_opt_in,
        ...(default_currency ? { default_currency } : {}),
      }),
    }),

  verifyEmail: (token: string) =>
    request<{ detail: string }>(`/auth/verify-email?token=${encodeURIComponent(token)}`),

  resendVerification: (email: string) =>
    request<{ detail: string }>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
};
