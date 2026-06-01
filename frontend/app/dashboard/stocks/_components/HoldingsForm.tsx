"use client";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export interface StockHoldingRow {
  ticker: string;
  quantity: string;
  name: string;
  avg_cost_tl: string;
  distributor: string;
}

interface Props {
  holdings: StockHoldingRow[];
  initialLoad: boolean;
  onUpdate: (i: number, field: keyof StockHoldingRow, val: string) => void;
  onRemove: (i: number) => void;
}

export function HoldingsForm({ holdings, initialLoad, onUpdate, onRemove }: Readonly<Props>) {
  const { t } = useTranslation();
  if (initialLoad) {
    return <p className="text-sm text-gray-400">{t("common.loading")}</p>;
  }

  return (
    <div className="space-y-3">
      {holdings.map((row, i) => (
        <div key={i} className="flex gap-2 items-center flex-wrap">
          <input
            placeholder={t("form.stockTickerPlaceholder")}
            value={row.ticker}
            onChange={(e) => onUpdate(i, "ticker", e.target.value.toUpperCase())}
            className={`w-32 font-mono uppercase ${INPUT_CLS}`}
            maxLength={12}
          />
          <input
            placeholder={t("table.count")}
            type="number"
            min="0"
            value={row.quantity}
            onChange={(e) => onUpdate(i, "quantity", e.target.value)}
            className={`w-28 ${INPUT_CLS}`}
          />
          <input
            placeholder={t("form.avgCostTl")}
            type="number"
            min="0"
            step="0.01"
            value={row.avg_cost_tl}
            onChange={(e) => onUpdate(i, "avg_cost_tl", e.target.value)}
            className={`w-36 ${INPUT_CLS}`}
            title={t("content.stocks.avgCostTitle")}
          />
          <input
            placeholder={t("form.stockDistributorPlaceholder")}
            value={row.distributor}
            onChange={(e) => onUpdate(i, "distributor", e.target.value)}
            className={`w-44 ${INPUT_CLS}`}
            maxLength={50}
            title={t("content.stocks.distributorTitle")}
          />
          <input
            placeholder={t("content.stocks.namePlaceholder")}
            value={row.name}
            onChange={(e) => onUpdate(i, "name", e.target.value)}
            className={`flex-1 min-w-[120px] ${INPUT_CLS}`}
          />
          {holdings.length > 1 && (
            <button onClick={() => onRemove(i)} className="text-gray-300 hover:text-red-400 text-lg leading-none px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded" aria-label={t("content.stocks.removeRow")}>
              <span aria-hidden="true">×</span>
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
