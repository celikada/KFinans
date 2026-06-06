"use client";
/**
 * Görüntüleme (display) para birimi bileşeni (v0.3.0).
 *
 * Backend tüm TOPLAMLARI TL (`*_tl`) döner. Kullanıcı Ayarlar'da bir görüntüleme
 * para birimi seçer (default_currency); kart/grafik/dashboard TOPLAMLARI bu
 * bileşenle seçili para birimine çevrilip gösterilir. Satır kalemleri (tek tek
 * gelir/gider) kendi giriş para biriminde gösterilir — onlar Money kullanmaz.
 *
 * Dönüşüm: `/portfolio/rates` "1 birim = X TL" verir → `tl / rate[currency]`.
 * Kur henüz yüklenmediyse (veya kur yoksa) ham TL gösterilir (güvenli fallback).
 */
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { fmtTL } from "@/lib/format";
import { getDefaultCurrency, DISPLAY_CURRENCY_CHANGED } from "@/lib/defaultCurrency";
import { getShowUsd, SHOW_USD_CHANGED_EVENT } from "@/app/_components/TLValue";
import type { CurrencyType } from "@/lib/api";

const RATES_KEY = "kfinans_rates_cache";
const RATES_TTL_MS = 5 * 60 * 1000;

export const CURRENCY_SYMBOLS: Record<string, string> = {
  TRY: "₺",
  USD: "$",
  EUR: "€",
  GBP: "£",
  CHF: "₣",
  JPY: "¥",
};

type Rates = Record<string, number>;

interface CachedRates {
  ts: number;
  rates: Rates;
}

function parseRates(raw: Record<string, string>): Rates {
  const out: Rates = {};
  for (const [k, v] of Object.entries(raw)) {
    const n = Number.parseFloat(v);
    if (Number.isFinite(n) && n > 0) out[k] = n;
  }
  return out;
}

/** Tüm para birimi kurları (1 birim = X TL); 5 dk localStorage cache. */
export function useRates(): Rates | null {
  const [rates, setRates] = useState<Rates | null>(() => {
    if (globalThis.window === undefined) return null;
    try {
      const raw = localStorage.getItem(RATES_KEY);
      if (!raw) return null;
      const cached = JSON.parse(raw) as CachedRates;
      if (Date.now() - cached.ts < RATES_TTL_MS) return cached.rates;
    } catch {
      /* swallow */
    }
    return null;
  });

  useEffect(() => {
    if (rates !== null) return;
    let cancelled = false;
    api
      .getRates()
      .then((r) => {
        if (cancelled) return;
        const parsed = parseRates(r.rates);
        setRates(parsed);
        localStorage.setItem(RATES_KEY, JSON.stringify({ ts: Date.now(), rates: parsed }));
      })
      .catch(() => {
        /* sessizce yut — kur yoksa TL fallback gösterilir */
      });
    return () => {
      cancelled = true;
    };
  }, [rates]);

  return rates;
}

/** "USD karşılığı göster" tercihi; Ayarlar'dan değişince reaktif güncellenir. */
export function useShowUsd(): boolean {
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(getShowUsd());
    const handler = () => setShow(getShowUsd());
    globalThis.addEventListener(SHOW_USD_CHANGED_EVENT, handler);
    return () => globalThis.removeEventListener(SHOW_USD_CHANGED_EVENT, handler);
  }, []);
  return show;
}

/** Seçili görüntüleme para birimi; Ayarlar'dan değişince reaktif güncellenir. */
export function useDisplayCurrency(): CurrencyType {
  const [currency, setCurrency] = useState<CurrencyType>("TRY");
  useEffect(() => {
    setCurrency(getDefaultCurrency());
    const handler = () => setCurrency(getDefaultCurrency());
    globalThis.addEventListener(DISPLAY_CURRENCY_CHANGED, handler);
    return () => globalThis.removeEventListener(DISPLAY_CURRENCY_CHANGED, handler);
  }, []);
  return currency;
}

/** TL tutarını seçili para birimine çevirip biçimlendirir (saf yardımcı). */
export function formatTlAs(tl: number, currency: CurrencyType, rates: Rates | null): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  if (currency === "TRY") return `${fmtTL(tl)} ${symbol}`;
  const rate = rates?.[currency];
  if (!rate || rate <= 0) {
    // Kur yok → güvenli TL fallback (yanlış değer gösterme).
    return `${fmtTL(tl)} ₺`;
  }
  return `${fmtTL(tl / rate)} ${symbol}`;
}

interface Props {
  /** TL cinsinden değer (number veya parsable string). */
  readonly tl: number | string | null | undefined;
  readonly className?: string;
  /** USD karşılığı alt-satırı için ek class (varsayılan: küçük gri blok). */
  readonly usdClassName?: string;
  /** "USD karşılığı göster" alt-satırını bu örnekte gösterme (ör. dar footer'lar). */
  readonly hideUsd?: boolean;
}

/**
 * Bir TL TOPLAMINI seçili görüntüleme para birimine çevirip gösterir.
 * (Tek tek satır kalemleri için DEĞİL — onlar kendi para biriminde gösterilir.)
 *
 * "USD karşılığı göster" (Ayarlar) açıksa ve görüntüleme birimi USD değilse,
 * değerin ALTINA `≈ $X` USD karşılığını ekler (güncel USD/TRY kuruyla).
 */
export function Money({ tl, className, usdClassName, hideUsd }: Props) {
  const rates = useRates();
  const currency = useDisplayCurrency();
  const showUsd = useShowUsd();
  const n = typeof tl === "string" ? Number.parseFloat(tl) : (tl ?? 0);
  const value = Number.isFinite(n) ? n : 0;

  const usdRate = rates?.USD;
  const showUsdLine = showUsd && !hideUsd && currency !== "USD" && !!usdRate && usdRate > 0;

  return (
    <span className={className}>
      {formatTlAs(value, currency, rates)}
      {showUsdLine && (
        <span className={usdClassName ?? "block text-xs text-gray-400 font-normal mt-0.5 tabular-nums"}>
          ≈ ${(value / usdRate).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
        </span>
      )}
    </span>
  );
}
