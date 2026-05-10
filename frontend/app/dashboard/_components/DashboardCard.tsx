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
import { COLOR_MAP, ICONS, type IconName } from "./icons";


export interface TopItem {
  label: string;
  value: number;
}

export interface CardProps {
  href: string;
  icon: IconName;
  color: keyof typeof COLOR_MAP;
  title: string;
  total: number | null;
  count?: number;
  countLabel?: string;
  loading?: boolean;
  top: TopItem[];
  placeholder: string;
  footer?: React.ReactNode;
}


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}


export function Card({
  href, icon, color, title, total, count, countLabel, loading, top, placeholder, footer,
}: CardProps) {
  const router = useRouter();
  const c = COLOR_MAP[color];
  // total === 0 da geçerli yüklenmiş değer (örn. kredi kartı borç yoksa).
  // Sadece null = henüz fetch gelmedi.
  const hasTotal = total !== null;

  return (
    <button
      onClick={() => router.push(href)}
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md ${c.border} transition-all group`}
    >
      <div className={`w-9 h-9 ${c.bg} rounded-xl flex items-center justify-center ${c.text} mb-3 group-hover:opacity-80 transition-opacity`}>
        {ICONS[icon]}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>

      {hasTotal ? (
        <TLValue tl={total} className={`text-base font-bold tabular-nums ${c.text}`} />
      ) : (count ?? 0) > 0 ? (
        <p className="text-xs text-gray-400">{count} {countLabel} · yükleniyor...</p>
      ) : loading ? (
        <p className="text-xs text-gray-400">Yükleniyor...</p>
      ) : (
        <p className="text-xs text-gray-400">{placeholder}</p>
      )}

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


export function GoalCard({ href, pct, passive }: { href: string; pct: number | null; passive: number | null }) {
  const router = useRouter();
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
        {hasData && (
          <span className="text-xs font-semibold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">
            %{pct!.toFixed(0)}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">Finansal Hedef</h3>

      {hasData ? (
        <>
          <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden mb-2">
            <div
              className="h-full bg-violet-500 rounded-full transition-all"
              style={{ width: `${Math.min(pct!, 100)}%` }}
            />
          </div>
          {passive !== null && (
            <p className="text-xs text-gray-400">
              Pasif gelir: <span className="font-medium text-gray-600">{fmtTL(passive)} ₺/ay</span>
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-400">Aylık ihtiyacını gir, hedefini hesapla</p>
      )}
    </button>
  );
}


export function BudgetCard({ href, overCount }: { href: string; overCount: number | null }) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push(href)}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md hover:border-amber-200 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600 group-hover:bg-amber-100 transition-colors">
          {ICONS.budget}
        </div>
        {overCount !== null && overCount > 0 && (
          <span className="text-xs font-semibold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">
            {overCount} aşım
          </span>
        )}
        {overCount !== null && overCount === 0 && (
          <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
            Dahilinde
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">Bütçe Takibi</h3>
      {overCount === null
        ? <p className="text-xs text-gray-400">Kategori bazında limit belirle</p>
        : overCount === 0
          ? <p className="text-xs text-emerald-600">Tüm kategoriler bütçe dahilinde</p>
          : <p className="text-xs text-red-500">{overCount} kategori bütçeyi aştı</p>
      }
    </button>
  );
}
