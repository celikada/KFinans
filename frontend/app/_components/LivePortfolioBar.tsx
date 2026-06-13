"use client";

/**
 * Canlı portföy üst-bar bileşeni: "Son güncelleme: X dk önce" göstergesi +
 * "Yenile" butonu (spinner). Dashboard ve 6 portföy detay sayfasında ortak
 * kullanılır (fix/dashboard-live-cache-resilience).
 *
 * `refreshedAt` ISO datetime (cache yazım anı); `stale` true ise hafif uyarı
 * rengi. `refreshing` sürerken buton disabled + spinner.
 */

import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly refreshedAt: string | null;
  readonly stale: boolean;
  readonly refreshing: boolean;
  readonly onRefresh: () => void;
  /** Buton + etiketi sağa hizalamak yerine satır içinde kullan. */
  readonly className?: string;
}

/** ISO datetime → "az önce" / "3 dk önce" / "2 sa önce" / "1 gün önce". */
function relativeTime(iso: string | null, t: (k: string) => string): string {
  if (!iso) return t("dashboard.live.never");
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return t("dashboard.live.never");
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return t("dashboard.live.justNow");
  if (mins < 60) return t("dashboard.live.minutesAgo").replace("{n}", String(mins));
  const hours = Math.floor(mins / 60);
  if (hours < 24) return t("dashboard.live.hoursAgo").replace("{n}", String(hours));
  const days = Math.floor(hours / 24);
  return t("dashboard.live.daysAgo").replace("{n}", String(days));
}

export function LivePortfolioBar({ refreshedAt, stale, refreshing, onRefresh, className }: Props) {
  const { t } = useTranslation();
  return (
    <div className={`flex items-center gap-3 ${className ?? ""}`}>
      <span
        className={`text-xs ${stale ? "text-amber-600" : "text-gray-400"}`}
        title={refreshedAt ?? undefined}
      >
        {t("dashboard.live.lastUpdated")}: {relativeTime(refreshedAt, t)}
        {stale && ` · ${t("dashboard.live.stale")}`}
      </span>
      <button
        type="button"
        onClick={onRefresh}
        disabled={refreshing}
        className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1.5"
      >
        {refreshing && (
          <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
        )}
        {refreshing ? t("dashboard.live.refreshing") : t("dashboard.live.refresh")}
      </button>
    </div>
  );
}
