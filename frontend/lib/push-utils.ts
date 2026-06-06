// Web Push helpers — VAPID key + subscription key encoding.
//
// PushManager.subscribe() requires the VAPID application server key as a
// Uint8Array, while the backend serves it as a base64url string. The browser
// also exposes subscription keys (p256dh/auth) as ArrayBuffers that must be
// base64url-encoded before being sent back to the backend.

/**
 * Convert a base64url-encoded VAPID public key into a Uint8Array suitable for
 * `PushManager.subscribe({ applicationServerKey })`.
 */
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replaceAll("-", "+").replaceAll("_", "/");
  const rawData = globalThis.atob(base64);
  // Back the view with a concrete ArrayBuffer so the type is Uint8Array<ArrayBuffer>,
  // which PushManager.subscribe()'s applicationServerKey (BufferSource) accepts.
  const buffer = new ArrayBuffer(rawData.length);
  const outputArray = new Uint8Array(buffer);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.codePointAt(i) ?? 0;
  }
  return outputArray;
}

/**
 * Encode a subscription key ArrayBuffer (p256dh / auth) as a base64url string
 * (no padding, URL-safe alphabet) for transport to the backend.
 */
export function arrayBufferToBase64Url(buffer: ArrayBuffer | null): string {
  if (!buffer) return "";
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCodePoint(byte);
  }
  return globalThis.btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
