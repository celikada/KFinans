"use client";
import { CryptoPositionDTO } from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";
import { PROVIDER_LABELS } from "./constants";

interface Props {
  positions: CryptoPositionDTO[];
  hidden: Set<string>;
  onToggle: (provider: string) => void;
}

export function ProviderSummaryCards({ positions, hidden, onToggle }: Props) {
  const byProvider = Object.entries(
    positions.reduce<Record<string, number>>((acc, p) => {
      acc[p.provider] = (acc[p.provider] ?? 0) + parseFloat(p.total_value_tl);
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  if (byProvider.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex gap-3 flex-wrap">
      {byProvider.map(([prov, total]) => {
        const isHidden = hidden.has(prov);
        return (
          <button
            key={prov}
            onClick={() => onToggle(prov)}
            className={`flex-1 min-w-[140px] rounded-xl px-4 py-3 text-left transition-all border ${
              isHidden
                ? "bg-gray-50 border-gray-100 opacity-40"
                : "bg-gray-50 border-gray-200 hover:border-blue-200"
            }`}
          >
            <p className="text-xs text-gray-400 mb-1 flex items-center gap-1">
              {PROVIDER_LABELS[prov] ?? prov}
              <span className="ml-auto text-gray-300">{isHidden ? "gizli" : "✓"}</span>
            </p>
            <TLValue
              tl={total}
              className={`text-sm font-bold ${isHidden ? "text-gray-400" : "text-gray-900"}`}
              usdClassName="block text-[10px] text-gray-400 font-normal mt-0.5 tabular-nums"
            />
          </button>
        );
      })}
    </div>
  );
}
