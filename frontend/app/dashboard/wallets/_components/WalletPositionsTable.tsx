"use client";
import { WalletPositionDTO } from "@/lib/api";
import { fmtNum, shortAddr } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { CHAIN_LABELS } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  positions: WalletPositionDTO[];
}

export function WalletPositionsTable({ positions }: Props) {
  const { t } = useTranslation();
  const totalTL = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);

  const sorted = [...positions].sort(
    (a, b) => parseFloat(b.total_value_tl) - parseFloat(a.total_value_tl)
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">{t("dashboard.position")}</h2>
        <TLValue tl={totalTL} className="text-lg font-bold text-gray-900" usdClassName="block text-xs text-gray-400 font-normal mt-0.5 tabular-nums text-right" />
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
            <th className="px-6 py-3 text-left">{t("table.chainWallet")}</th>
            <th className="px-6 py-3 text-right">{t("table.quantity")}</th>
            <th className="px-6 py-3 text-right">{t("table.priceUsd")}</th>
            <th className="px-6 py-3 text-right">{t("table.totalTl")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.map((pos, i) => {
            const liquid = parseFloat(pos.liquid_quantity);
            const staked = parseFloat(pos.staked_quantity);
            const rewards = parseFloat(pos.pending_rewards);
            const total = liquid + staked;
            return (
              <tr key={i} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <span className="font-mono font-semibold text-gray-900">{pos.symbol}</span>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {CHAIN_LABELS[pos.chain] ?? pos.chain}
                    {pos.label && <span className="ml-1">· {pos.label}</span>}
                  </p>
                  <p className="text-xs text-gray-300 font-mono">{shortAddr(pos.address)}</p>
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  {fmtNum(total.toString())}
                  {staked > 0 && (
                    <p className="text-xs text-orange-400">{fmtNum(staked.toString())} stake</p>
                  )}
                  {rewards > 0 && (
                    <p className="text-xs text-green-400">{fmtNum(rewards.toString())} ödül</p>
                  )}
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  ${fmtNum(pos.unit_price_usd, 2)}
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
