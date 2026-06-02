import type { IntegrationDTO } from "./types";
import { downloadBlobPost, request, uploadForm } from "./_client";

export const integrationsApi = {
  getIntegrations: () => request<IntegrationDTO[]>("/integrations"),

  addIntegration: (provider: string, api_key: string, api_secret?: string, extra_token?: string) =>
    request<IntegrationDTO>("/integrations", {
      method: "POST",
      body: JSON.stringify({ provider, api_key, api_secret, extra_token }),
    }),

  removeIntegration: (provider: string) => request<void>(`/integrations/${provider}`, { method: "DELETE" }),

  // Tam (açık) API anahtarlarını şifre doğrulamalı dışa aktar; yanlış şifre → 403, anahtar verilmez.
  exportIntegrationsFull: (password: string) =>
    downloadBlobPost("/integrations/export", { password }, "kripto-api-anahtarlari.xlsx"),
  importIntegrations: (file: File) => uploadForm<IntegrationDTO[]>("/integrations/import", file),
};
