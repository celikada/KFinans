"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { arrayBufferToBase64Url, urlBase64ToUint8Array } from "@/lib/push-utils";

const CARD_CLS = "bg-white rounded-2xl border border-gray-100 shadow-sm p-6";

// Push is only usable when the browser exposes SW + PushManager + Notification.
function pushSupported(): boolean {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in globalThis &&
    "Notification" in globalThis
  );
}

// iOS Safari requires the PWA to be installed (standalone) before push works.
function isUnsupportedIos(): boolean {
  const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return isIos && !standalone;
}

export function PushNotifications() {
  const { t } = useTranslation();
  const [supported, setSupported] = useState(false);
  const [iosBlocked, setIosBlocked] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    if (!pushSupported()) {
      setSupported(false);
      return;
    }
    setSupported(true);
    setIosBlocked(isUnsupportedIos());
    // Reflect the existing subscription state on mount.
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setSubscribed(sub !== null))
      .catch(() => setSubscribed(false));
  }, []);

  async function enable() {
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const permission = await globalThis.Notification.requestPermission();
      if (permission !== "granted") {
        setError(t("content.settings.push.permissionDenied"));
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const { public_key } = await api.getVapidPublicKey();
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });
      await api.subscribePush({
        endpoint: sub.endpoint,
        keys: {
          p256dh: arrayBufferToBase64Url(sub.getKey("p256dh")),
          auth: arrayBufferToBase64Url(sub.getKey("auth")),
        },
        user_agent: navigator.userAgent,
      });
      setSubscribed(true);
    } catch (e) {
      console.error("Push enable failed:", e);
      // AbortError "Registration failed - push service error": tarayıcının push
      // servisi devre dışı (en sık Brave'de Google push kapalıyken). Kullanıcıya
      // genel "başarısız" yerine eyleme dönük ipucu ver.
      const name = e instanceof Error ? e.name : "";
      if (name === "AbortError") {
        setError(t("content.settings.push.pushServiceError"));
      } else if (name === "NotAllowedError") {
        setError(t("content.settings.push.permissionDenied"));
      } else {
        setError(t("content.settings.push.failed"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await api.unsubscribePush(sub.endpoint);
        await sub.unsubscribe();
      }
      setSubscribed(false);
    } catch (e) {
      console.error("Push disable failed:", e);
      setError(t("content.settings.push.failed"));
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const { sent } = await api.sendTestPush();
      // sent=0: abonelik sunucuda yok / gönderilemedi → kullanıcı yanıltılmasın.
      setInfo(sent > 0 ? t("content.settings.push.testSent") : t("content.settings.push.testNoSubs"));
    } catch (e) {
      console.error("Push test failed:", e);
      setError(t("content.settings.push.failed"));
    } finally {
      setBusy(false);
    }
  }

  function handleToggle() {
    if (subscribed) {
      void disable();
    } else {
      void enable();
    }
  }

  if (!supported) {
    return (
      <section className={CARD_CLS}>
        <h2 className="text-base font-semibold text-gray-900 mb-1">{t("content.settings.push.title")}</h2>
        <p className="text-xs text-gray-500">{t("content.settings.push.unsupported")}</p>
      </section>
    );
  }

  return (
    <section className={CARD_CLS}>
      <h2 className="text-base font-semibold text-gray-900 mb-1">{t("content.settings.push.title")}</h2>
      <p className="text-xs text-gray-500 mb-4">{t("content.settings.push.description")}</p>

      {iosBlocked && (
        <p className="text-xs text-amber-700 bg-amber-50 px-3 py-2 rounded-lg mb-4">
          {t("content.settings.push.iosHint")}
        </p>
      )}

      <div className="flex items-center justify-between py-2">
        <div>
          <p className="text-sm text-gray-700">{t("content.settings.push.toggle")}</p>
          <p className="text-xs text-gray-400 mt-0.5">{t("content.settings.push.toggleHint")}</p>
        </div>
        <button
          type="button"
          onClick={handleToggle}
          disabled={busy}
          className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 disabled:opacity-50 ${subscribed ? "bg-blue-600" : "bg-gray-200"}`}
          aria-pressed={subscribed}
          aria-label={subscribed ? t("content.settings.push.disable") : t("content.settings.push.enable")}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${subscribed ? "translate-x-5" : ""}`}
          />
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mt-3" role="alert">
          {error}
        </p>
      )}
      {info && (
        <p className="text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg mt-3">{info}</p>
      )}

      {subscribed && (
        <button
          type="button"
          onClick={sendTest}
          disabled={busy}
          className="mt-4 w-full py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-50"
        >
          {t("content.settings.push.sendTest")}
        </button>
      )}
    </section>
  );
}
