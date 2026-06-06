"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtTL } from "@/lib/format";

const STORAGE_KEY = "kfinans_show_usd";
const RATE_KEY = "kfinans_usd_rate_cache";
const RATE_TTL_MS = 5 * 60 * 1000;

/** "USD karşılığı göster" değişince yayınlanan olay (aynı sekmede reaktif güncelleme). */
export const SHOW_USD_CHANGED_EVENT = "kfinans-show-usd-changed";

export function getShowUsd(): boolean {
  if (globalThis.window === undefined) return false;
  return localStorage.getItem(STORAGE_KEY) === "true";
}

export function setShowUsd(v: boolean) {
  localStorage.setItem(STORAGE_KEY, v ? "true" : "false");
  // Tüm bileşenlere haber ver — storage event aynı sekmede tetiklenmez
  globalThis.dispatchEvent(new CustomEvent(SHOW_USD_CHANGED_EVENT));
}

interface CachedRate {
  ts: number;
  rate: number;
}

export function useUsdRate(): number | null {
  const [rate, setRate] = useState<number | null>(() => {
    if (globalThis.window === undefined) return null;
    try {
      const raw = localStorage.getItem(RATE_KEY);
      if (!raw) return null;
      const cached = JSON.parse(raw) as CachedRate;
      if (Date.now() - cached.ts < RATE_TTL_MS) return cached.rate;
    } catch { /* swallow */ }
    return null;
  });

  useEffect(() => {
    if (rate !== null) return;
    let cancelled = false;
    api.getUsdRate()
      .then((r) => {
        if (cancelled) return;
        const n = Number.parseFloat(r.usd_try);
        setRate(n);
        localStorage.setItem(RATE_KEY, JSON.stringify({ ts: Date.now(), rate: n }));
      })
      .catch(() => { /* sessizce yut — fallback yok, USD gösterilmez */ });
    return () => { cancelled = true; };
  }, [rate]);

  return rate;
}

interface Props {
  /** TRY cinsinden değer (number veya parsable string). */
  readonly tl: number | string | null | undefined;
  /** Tipografi sınıfları — opsiyonel override. */
  readonly className?: string;
  /** USD karşılığı için ek class (varsayılan: küçük gri). */
  readonly usdClassName?: string;
}

/**
 * TL değerini `1.234,56 ₺` formatında gösterir; ayar açıksa altında
 * `≈ $369.30` USD karşılığını da gösterir.
 *
 * Kullanıcı `Ayarlar > Genel` üzerinden toggle ile USD gösterimini açar.
 */
export function TLValue({ tl, className, usdClassName }: Props) {
  const rate = useUsdRate();
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(getShowUsd());
    const handler = () => setShow(getShowUsd());
    globalThis.addEventListener(SHOW_USD_CHANGED_EVENT, handler);
    return () => globalThis.removeEventListener(SHOW_USD_CHANGED_EVENT, handler);
  }, []);

  if (tl === null || tl === undefined || tl === "") {
    return <span className={className}>—</span>;
  }
  const n = typeof tl === "string" ? Number.parseFloat(tl) : tl;
  if (Number.isNaN(n)) return <span className={className}>—</span>;

  return (
    <span className={className}>
      {fmtTL(n)} ₺
      {show && rate !== null && rate > 0 && (
        <span className={usdClassName ?? "block text-xs text-gray-400 font-normal mt-0.5 tabular-nums"}>
          ≈ ${(n / rate).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      )}
    </span>
  );
}
