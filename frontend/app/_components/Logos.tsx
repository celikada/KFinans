"use client";

type LogoSize = "sm" | "md" | "lg" | "xl";

const ICON_SIZE: Record<LogoSize, number> = { sm: 24, md: 32, lg: 40, xl: 64 };
const TEXT_CLS: Record<LogoSize, string> = {
  sm: "text-base",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-4xl",
};

export function KFinansLogo({ size = "md" }: { readonly size?: LogoSize }) {
  const iconSize = ICON_SIZE[size];
  const textCls = TEXT_CLS[size];

  return (
    <div className="flex items-center gap-2.5 select-none">
      <svg width={iconSize} height={iconSize} viewBox="0 0 32 32" fill="none" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#1D4ED8" />
        {/* K stem */}
        <line x1="9" y1="8" x2="9" y2="24" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        {/* K upper arm */}
        <line x1="9" y1="16" x2="18" y2="8" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        {/* K lower arm */}
        <line x1="9" y1="16" x2="18" y2="24" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        {/* Trend line accent */}
        <polyline
          points="16,22 19,16 22,19 25,12"
          stroke="#93C5FD"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>

      <span className={`${textCls} font-bold leading-none tracking-tight`}>
        <span className="text-blue-700">K</span>
        <span className="text-gray-800">Finans</span>
      </span>
    </div>
  );
}

export function MayotekLogo() {
  return (
    <div className="flex items-center gap-1.5 select-none">
      {/* m bracket icon */}
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
        <rect width="18" height="18" rx="4" fill="#F1F5F9" />
        <path d="M4 13 C4 13 4 6 7 6 C9 6 9 10 9 10 C9 10 9 6 11 6 C14 6 14 13 14 13"
          stroke="#334155" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
      <span className="text-sm font-semibold tracking-tight leading-none">
        <span className="text-slate-700">mayo</span>
        <span className="text-blue-600">tek</span>
      </span>
    </div>
  );
}
