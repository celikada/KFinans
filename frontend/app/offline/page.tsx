"use client";

/**
 * Offline fallback page (PWA).
 *
 * Precached by the service worker and served when a document navigation fails
 * because the device is offline. Intentionally self-contained: it renders even
 * without network and shows a "retry" affordance. No financial data is shown —
 * that always requires a live network request.
 */

import { KFinansLogo } from "@/app/_components/Logos";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function OfflinePage() {
  const { t } = useTranslation();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <KFinansLogo size="xl" />

      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-gray-800">
          {t("pages.offline.title")}
        </h1>
        <p className="max-w-sm text-sm text-gray-500">
          {t("pages.offline.description")}
        </p>
      </div>

      <button
        type="button"
        onClick={() => globalThis.location.reload()}
        className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-800 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
      >
        {t("pages.offline.retry")}
      </button>
    </main>
  );
}
