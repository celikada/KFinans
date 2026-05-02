"use client";
import { WalletDTO } from "@/lib/api";
import { shortAddr } from "@/lib/format";
import { CHAIN_LABELS } from "./constants";

interface Props {
  wallets: WalletDTO[];
  removing: string | null;
  onRemove: (walletId: string) => void;
}

export function WalletList({ wallets, removing, onRemove }: Props) {
  if (wallets.length === 0) {
    return <p className="text-sm text-gray-400">Henüz cüzdan eklenmedi.</p>;
  }

  return (
    <div className="space-y-2">
      {wallets.map((w) => (
        <div
          key={w.id}
          className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" />
            <div className="min-w-0">
              <span className="text-sm font-medium text-gray-800 block">
                {CHAIN_LABELS[w.chain] ?? w.chain}
                {w.label && <span className="text-gray-400 ml-1.5">· {w.label}</span>}
              </span>
              <span className="text-xs text-gray-400 font-mono">{shortAddr(w.address)}</span>
            </div>
          </div>
          <button
            onClick={() => onRemove(w.id)}
            disabled={removing === w.id}
            className="text-xs text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40 shrink-0 ml-3"
          >
            {removing === w.id ? "Siliniyor..." : "Kaldır"}
          </button>
        </div>
      ))}
    </div>
  );
}
