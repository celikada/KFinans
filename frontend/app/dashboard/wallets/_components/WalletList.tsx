"use client";
import { WalletDTO } from "@/lib/api";
import { shortAddr } from "@/lib/format";
import { CHAIN_LABELS } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly wallets: WalletDTO[];
  readonly removing: string | null;
  readonly onRemove: (walletId: string) => void;
  /** wallet_id → hata mesajı (canlı cache wallet_errors); sorunlu cüzdan ⚠ ile işaretlenir. */
  readonly walletErrors?: Record<string, string>;
  /** Tek cüzdanı yeniden hesaplat (per-cüzdan yenile ikonu). */
  readonly onRefreshWallet?: (walletId: string) => void;
  /** Şu an yenilemesi süren cüzdan id (yalnız o satır spinner/disabled). */
  readonly refreshingWalletId?: string | null;
}

export function WalletList({
  wallets,
  removing,
  onRemove,
  walletErrors,
  onRefreshWallet,
  refreshingWalletId,
}: Props) {
  const { t } = useTranslation();
  if (wallets.length === 0) {
    return <p className="text-sm text-gray-400">{t("content.wallets.noWallets")}</p>;
  }

  return (
    <div className="space-y-2">
      {wallets.map((w) => {
        const errMsg = walletErrors?.[w.id];
        const refreshing = refreshingWalletId === w.id;
        return (
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
                  {errMsg && (
                    <span
                      title={errMsg}
                      aria-label={t("content.wallets.walletProblem")}
                      className="ml-1.5 text-amber-500 cursor-help"
                    >
                      <span aria-hidden="true">⚠</span>
                    </span>
                  )}
                </span>
                <span className="text-xs text-gray-400 font-mono">{shortAddr(w.address)}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-3">
              {onRefreshWallet && (
                <button
                  type="button"
                  onClick={() => onRefreshWallet(w.id)}
                  disabled={refreshing}
                  aria-label={t("content.wallets.refreshWallet")}
                  title={t("content.wallets.refreshWallet")}
                  className="text-xs text-gray-400 hover:text-violet-500 transition-colors disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-violet-500 rounded"
                >
                  <span aria-hidden="true" className={refreshing ? "inline-block animate-spin" : "inline-block"}>
                    🔄
                  </span>
                </button>
              )}
              <button
                onClick={() => onRemove(w.id)}
                disabled={removing === w.id}
                className="text-xs text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40"
              >
                {removing === w.id ? t("content.wallets.removing") : t("content.wallets.remove")}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
