/**
 * FE-003 (FAZ H): Dashboard kart icon'lari ve renk paleti.
 *
 * Onceden dashboard/page.tsx'in icinde inline tanimlydi (913+ satir);
 * 150 satir kuralini ihlal ediyordu. Bu modul kart bilesenlerinden
 * kullanilan SVG'leri ve color map'i izole tutar.
 */
import * as React from "react";

export const COLOR_MAP: Record<string, { bg: string; border: string; text: string; accent: string }> = {
  blue:    { bg: "bg-blue-50",    border: "hover:border-blue-200",    text: "text-blue-600",    accent: "bg-blue-500" },
  orange:  { bg: "bg-orange-50",  border: "hover:border-orange-200",  text: "text-orange-500",  accent: "bg-orange-500" },
  indigo:  { bg: "bg-indigo-50",  border: "hover:border-indigo-200",  text: "text-indigo-600",  accent: "bg-indigo-500" },
  purple:  { bg: "bg-purple-50",  border: "hover:border-purple-200",  text: "text-purple-600",  accent: "bg-purple-500" },
  green:   { bg: "bg-green-50",   border: "hover:border-green-200",   text: "text-green-600",   accent: "bg-green-500" },
  red:     { bg: "bg-red-50",     border: "hover:border-red-200",     text: "text-red-500",     accent: "bg-red-500" },
  violet:  { bg: "bg-violet-50",  border: "hover:border-violet-200",  text: "text-violet-600",  accent: "bg-violet-500" },
  emerald: { bg: "bg-emerald-50", border: "hover:border-emerald-200", text: "text-emerald-600", accent: "bg-emerald-500" },
  amber:   { bg: "bg-amber-50",   border: "hover:border-amber-200",   text: "text-amber-600",   accent: "bg-amber-500" },
};

export type IconName =
  | "tefas" | "crypto" | "stocks" | "wallets" | "bes"
  | "expenses" | "planned" | "income" | "goal"
  | "commodities" | "budget" | "cash" | "creditCard";

export const ICONS: Record<IconName, React.ReactNode> = {
  tefas: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2v10h10" />
      <path d="M12 12L4.93 19.07" />
    </svg>
  ),
  crypto: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M11.767 19.089c4.924.868 6.14-6.025 1.216-6.894m-1.216 6.894L5.86 18.047m5.908 1.042-.347 1.97m1.563-8.864c4.924.869 6.14-6.025 1.215-6.893m-1.215 6.893-3.94-.694m5.155-6.2L8.29 4.26m5.908 1.042.348-1.97M7.48 20.364l3.126-17.727" />
    </svg>
  ),
  stocks: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <line x1="6"  y1="3"  x2="6"  y2="21" />
      <rect x="4"  y="7"  width="4" height="7" fill="currentColor" stroke="none" />
      <line x1="12" y1="5"  x2="12" y2="19" />
      <rect x="10" y="13" width="4" height="4" fill="currentColor" stroke="none" />
      <line x1="18" y1="2"  x2="18" y2="22" />
      <rect x="16" y="6"  width="4" height="9" fill="currentColor" stroke="none" />
    </svg>
  ),
  wallets: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  bes: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  ),
  expenses: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="1" y="4" width="22" height="16" rx="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  ),
  planned: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8"  y1="2" x2="8"  y2="6" />
      <line x1="3"  y1="10" x2="21" y2="10" />
    </svg>
  ),
  income: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  goal: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  ),
  commodities: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <ellipse cx="12" cy="5"  rx="8" ry="2.5" />
      <path d="M4 5v3.5c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5V5" />
      <path d="M4 11v3.5c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5V11" />
      <path d="M4 17v2c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-2" />
    </svg>
  ),
  budget: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </svg>
  ),
  cash: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <circle cx="12" cy="12" r="2" />
      <path d="M6 12h.01M18 12h.01" />
    </svg>
  ),
  creditCard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <line x1="2" y1="10" x2="22" y2="10" />
      <rect x="5" y="13" width="4" height="3" rx="0.5" fill="currentColor" stroke="none" />
    </svg>
  ),
};
