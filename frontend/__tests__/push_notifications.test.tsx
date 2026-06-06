import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

const getVapidPublicKey = vi.fn();
const subscribePush = vi.fn();
const unsubscribePush = vi.fn();
const sendTestPush = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getVapidPublicKey: (...a: unknown[]) => getVapidPublicKey(...a),
    subscribePush: (...a: unknown[]) => subscribePush(...a),
    unsubscribePush: (...a: unknown[]) => unsubscribePush(...a),
    sendTestPush: (...a: unknown[]) => sendTestPush(...a),
  },
}));

import { PushNotifications } from "@/app/dashboard/settings/_components/PushNotifications";

// ─── Web API mocks ──────────────────────────────────────────────
function makeKey() {
  return new Uint8Array([1, 2, 3]).buffer;
}

function installSupport(existingSub: object | null) {
  const subscription = {
    endpoint: "https://push.example/abc",
    getKey: () => makeKey(),
    unsubscribe: vi.fn().mockResolvedValue(true),
  };
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(existingSub),
    subscribe: vi.fn().mockResolvedValue(subscription),
  };
  const registration = { pushManager };
  vi.stubGlobal("navigator", {
    userAgent: "Mozilla/5.0 (Windows)",
    serviceWorker: { ready: Promise.resolve(registration) },
  });
  // Presence of these globals is what the support check inspects.
  vi.stubGlobal("PushManager", function PushManager() {});
  return { subscription, pushManager };
}

function installNotification(result: NotificationPermission) {
  const Notif = vi.fn() as unknown as typeof Notification;
  (Notif as unknown as { requestPermission: () => Promise<NotificationPermission> }).requestPermission =
    vi.fn().mockResolvedValue(result);
  vi.stubGlobal("Notification", Notif);
}

beforeEach(() => {
  vi.restoreAllMocks();
  getVapidPublicKey.mockReset().mockResolvedValue({ public_key: "aGVsbG8" });
  subscribePush.mockReset().mockResolvedValue(undefined);
  unsubscribePush.mockReset().mockResolvedValue(undefined);
  sendTestPush.mockReset().mockResolvedValue({ sent: 1 });
});

describe("PushNotifications", () => {
  it("shows unsupported message when service worker missing", () => {
    // No `serviceWorker` on navigator → support check fails, effect returns early.
    vi.stubGlobal("navigator", { userAgent: "x" });
    render(<PushNotifications />);
    expect(screen.getByText("content.settings.push.unsupported")).toBeInTheDocument();
  });

  it("reflects an existing subscription on mount (toggle on + test button)", async () => {
    installSupport({ endpoint: "x" });
    installNotification("granted");
    render(<PushNotifications />);
    await waitFor(() =>
      expect(screen.getByText("content.settings.push.sendTest")).toBeInTheDocument(),
    );
  });

  it("enables: requests permission, subscribes and registers with backend", async () => {
    const { pushManager } = installSupport(null);
    installNotification("granted");
    render(<PushNotifications />);
    await waitFor(() => expect(pushManager.getSubscription).toHaveBeenCalled());

    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "content.settings.push.enable" }));

    await waitFor(() => expect(subscribePush).toHaveBeenCalled());
    expect(getVapidPublicKey).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    const payload = subscribePush.mock.calls[0][0];
    expect(payload.endpoint).toBe("https://push.example/abc");
    expect(payload.keys.p256dh).toBeTruthy();
    expect(payload.user_agent).toContain("Mozilla");
  });

  it("permission denied → shows error, no subscribe", async () => {
    installSupport(null);
    installNotification("denied");
    render(<PushNotifications />);
    const user = userEvent.setup({ delay: null });
    await user.click(screen.getByRole("button", { name: "content.settings.push.enable" }));
    await waitFor(() =>
      expect(screen.getByText("content.settings.push.permissionDenied")).toBeInTheDocument(),
    );
    expect(subscribePush).not.toHaveBeenCalled();
  });

  it("disables: unsubscribes from backend and browser", async () => {
    const { subscription, pushManager } = installSupport({ endpoint: "x" });
    pushManager.getSubscription.mockResolvedValue(subscription);
    installNotification("granted");
    render(<PushNotifications />);
    const user = userEvent.setup({ delay: null });
    await user.click(
      await screen.findByRole("button", { name: "content.settings.push.disable" }),
    );
    await waitFor(() => expect(unsubscribePush).toHaveBeenCalledWith("https://push.example/abc"));
    expect(subscription.unsubscribe).toHaveBeenCalled();
  });
});
