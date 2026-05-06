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
  // Portföy grubu
  { id: "bes",          label: "BES",                       group: "portfolio" },
  { id: "tefas",        label: "TEFAS Fonları",             group: "portfolio" },
  { id: "stocks",       label: "Hisse Senedi",              group: "portfolio" },
  { id: "wallets",      label: "Blockchain Cüzdanlar",      group: "portfolio" },
  { id: "crypto",       label: "Kripto",                    group: "portfolio" },
  { id: "manualCrypto", label: "Manuel Kripto (API'siz)",   group: "portfolio" },
  { id: "commodities",  label: "Altın & Gümüş",             group: "portfolio" },
  { id: "cash",         label: "Nakit / Banka",             group: "portfolio" },
  // Finans grubu
  { id: "creditCards",  label: "Kredi Kartları",             group: "finance" },
  { id: "income",       label: "Gelirler",                  group: "finance" },
  { id: "expenses",     label: "Harcamalar",                group: "finance" },
  { id: "planned",      label: "Planlı Harcamalar",         group: "finance" },
  { id: "budget",       label: "Bütçe Takibi",              group: "finance" },
  { id: "goal",         label: "Finansal Hedef",            group: "finance" },
] as const;

export type DashboardCardId = typeof DASHBOARD_CARDS[number]["id"];
export type DashboardGroup = "portfolio" | "finance";

export const DASHBOARD_GROUPS: { id: DashboardGroup; label: string }[] = [
  { id: "portfolio", label: "Portföy" },
  { id: "finance",   label: "Finans" },
];

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
