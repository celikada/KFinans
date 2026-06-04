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

import { TLValue } from "@/app/_components/TLValue";
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
}


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
  href, icon, color, title, total, count, countLabel, loading, top, placeholder, footer, updating,
}: CardProps) {
  const router = useRouter();
  const c = COLOR_MAP[color];
  // total === 0 da geçerli yüklenmiş değer (örn. kredi kartı borç yoksa).
  // Sadece null = henüz fetch gelmedi.
  const hasTotal = total !== null;

  let body: React.ReactNode;
  if (hasTotal) {
    body = <TLValue tl={total} className={`text-base font-bold tabular-nums ${c.text}`} />;
  } else if ((count ?? 0) > 0) {
    body = <p className="text-xs text-gray-400">{count} {countLabel} · yükleniyor...</p>;
  } else if (loading) {
    body = <p className="text-xs text-gray-400">Yükleniyor...</p>;
  } else {
    body = <p className="text-xs text-gray-400">{placeholder}</p>;
  }

  return (
    <button
      onClick={() => router.push(href)}
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md ${c.border} transition-all group`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 ${c.bg} rounded-xl flex items-center justify-center ${c.text} group-hover:opacity-80 transition-opacity`}>
          {ICONS[icon]}
        </div>
        {updating && <UpdatingBadge />}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>

      {body}

      {top.length > 0 && (
        <ul className="mt-3 pt-3 border-t border-gray-50 space-y-1.5">
          {top.map((it) => (
            <li key={it.label} className="flex justify-between items-center text-xs">
              <span className="truncate text-gray-500 font-mono max-w-[60%]">{it.label}</span>
              <span className="font-semibold tabular-nums text-gray-700 ml-2 shrink-0">{fmtTL(it.value)} ₺</span>
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
  );
}


export function GoalCard({ href, pct, passive, updating }: { readonly href: string; readonly pct: number | null; readonly passive: number | null; readonly updating?: boolean }) {
  const router = useRouter();
  const { t } = useTranslation();
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
              {t("content.dashboard.goalPassiveIncome")} <span className="font-medium text-gray-600">{fmtTL(passive)} {t("content.dashboard.perMonthSuffix")}</span>
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
