"use client";
import { useState } from "react";
import { api, COIN_LABELS, BIGA_GRAM_WEIGHTS, type CommodityPositionDTO } from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  positions: CommodityPositionDTO[];
  onDeleted: () => void;
}

function label(pos: CommodityPositionDTO): string {
  if (pos.unit_type === "coin") return COIN_LABELS[pos.coin_type as keyof typeof COIN_LABELS] ?? pos.coin_type ?? "";
  if (pos.unit_type === "biga") return `BiGA ${pos.biga_code} (${BIGA_GRAM_WEIGHTS[pos.biga_code!]}g)`;
  return pos.metal === "gold" ? "Altın (gram)" : "Gümüş (gram)";
}

function unitLabel(pos: CommodityPositionDTO): string {
  if (pos.unit_type === "gram") return `${parseFloat(pos.quantity).toFixed(4)} g`;
  return `${parseFloat(pos.quantity).toFixed(pos.unit_type === "biga" ? 0 : 0)} adet`;
}

export function CommodityList({ positions, onDeleted }: Props) {
  const { t } = useTranslation();
  const [deletingId, setDeletingId] = useState<number | null>(null);

  if (positions.length === 0) {
    return <p className="text-center text-sm text-gray-400 py-8">{t("empty.noCommodity")}</p>;
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await api.deleteCommodity(id);
      onDeleted();
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-400 border-b border-gray-50">
            <th className="text-left px-4 py-3 font-medium">{t("table.asset")}</th>
            <th className="text-right px-4 py-3 font-medium">{t("table.quantity")}</th>
            <th className="text-right px-4 py-3 font-medium">{t("table.gramEquivalent")}</th>
            <th className="text-right px-4 py-3 font-medium">{t("table.tlValue")}</th>
            <th className="px-3 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {positions.map((pos) => (
            <tr key={pos.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <span className="font-medium text-gray-800">{label(pos)}</span>
                {pos.notes && <span className="block text-xs text-gray-400">{pos.notes}</span>}
              </td>
              <td className="px-4 py-3 text-right text-gray-600 tabular-nums">{unitLabel(pos)}</td>
              <td className="px-4 py-3 text-right text-gray-500 tabular-nums">
                {parseFloat(pos.gram_equivalent).toFixed(2)} g
              </td>
              <td className="px-4 py-3 text-right">
                <TLValue tl={pos.total_value_tl} className="font-semibold text-amber-700 tabular-nums" />
              </td>
              <td className="px-3 py-3 text-right">
                <button
                  onClick={() => handleDelete(pos.id)}
                  disabled={deletingId === pos.id}
                  className="text-gray-300 hover:text-red-400 transition-colors disabled:opacity-50 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                  aria-label="Kaydı sil"
                >
                  <span aria-hidden="true">✕</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
