"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, WalletDTO, WalletPositionDTO } from "@/lib/api";

const INPUT_CLS =
  "px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400";

const CHAIN_LABELS: Record<string, string> = {
  sonic: "Sonic (S)",
  avalanche_c: "Avalanche C-Chain",
  avalanche_p: "Avalanche P-Chain",
  ethereum: "Ethereum",
};

const CHAIN_SYMBOLS: Record<string, string> = {
  sonic: "S",
  avalanche_c: "AVAX",
  avalanche_p: "AVAX",
  ethereum: "ETH",
};

function fmtNum(val: string | number, decimals = 4) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  });
}

function fmtTL(val: string | number) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function shortAddr(addr: string) {
  if (addr.length <= 16) return addr;
  return `${addr.slice(0, 8)}…${addr.slice(-6)}`;
}

export default function WalletsPage() {
  const router = useRouter();

  const [wallets, setWallets] = useState<WalletDTO[]>([]);
  const [positions, setPositions] = useState<WalletPositionDTO[]>([]);
  const [loadingPositions, setLoadingPositions] = useState(false);
  const [posError, setPosError] = useState("");

  const [chain, setChain] = useState<"sonic" | "avalanche_c" | "avalanche_p" | "ethereum">("sonic");
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    api.getWallets().then((data) => {
      setWallets(data);
      if (data.length > 0) fetchPositions();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchPositions() {
    setLoadingPositions(true);
    setPosError("");
    try {
      const { positions, errors } = await api.getWalletPositions();
      setPositions(positions.filter((p) => parseFloat(p.total_value_tl) > 0.01));
      if (Object.keys(errors).length > 0) {
        const msgs = Object.entries(errors)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" | ");
        setPosError(msgs);
      }
    } catch (err) {
      setPosError(err instanceof Error ? err.message : "Pozisyonlar alınamadı");
    } finally {
      setLoadingPositions(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) { setFormError("Adres zorunludur"); return; }
    setSaving(true);
    setFormError("");
    try {
      const added = await api.addWallet(chain, address.trim(), label.trim() || undefined);
      setWallets((prev) => [...prev, added]);
      setAddress("");
      setLabel("");
      fetchPositions();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      await api.exportWallets();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Export başarısız");
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setFormError("");
    try {
      const imported = await api.importWallets(file);
      setWallets(imported);
      if (imported.length > 0) fetchPositions();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  async function handleRemove(walletId: string) {
    setRemoving(walletId);
    try {
      await api.removeWallet(walletId);
      setWallets((prev) => prev.filter((w) => w.id !== walletId));
      setPositions((prev) => prev.filter((p) => p.wallet_id !== walletId));
    } finally {
      setRemoving(null);
    }
  }

  const totalTL = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ← Geri
        </button>
        <h1 className="text-lg font-semibold text-gray-900">Blockchain Cüzdanları</h1>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* Kayıtlı cüzdanlar */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Kayıtlı Cüzdanlar</h2>

          {wallets.length === 0 ? (
            <p className="text-sm text-gray-400">Henüz cüzdan eklenmedi.</p>
          ) : (
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
                    onClick={() => handleRemove(w.id)}
                    disabled={removing === w.id}
                    className="text-xs text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40 shrink-0 ml-3"
                  >
                    {removing === w.id ? "Siliniyor..." : "Kaldır"}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Cüzdan ekle formu */}
          <form onSubmit={handleAdd} className="mt-5 space-y-3 border-t border-gray-50 pt-5">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Cüzdan Ekle
            </h3>
            <div className="flex gap-3 flex-wrap">
              <select
                value={chain}
                onChange={(e) => setChain(e.target.value as typeof chain)}
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
              {wallets.length > 0 && (
                <button
                  type="button"
                  onClick={fetchPositions}
                  disabled={loadingPositions}
                  className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  {loadingPositions ? "Yükleniyor..." : "Yenile"}
                </button>
              )}
              <button
                type="button"
                onClick={handleExport}
                disabled={exporting || wallets.length === 0}
                className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
              >
                {exporting ? "İndiriliyor..." : "Excel İndir"}
              </button>
              <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
                {importing ? "İçe aktarılıyor..." : "Excel Yükle"}
                <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleImport} disabled={importing} />
              </label>
            </div>
          </form>
        </div>

        {/* Yükleniyor */}
        {loadingPositions && (
          <p className="text-sm text-gray-400 text-center py-4">
            Blockchain bakiyeleri sorgulanıyor...
          </p>
        )}

        {posError && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{posError}</p>
        )}

        {/* Pozisyonlar tablosu */}
        {!loadingPositions && positions.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Pozisyonlar</h2>
              <span className="text-lg font-bold text-gray-900">{fmtTL(totalTL)} ₺</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-6 py-3 text-left">Zincir / Cüzdan</th>
                  <th className="px-6 py-3 text-right">Miktar</th>
                  <th className="px-6 py-3 text-right">Fiyat (USD)</th>
                  <th className="px-6 py-3 text-right">Toplam (₺)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {[...positions]
                  .sort((a, b) => parseFloat(b.total_value_tl) - parseFloat(a.total_value_tl))
                  .map((pos, i) => {
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
                        <td className="px-6 py-4 text-right font-semibold text-gray-900">
                          {fmtTL(pos.total_value_tl)} ₺
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
