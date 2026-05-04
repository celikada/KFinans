/**
 * Ortak formatlamalar — TL, sayi, tarih.
 * crypto/stocks/wallets/bes/dashboard/history sayfalarinin tamami burayi kullanir.
 */

export function fmtTL(val: string | number, decimals = 2) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  });
}

export function fmtNum(val: string | number, decimals = 6) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  });
}

export function fmtDate(iso: string, opts: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" }) {
  return new Date(iso).toLocaleDateString("tr-TR", opts);
}

export function shortAddr(addr: string, headLen = 8, tailLen = 6) {
  if (addr.length <= headLen + tailLen + 2) return addr;
  return `${addr.slice(0, headLen)}…${addr.slice(-tailLen)}`;
}

export const INPUT_CLS =
  "px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400";

export const TOOLBAR_BTN_CLS =
  "text-sm text-gray-600 hover:text-gray-900 font-medium border border-gray-200 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50";

export const DASHBOARD_CARDS = [
  { id: "tefas",       label: "TEFAS Fonları" },
  { id: "crypto",      label: "Kripto" },
  { id: "stocks",      label: "Hisse Senedi" },
  { id: "wallets",     label: "Blockchain Cüzdanlar" },
  { id: "bes",         label: "BES" },
  { id: "expenses",    label: "Harcamalar" },
  { id: "planned",     label: "Planlı Ödemeler" },
  { id: "income",      label: "Gelirler" },
  { id: "goal",        label: "Finansal Hedef" },
  { id: "commodities", label: "Altın & Gümüş" },
  { id: "budget",      label: "Bütçe Takibi" },
  { id: "cash",        label: "Nakit / Banka" },
] as const;

export type DashboardCardId = typeof DASHBOARD_CARDS[number]["id"];

export function getHiddenCards(): DashboardCardId[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem("kfinans_hidden_cards") ?? "[]");
  } catch {
    return [];
  }
}

export function saveHiddenCards(ids: DashboardCardId[]) {
  localStorage.setItem("kfinans_hidden_cards", JSON.stringify(ids));
}
