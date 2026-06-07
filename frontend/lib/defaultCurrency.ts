// KFinans Frontend — kullanıcının varsayılan para birimi (v0.3.0).
//
// Backend `/user/me` → `default_currency` döner. Formlar (gelir/gider/planlı/
// periyodik/bütçe/kredi-kartı) yeni kayıtta bu değeri başlangıç olarak kullanır.
// Ağ çağrısını her formda tekrarlamamak için localStorage'a önbelleklenir;
// dashboard layout açılışta `/user/me`'den okuyup `cacheDefaultCurrency` ile yazar.
//
// `getDefaultCurrency()` senkron çalışır (form initial state için); değer yoksa
// güvenli "TRY" döner (geriye uyumlu — eski TL-bazlı davranış).

import type { CurrencyType } from "@/lib/api/types";
import { CURRENCIES } from "@/lib/api/types";

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

/** Görüntüleme (display) para birimi değiştiğinde tetiklenen olay adı. */
export const DISPLAY_CURRENCY_CHANGED = "kfinans-display-currency-changed";

/** `/user/me` sonucundan / ayarlardan gelen değeri önbelleğe yaz (geçersizse dokunma).
 *  Değer gerçekten değiştiyse `DISPLAY_CURRENCY_CHANGED` olayını yayar — tüm Money
 *  bileşenleri tam sayfa yenileme olmadan yeni para birimine geçer. */
export function cacheDefaultCurrency(currency: string | null | undefined): void {
  if (globalThis.window === undefined) return;
  if (!isCurrency(currency)) return;
  const prev = localStorage.getItem(KEY);
  localStorage.setItem(KEY, currency);
  if (prev !== currency) {
    globalThis.dispatchEvent(new CustomEvent(DISPLAY_CURRENCY_CHANGED));
  }
}
