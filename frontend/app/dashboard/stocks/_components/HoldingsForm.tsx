"use client";
import { INPUT_CLS } from "@/lib/format";

export interface StockHoldingRow {
  ticker: string;
  quantity: string;
  name: string;
}

interface Props {
  holdings: StockHoldingRow[];
  initialLoad: boolean;
  onUpdate: (i: number, field: keyof StockHoldingRow, val: string) => void;
  onRemove: (i: number) => void;
}

export function HoldingsForm({ holdings, initialLoad, onUpdate, onRemove }: Props) {
  if (initialLoad) {
    return <p className="text-sm text-gray-400">Yükleniyor...</p>;
  }

  return (
    <div className="space-y-3">
      {holdings.map((row, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            placeholder="Ticker (THYAO.IS)"
            value={row.ticker}
            onChange={(e) => onUpdate(i, "ticker", e.target.value.toUpperCase())}
            className={`w-32 font-mono uppercase ${INPUT_CLS}`}
            maxLength={12}
          />
          <input
            placeholder="Adet"
            type="number"
            min="0"
            value={row.quantity}
            onChange={(e) => onUpdate(i, "quantity", e.target.value)}
            className={`w-32 ${INPUT_CLS}`}
          />
          <input
            placeholder="İsim (opsiyonel)"
            value={row.name}
            onChange={(e) => onUpdate(i, "name", e.target.value)}
            className={`flex-1 ${INPUT_CLS}`}
          />
          {holdings.length > 1 && (
            <button onClick={() => onRemove(i)} className="text-gray-300 hover:text-red-400 text-lg leading-none px-1">
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
