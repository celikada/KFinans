"use client";
import { useState } from "react";
import { api, WalletDTO } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { Chain } from "./constants";

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
  const [chain, setChain] = useState<Chain>("sonic");
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) { setFormError("Adres zorunludur"); return; }
    setSaving(true);
    setFormError("");
    try {
      const added = await api.addWallet(chain, address.trim(), label.trim() || undefined);
      onAdded(added);
      setAddress("");
      setLabel("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-5 space-y-3 border-t border-gray-50 pt-5">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        Cüzdan Ekle
      </h3>
      <div className="flex gap-3 flex-wrap">
        <select
          value={chain}
          onChange={(e) => setChain(e.target.value as Chain)}
          className={`w-44 ${INPUT_CLS}`}
        >
          <option value="sonic">Sonic (S)</option>
          <option value="avalanche_c">Avalanche C-Chain</option>
          <option value="avalanche_p">Avalanche P-Chain</option>
          <option value="ethereum">Ethereum</option>
        </select>
        <input
          placeholder={chain === "avalanche_p" ? "P-avax1..." : "0x..."}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          className={`flex-1 min-w-0 font-mono text-xs ${INPUT_CLS}`}
        />
        <input
          placeholder="Etiket (isteğe bağlı)"
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
          {saving ? "Kaydediliyor..." : "Ekle"}
        </button>
        {hasWallets && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loadingPositions}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {loadingPositions ? "Yükleniyor..." : "Yenile"}
          </button>
        )}
        <button
          type="button"
          onClick={onExport}
          disabled={exporting || !hasWallets}
          className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
        >
          {exporting ? "İndiriliyor..." : "Excel İndir"}
        </button>
        <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
          {importing ? "İçe aktarılıyor..." : "Excel Yükle"}
          <input type="file" accept=".xlsx,.xls" className="hidden" onChange={onImport} disabled={importing} />
        </label>
      </div>
    </form>
  );
}
