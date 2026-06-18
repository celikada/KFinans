"use client";
/**
 * FE-003 (FAZ H): Dashboard kart bilesenleri.
 *
 * Genel Card (TEFAS, Kripto, Hisse vs.), GoalCard (finansal hedef + pasif
 * gelir progress bar), BudgetCard (asim/dahil rozeti). Hepsi page.tsx'ten
 * extract edildi.
 */
import * as React from "react";
import { useRouter } from "next/navigation";

import { Money, DisplayMoney, fmtCurrency, formatTlAs, useRates, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { COLOR_MAP, ICONS, type IconName } from "./icons";


export interface TopItem {
  readonly label: string;
  readonly value: number;
}

export interface CardProps {
  readonly href: string;
  readonly icon: IconName;
  readonly color: keyof typeof COLOR_MAP;
  readonly title: string;
  readonly total: number | null;
  readonly count?: number;
  readonly countLabel?: string;
  readonly loading?: boolean;
  readonly top: TopItem[];
  readonly placeholder: string;
  readonly footer?: React.ReactNode;
  // Cache hit sonrasi bu kartin verisi yeniden cekiliyor mu? true ise kart
  // ustunde "guncelleniyor" rozeti gosterilir (hangi kartin guncellendigini belirtir).
  readonly updating?: boolean;
  // Faz C: `total` ve `top` değerleri ZATEN görüntüleme para biriminde mi (backend
  // `*_display`, tarihsel kur)? true → DisplayMoney/fmtCurrency (BÖLME YOK).
  // false/undefined → Money/formatTlAs (TL → güncel kur; canlı yatırım kartları).
  readonly displayValue?: boolean;
  // Verilirse kartın sağ-üstüne "yenile" ikonu konur (yalnız bu kartı yeniden
  // çekmek için). Karta tıklayıp detaya gitmeyi engeller (stopPropagation).
  readonly onRefresh?: () => void;
  // Bu kartın bölümünde son güncellemede oluşan uyarı mesajları (ör. "X fiyatı
  // alınamadı"). Doluysa yenile ikonunun yanına ⚠ konur; üzerine gelince/tıklayınca
  // mesajlar gösterilir.
  readonly warnings?: readonly string[];
}


/** Kartın sağ-üstündeki tek-kart yenileme ikonu (dönen ok). */
function RefreshIcon({ spinning }: { readonly spinning?: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${spinning ? "animate-spin" : ""}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  );
}


/** Uyarı (⚠) üçgen ikonu. */
function WarningIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

/** Kartın sağ-üstünde, yenile ikonunun yanındaki uyarı (⚠) göstergesi + popover. */
function CardWarning({ warnings, title, offset }: { readonly warnings: readonly string[]; readonly title: string; readonly offset: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div ref={ref} className={`absolute top-3 ${offset ? "right-12" : "right-3"} z-20`}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        title={warnings.join("\n")}
        aria-label={`${title}: ${t("dashboard.cardWarning")}`}
        className="p-1.5 rounded-lg text-amber-500 hover:text-amber-600 hover:bg-amber-50 focus-visible:ring-2 focus-visible:ring-amber-400 transition-colors"
      >
        <WarningIcon />
      </button>
      {open && (
        <div
          role="tooltip"
          className="absolute top-9 right-0 w-64 max-w-[80vw] bg-white border border-amber-200 rounded-xl shadow-lg p-3 text-left"
        >
          <p className="text-xs font-semibold text-amber-700 mb-1">⚠ {t("dashboard.cardWarning")}</p>
          <ul className="space-y-1">
            {warnings.map((w) => (
              <li key={w} className="text-xs text-gray-600 leading-snug">{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


/** Kart ustunde "guncelleniyor" gostergesi (kucuk spinner + metin). */
export function UpdatingBadge() {
  const { t } = useTranslation();
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-normal text-blue-600 normal-case tracking-normal"
      title={t("dashboard.updating")}
    >
      <span className="inline-block w-2.5 h-2.5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
      {t("dashboard.updating")}
    </span>
  );
}


export function Card({
  href, icon, color, title, total, count, countLabel, loading, top, placeholder, footer, updating, displayValue, onRefresh, warnings,
}: CardProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const hasWarnings = (warnings?.length ?? 0) > 0;
  const c = COLOR_MAP[color];
  // Görüntüleme para birimi dönüşümü (top3 satırları için; total Money kullanır).
  const rates = useRates();
  const displayCurrency = useDisplayCurrency();
  // total === 0 da geçerli yüklenmiş değer (örn. kredi kartı borç yoksa).
  // Sadece null = henüz fetch gelmedi.
  const hasTotal = total !== null;

  let body: React.ReactNode;
  if (hasTotal) {
    // Faz C: finans kartları (displayValue) → DisplayMoney (zaten görüntüleme
    // biriminde, BÖLME YOK); yatırım kartları → Money (TL → güncel kur).
    body = displayValue
      ? <DisplayMoney value={total} currency={displayCurrency} className={`text-base font-bold tabular-nums ${c.text}`} />
      : <Money tl={total} className={`text-base font-bold tabular-nums ${c.text}`} />;
  } else if ((count ?? 0) > 0) {
    body = <p className="text-xs text-gray-400">{count} {countLabel} · yükleniyor...</p>;
  } else if (loading) {
    body = <p className="text-xs text-gray-400">Yükleniyor...</p>;
  } else {
    body = <p className="text-xs text-gray-400">{placeholder}</p>;
  }

  return (
    <div className="relative">
      {hasWarnings && warnings && <CardWarning warnings={warnings} title={title} offset={!!onRefresh} />}
      {onRefresh && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRefresh(); }}
          disabled={updating}
          title={t("dashboard.refreshCard")}
          aria-label={`${title} ${t("dashboard.refreshCard")}`}
          className="absolute top-3 right-3 z-10 p-1.5 rounded-lg text-gray-300 hover:text-blue-600 hover:bg-blue-50 focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-60 transition-colors"
        >
          <RefreshIcon spinning={updating} />
        </button>
      )}
      <button
        onClick={() => router.push(href)}
        className={`w-full bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md ${c.border} transition-all group`}
      >
        <div className="flex items-start justify-between mb-3">
          <div className={`w-9 h-9 ${c.bg} rounded-xl flex items-center justify-center ${c.text} group-hover:opacity-80 transition-opacity`}>
            {ICONS[icon]}
          </div>
          {updating && !onRefresh && <UpdatingBadge />}
        </div>
        <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>

        {body}

        {top.length > 0 && (
          <ul className="mt-3 pt-3 border-t border-gray-50 space-y-1.5">
            {top.map((it) => (
              <li key={it.label} className="flex justify-between items-center text-xs">
                <span className="truncate text-gray-500 font-mono max-w-[60%]">{it.label}</span>
                <span className="font-semibold tabular-nums text-gray-700 ml-2 shrink-0">
                  {displayValue ? fmtCurrency(it.value, displayCurrency) : formatTlAs(it.value, displayCurrency, rates)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {footer && (
          <div className="mt-3 pt-3 border-t border-gray-50 text-xs text-gray-500">
            {footer}
          </div>
        )}
      </button>
    </div>
  );
}


export function GoalCard({ href, pct, passive, updating }: { readonly href: string; readonly pct: number | null; readonly passive: number | null; readonly updating?: boolean }) {
  const router = useRouter();
  const { t } = useTranslation();
  const rates = useRates();
  const displayCurrency = useDisplayCurrency();
  const hasData = pct !== null;

  return (
    <button
      onClick={() => router.push(href)}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md hover:border-violet-200 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 bg-violet-50 rounded-xl flex items-center justify-center text-violet-600 group-hover:bg-violet-100 transition-colors">
          {ICONS.goal}
        </div>
        {updating ? (
          <UpdatingBadge />
        ) : (
          pct !== null && (
            <span className="text-xs font-semibold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">
              %{pct.toFixed(0)}
            </span>
          )
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{t("content.dashboard.goalTitle")}</h3>

      {hasData ? (
        <>
          <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden mb-2">
            <div
              className="h-full bg-violet-500 rounded-full transition-all"
              style={{ width: `${Math.min(pct ?? 0, 100)}%` }}
            />
          </div>
          {passive !== null && (
            <p className="text-xs text-gray-400">
              {t("content.dashboard.goalPassiveIncome")} <span className="font-medium text-gray-600">{formatTlAs(passive, displayCurrency, rates)}{t("content.dashboard.perMonthSuffix")}</span>
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-400">{t("content.dashboard.goalEmptyHint")}</p>
      )}
    </button>
  );
}


export function BudgetCard({ href, overCount, updating }: { readonly href: string; readonly overCount: number | null; readonly updating?: boolean }) {
  const router = useRouter();
  const { t } = useTranslation();
  let status: React.ReactNode;
  if (overCount === null) {
    status = <p className="text-xs text-gray-400">{t("content.dashboard.budgetEmptyHint")}</p>;
  } else if (overCount === 0) {
    status = <p className="text-xs text-emerald-600">{t("content.dashboard.budgetAllWithin")}</p>;
  } else {
    status = <p className="text-xs text-red-500">{t("content.dashboard.budgetOverCount").replace("{count}", String(overCount))}</p>;
  }
  return (
    <button
      onClick={() => router.push(href)}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md hover:border-amber-200 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600 group-hover:bg-amber-100 transition-colors">
          {ICONS.budget}
        </div>
        {updating && <UpdatingBadge />}
        {!updating && overCount !== null && overCount > 0 && (
          <span className="text-xs font-semibold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">
            {t("content.dashboard.budgetOverBadge").replace("{count}", String(overCount))}
          </span>
        )}
        {!updating && overCount !== null && overCount === 0 && (
          <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
            {t("content.dashboard.budgetWithinBadge")}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{t("content.dashboard.budgetTitle")}</h3>
      {status}
    </button>
  );
}
