"use client";
import { StockPositionDTO } from "@/lib/api";
import { fmtNum, fmtTL } from "@/lib/format";

interface Props {
  positions: StockPositionDTO[];
}

export function StockPositionsTable({ positions }: Props) {
  const totalTL = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
  const hasGainLoss = positions.some((p) => p.gain_loss_tl !== null);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">Portföy</h2>
        <span className="text-lg font-bold text-gray-900">{fmtTL(totalTL)} ₺</span>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
            <th className="px-6 py-3 text-left">Hisse</th>
            <th className="px-6 py-3 text-right">Adet</th>
            <th className="px-6 py-3 text-right">Birim Fiyat</th>
            <th className="px-6 py-3 text-right">Toplam Değer</th>
            {hasGainLoss && <th className="px-6 py-3 text-right">Kâr / Zarar</th>}
            <th className="px-6 py-3 text-right">Ağırlık</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {positions.map((pos) => {
            const weight = totalTL > 0 ? (parseFloat(pos.total_value_tl) / totalTL) * 100 : 0;
            const isTRY = pos.currency === "TRY";
            const gl = pos.gain_loss_tl !== null ? parseFloat(pos.gain_loss_tl) : null;
            const glPct = pos.gain_loss_pct;
            const isPositive = gl !== null && gl >= 0;

            return (
              <tr key={pos.ticker} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <span className="font-mono font-semibold text-gray-900">{pos.ticker}</span>
                  {pos.name && (
                    <p className="text-xs text-gray-400 mt-0.5 truncate max-w-48">{pos.name}</p>
                  )}
                  <span className="text-xs text-gray-300">{pos.currency}</span>
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  {fmtNum(pos.quantity, 2)}
                </td>
                <td className="px-6 py-4 text-right text-gray-600">
                  {isTRY
                    ? `${fmtTL(pos.unit_price_tl)} ₺`
                    : `$${fmtNum(pos.unit_price_original, 2)}`}
                  {!isTRY && (
                    <p className="text-xs text-gray-400">{fmtTL(pos.unit_price_tl)} ₺</p>
                  )}
                </td>
                <td className="px-6 py-4 text-right font-semibold text-gray-900">
                  {fmtTL(pos.total_value_tl)} ₺
                </td>
                {hasGainLoss && (
                  <td className="px-6 py-4 text-right">
                    {gl !== null ? (
                      <span className={`font-medium ${isPositive ? "text-emerald-600" : "text-red-500"}`}>
                        {isPositive ? "+" : ""}{fmtTL(gl)} ₺
                        {glPct !== null && (
                          <p className="text-xs font-normal">
                            {isPositive ? "+" : ""}{glPct.toFixed(2)}%
                          </p>
                        )}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-300">—</span>
                    )}
                  </td>
                )}
                <td className="px-6 py-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-16 bg-gray-100 rounded-full h-1.5">
                      <div
                        className="bg-green-500 h-1.5 rounded-full"
                        style={{ width: `${Math.min(weight, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-10 text-right">{weight.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
