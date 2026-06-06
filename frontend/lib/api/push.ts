import type { PushSubscriptionInput, PushTestResultDTO, VapidPublicKeyDTO } from "./types";
import { request } from "./_client";

export const pushApi = {
  // VAPID application server public key (base64url). Used by PushManager.subscribe.
  getVapidPublicKey: () => request<VapidPublicKeyDTO>("/push/vapid-public-key"),

  // Register a browser push subscription on the backend (201).
  subscribePush: (sub: PushSubscriptionInput) =>
    request<void>("/push/subscribe", {
      method: "POST",
      body: JSON.stringify(sub),
    }),

  // Remove a subscription by endpoint (204).
  unsubscribePush: (endpoint: string) =>
    request<void>("/push/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint }),
    }),

  // Dispatch a test notification to the current user's subscriptions.
  sendTestPush: () => request<PushTestResultDTO>("/push/test", { method: "POST" }),
};
