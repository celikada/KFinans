"use client";
import { useState } from "react";
import { api, WalletDTO } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { CHAIN_LABELS, Chain } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  hasWallets: boolean;
  loadingPositions: boolean;
  exporting: boolean;
  importing: boolean;
  onAdded: (wallet: WalletDTO) => void;
  onRefresh: () => void;
  onExport: () => void;
  onImport: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

export function WalletForm({
  hasWallets, loadingPositions, exporting, importing,
  onAdded, onRefresh, onExport, onImport,
}: Props) {
  const { t } = useTranslation();
  const [chain, setChain] = useState<Chain>("sonic");
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [showHint, setShowHint] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) { setFormError(t("form.addressRequired")); return; }
    setSaving(true);
    setFormError("");
    try {
      const added = await api.addWallet(chain, address.trim(), label.trim() || undefined);
      onAdded(added);
      setAddress("");
      setLabel("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t("form.addFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-5 space-y-3 border-t border-gray-50 pt-5">
      <div className="flex items-center gap-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          {t("form.addWallet")}
        </h3>
        <button
          type="button"
          onClick={() => setShowHint((s) => !s)}
          className="text-blue-500 hover:text-blue-700 transition-colors"
          aria-label={t("form.addressLookup")}
          title={t("form.addressLookup")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="w-4 h-4">
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4M12 8h.01" />
          </svg>
        </button>
      </div>
      {showHint && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5 text-xs text-gray-700 space-y-1">
          <p className="font-semibold text-blue-700">
            {CHAIN_LABELS[chain]} {t("form.chainAddressHowTo")}
          </p>
          <p>
            <span className="font-medium text-gray-600">{t("form.chainAddressFormat")} </span>
            <span className="font-mono text-[11px]">{t(`content.wallets.hints.${chain}.format`)}</span>
          </p>
          <p className="whitespace-pre-line text-gray-600 leading-relaxed">
            {t(`content.wallets.hints.${chain}.howTo`)}
          </p>
        </div>
      )}
      <div className="flex gap-3 flex-wrap">
        <select
          value={chain}
          onChange={(e) => setChain(e.target.value as Chain)}
          className={`w-44 ${INPUT_CLS}`}
        >
          <option value="bitcoin">Bitcoin</option>
          <option value="ethereum">Ethereum</option>
          <option value="sonic">Sonic (S)</option>
          <option value="avalanche_c">Avalanche C-Chain</option>
          <option value="avalanche_p">Avalanche P-Chain</option>
          <option value="solana">Solana</option>
          <option value="cardano">Cardano</option>
          <option value="algorand">Algorand</option>
          <option value="polkadot">Polkadot</option>
          <option value="litecoin">Litecoin</option>
        </select>
        <input
          placeholder={t(`content.wallets.placeholders.${chain}`)}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          className={`flex-1 min-w-0 font-mono text-xs ${INPUT_CLS}`}
        />
        <input
          placeholder={t("form.labelPlaceholder")}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className={`w-36 ${INPUT_CLS}`}
        />
      </div>
      {formError && (
        <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{formError}</p>
      )}
      <div className="flex gap-3 flex-wrap items-center">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? t("form.saving") : t("form.add")}
        </button>
        {hasWallets && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loadingPositions}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {loadingPositions ? t("form.refreshing") : t("form.refresh")}
          </button>
        )}
        <button
          type="button"
          onClick={onExport}
          disabled={exporting || !hasWallets}
          className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
        >
          {exporting ? t("form.downloading") : t("form.excelDownload")}
        </button>
        <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
          {importing ? t("form.uploading") : t("form.excelUpload")}
          <input type="file" accept=".xlsx,.xls" className="hidden" onChange={onImport} disabled={importing} />
        </label>
      </div>
    </form>
  );
}
