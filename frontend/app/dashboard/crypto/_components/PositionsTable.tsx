"use client";
import { useState } from "react";
import { CryptoPositionDTO } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { PROVIDER_LABELS } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

type SortCol = "value" | "name" | "amount";
type SortDir = "desc" | "asc";

interface Props {
  positions: CryptoPositionDTO[];
}

export function PositionsTable({ positions }: Props) {
  const { t } = useTranslation();
  const [sortBy, setSortBy] = useState<SortCol>("value");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function toggleSort(col: SortCol) {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir(col === "name" ? "asc" : "desc");
    }
  }

  const totalTL = positions.reduce((s, p) => s + Number.parseFloat(p.total_value_tl), 0);

  const sorted = [...positions].sort((a, b) => {
    const dir = sortDir === "desc" ? -1 : 1;
    if (sortBy === "name") return dir * a.symbol.localeCompare(b.symbol);
    if (sortBy === "amount") {
      const qa = Number.parseFloat(a.liquid_quantity) + Number.parseFloat(a.staked_quantity);
      const qb = Number.parseFloat(b.liquid_quantity) + Number.parseFloat(b.staked_quantity);
      return dir * (qa - qb);
    }
    return dir * (Number.parseFloat(a.total_value_tl) - Number.parseFloat(b.total_value_tl));
  });

  const arrow = sortDir === "desc" ? " ↓" : " ↑";
  const headers: Array<{ label: string; align: string; col: SortCol | null }> = [
    { label: t("content.crypto.colCoin"), align: "text-left", col: "name" },
    { label: t("content.crypto.colAmount"), align: "text-right", col: "amount" },
    { label: t("content.crypto.colPriceUsdt"), align: "text-right", col: null },
    { label: t("content.crypto.colTotalTl"), align: "text-right", col: "value" },
  ];

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">{t("content.crypto.positionsTitle")}</h2>
        <TLValue tl={totalTL} className="text-lg font-bold text-gray-900" usdClassName="block text-xs text-gray-400 font-normal mt-0.5 tabular-nums text-right" />
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
            {headers.map((h, i) => {
              const active = h.col && sortBy === h.col;
              return (
                <th
                  key={i}
                  className={`px-6 py-3 ${h.align} ${h.col ? "cursor-pointer select-none hover:text-gray-600" : ""} ${active ? "text-gray-700" : ""}`}
                  onClick={() => h.col && toggleSort(h.col)}
                >
                  {h.label}{active && arrow}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.map((pos) => {
            const totalQty = Number.parseFloat(pos.liquid_quantity) + Number.parseFloat(pos.staked_quantity);
            return (
              <tr key={`${pos.provider}-${pos.symbol}`} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <span className="font-mono font-semibold text-gray-900">{pos.symbol}</span>
                  <p className="text-xs text-gray-400 mt-0.5">{PROVIDER_LABELS[pos.provider] ?? pos.provider}</p>
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  {fmtNum(totalQty.toString())}
                  {Number.parseFloat(pos.staked_quantity) > 0 && (
                    <p className="text-xs text-orange-400">
                      {fmtNum(pos.staked_quantity)} {t("content.crypto.stakeSuffix")}
                    </p>
                  )}
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  ${fmtNum(pos.unit_price_usd, 4)}
                </td>
                <td className="px-6 py-4 text-right">
                  <TLValue tl={pos.total_value_tl} className="font-semibold text-gray-900" />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
