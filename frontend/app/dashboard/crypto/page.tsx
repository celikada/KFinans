"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, IntegrationDTO, CryptoPositionDTO } from "@/lib/api";

const INPUT_CLS =
  "px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400";

const PROVIDER_LABELS: Record<string, string> = {
  binance: "Binance",
  icrypex: "iCrypex",
};

function fmtNum(val: string, decimals = 6) {
  return parseFloat(val).toLocaleString("tr-TR", {
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

export default function CryptoPage() {
  const router = useRouter();

  const [integrations, setIntegrations] = useState<IntegrationDTO[]>([]);
  const [positions, setPositions] = useState<CryptoPositionDTO[]>([]);
  const [loadingPositions, setLoadingPositions] = useState(false);
  const [posError, setPosError] = useState("");

  // form state
  const [provider, setProvider] = useState<"binance" | "icrypex">("binance");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"value" | "name" | "amount">("value");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  function toggleSort(col: "value" | "name" | "amount") {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir(col === "name" ? "asc" : "desc");
    }
  }

  useEffect(() => {
    api.getIntegrations().then((data) => {
      const crypto = data.filter((i) => i.provider === "binance" || i.provider === "icrypex");
      setIntegrations(crypto);
      if (crypto.length > 0) fetchPositions();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchPositions() {
    setLoadingPositions(true);
    setPosError("");
    try {
      const { positions, errors } = await api.getCryptoPositions();
      setPositions(positions.filter((p) => parseFloat(p.total_value_tl) > 0.01));
      if (Object.keys(errors).length > 0) {
        const msgs = Object.entries(errors)
          .map(([provider, err]) => `${PROVIDER_LABELS[provider] ?? provider}: ${err}`)
          .join(" | ");
        setPosError(msgs);
      }
    } catch (err) {
      setPosError(err instanceof Error ? err.message : "Pozisyonlar alınamadı");
    } finally {
      setLoadingPositions(false);
    }
  }

  async function handleAddIntegration(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) { setFormError(provider === "icrypex" ? "E-posta zorunludur" : "API Key zorunludur"); return; }
    if (!apiSecret.trim()) { setFormError(provider === "icrypex" ? "Şifre zorunludur" : "API Secret zorunludur"); return; }
    setSaving(true);
    setFormError("");
    try {
      const added = await api.addIntegration(provider, apiKey.trim(), apiSecret.trim() || undefined);
      setIntegrations((prev) => {
        const filtered = prev.filter((i) => i.provider !== provider);
        return [...filtered, added];
      });
      setApiKey("");
      setApiSecret("");
      fetchPositions();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(prov: string) {
    setRemoving(prov);
    try {
      await api.removeIntegration(prov);
      setIntegrations((prev) => prev.filter((i) => i.provider !== prov));
      setPositions((prev) => prev.filter((p) => p.provider !== prov));
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
        <h1 className="text-lg font-semibold text-gray-900">Kripto Portföyü</h1>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* Bağlı borsalar */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Bağlı Borsalar</h2>

          {integrations.length === 0 ? (
            <p className="text-sm text-gray-400">Henüz borsa eklenmedi.</p>
          ) : (
            <div className="space-y-2">
              {integrations.map((intg) => (
                <div
                  key={intg.provider}
                  className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-400" />
                    <span className="text-sm font-medium text-gray-800">
                      {PROVIDER_LABELS[intg.provider] ?? intg.provider}
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemove(intg.provider)}
                    disabled={removing === intg.provider}
                    className="text-xs text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40"
                  >
                    {removing === intg.provider ? "Siliniyor..." : "Kaldır"}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Borsa ekle formu */}
          <form onSubmit={handleAddIntegration} className="mt-5 space-y-3 border-t border-gray-50 pt-5">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Borsa Ekle / Güncelle
            </h3>
            <div className="flex gap-3 flex-wrap">
              <select
                value={provider}
                onChange={(e) => { setProvider(e.target.value as "binance" | "icrypex"); setApiSecret(""); }}
                className={`w-32 ${INPUT_CLS}`}
              >
                <option value="binance">Binance</option>
                <option value="icrypex">iCrypex</option>
              </select>
              <input
                placeholder={provider === "icrypex" ? "E-posta" : "API Key"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className={`flex-1 min-w-0 ${provider === "icrypex" ? "" : "font-mono"} text-xs ${INPUT_CLS}`}
              />
              <input
                placeholder={provider === "icrypex" ? "Şifre" : "API Secret"}
                type={provider === "icrypex" ? "password" : "text"}
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                className={`flex-1 min-w-0 ${provider === "icrypex" ? "" : "font-mono"} text-xs ${INPUT_CLS}`}
              />
            </div>
            {formError && (
              <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{formError}</p>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Kaydediliyor..." : "Kaydet"}
              </button>
              {integrations.length > 0 && (
                <button
                  type="button"
                  onClick={fetchPositions}
                  disabled={loadingPositions}
                  className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  {loadingPositions ? "Yükleniyor..." : "Yenile"}
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Pozisyonlar tablosu */}
        {loadingPositions && (
          <p className="text-sm text-gray-400 text-center py-4">
            Bakiyeler borsadan çekiliyor...
          </p>
        )}

        {posError && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{posError}</p>
        )}

        {!loadingPositions && positions.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Pozisyonlar</h2>
              <span className="text-lg font-bold text-gray-900">{fmtTL(totalTL)} ₺</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  {(["name", "amount", null, "value"] as const).map((col, i) => {
                    const labels = ["Coin", "Miktar", "Fiyat (USDT)", "Toplam (₺)"];
                    const aligns = ["text-left", "text-right", "text-right", "text-right"];
                    const active = col && sortBy === col;
                    const arrow = sortDir === "desc" ? " ↓" : " ↑";
                    return (
                      <th
                        key={i}
                        className={`px-6 py-3 ${aligns[i]} ${col ? "cursor-pointer select-none hover:text-gray-600" : ""} ${active ? "text-gray-700" : ""}`}
                        onClick={() => col && toggleSort(col)}
                      >
                        {labels[i]}{active && arrow}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {[...positions]
                  .sort((a, b) => {
                    const dir = sortDir === "desc" ? -1 : 1;
                    if (sortBy === "name") return dir * a.symbol.localeCompare(b.symbol);
                    if (sortBy === "amount") {
                      const qa = parseFloat(a.liquid_quantity) + parseFloat(a.staked_quantity);
                      const qb = parseFloat(b.liquid_quantity) + parseFloat(b.staked_quantity);
                      return dir * (qa - qb);
                    }
                    return dir * (parseFloat(a.total_value_tl) - parseFloat(b.total_value_tl));
                  })
                  .map((pos) => {
                    const totalQty = parseFloat(pos.liquid_quantity) + parseFloat(pos.staked_quantity);
                    return (
                      <tr key={`${pos.provider}-${pos.symbol}`} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4">
                          <span className="font-mono font-semibold text-gray-900">{pos.symbol}</span>
                          <p className="text-xs text-gray-400 mt-0.5">{PROVIDER_LABELS[pos.provider] ?? pos.provider}</p>
                        </td>
                        <td className="px-6 py-4 text-right text-gray-600">
                          {fmtNum(totalQty.toString())}
                          {parseFloat(pos.staked_quantity) > 0 && (
                            <p className="text-xs text-orange-400">
                              {fmtNum(pos.staked_quantity)} stake
                            </p>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-600">
                          ${fmtNum(pos.unit_price_usd, 4)}
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
