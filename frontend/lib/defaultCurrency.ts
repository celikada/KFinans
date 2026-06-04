// KFinans Frontend — kullanıcının varsayılan para birimi (v0.3.0).
//
// Backend `/user/me` → `default_currency` döner. Formlar (gelir/gider/planlı/
// periyodik/bütçe/kredi-kartı) yeni kayıtta bu değeri başlangıç olarak kullanır.
// Ağ çağrısını her formda tekrarlamamak için localStorage'a önbelleklenir;
// dashboard layout açılışta `/user/me`'den okuyup `cacheDefaultCurrency` ile yazar.
//
// `getDefaultCurrency()` senkron çalışır (form initial state için); değer yoksa
// güvenli "TRY" döner (geriye uyumlu — eski TL-bazlı davranış).

import type { CurrencyType } from "@/lib/api";
import { CURRENCIES } from "@/lib/api";

const KEY = "kfinans_default_currency";

function isCurrency(v: unknown): v is CurrencyType {
  return typeof v === "string" && (CURRENCIES as string[]).includes(v);
}

/** localStorage'daki varsayılan para birimi; yoksa "TRY". SSR güvenli. */
export function getDefaultCurrency(): CurrencyType {
  if (globalThis.window === undefined) return "TRY";
  const v = localStorage.getItem(KEY);
  return isCurrency(v) ? v : "TRY";
}

/** `/user/me` sonucundan gelen değeri önbelleğe yaz (geçersizse dokunma). */
export function cacheDefaultCurrency(currency: string | null | undefined): void {
  if (globalThis.window === undefined) return;
  if (isCurrency(currency)) {
    localStorage.setItem(KEY, currency);
  }
}
