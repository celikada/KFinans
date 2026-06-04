import type { ReleaseOptInStatusDTO, ReleaseSendResultDTO } from "./types";
import { BASE, request } from "./_client";

export const releaseApi = {
  // Kullanıcı kendi abonelik durumunu okur (ayarlar sayfası).
  getReleaseOptIn: () => request<ReleaseOptInStatusDTO>("/release-notes/opt-in"),

  // Sürüm bildirimi aboneliğini aç/kapat.
  setReleaseOptIn: (opt_in: boolean) =>
    request<ReleaseOptInStatusDTO>("/release-notes/opt-in", {
      method: "PUT",
      body: JSON.stringify({ opt_in }),
    }),

  // Admin: belirli bir sürümün notlarını opt-in kullanıcılara gönder.
  sendReleaseNotes: (version: string) =>
    request<ReleaseSendResultDTO>("/release-notes/send", {
      method: "POST",
      body: JSON.stringify({ version }),
    }),

  // AUTH YOK: mail içindeki token ile aboneliği iptal eder.
  // Backend HTML döner; burada sadece HTTP başarısını kontrol ederiz.
  unsubscribe: async (token: string): Promise<boolean> => {
    const res = await fetch(`${BASE}/release-notes/unsubscribe?token=${encodeURIComponent(token)}`);
    return res.ok;
  },
};
