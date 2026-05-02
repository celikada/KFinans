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
