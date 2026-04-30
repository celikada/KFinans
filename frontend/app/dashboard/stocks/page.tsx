"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, StockPositionDTO, StockHoldingDTO } from "@/lib/api";

interface Holding {
  ticker: string;
  quantity: string;
  name: string;
}

const INPUT_CLS =
  "px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400";

function fmtTL(val: string | number) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtNum(val: string | number, dec = 4) {
  return parseFloat(val.toString()).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: dec,
  });
}

function toDTO(holdings: Holding[]): StockHoldingDTO[] {
  return holdings
    .filter((h) => h.ticker.trim() && parseFloat(h.quantity) > 0)
    .map((h) => ({ ticker: h.ticker.trim().toUpperCase(), quantity: parseFloat(h.quantity), name: h.name.trim() }));
}

export default function StocksPage() {
  const router = useRouter();
  const [holdings, setHoldings] = useState<Holding[]>([{ ticker: "", quantity: "", name: "" }]);
  const [result, setResult] = useState<StockPositionDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    api.getStockHoldings()
      .then((data) => {
        if (data.length > 0) {
          setHoldings(data.map((h) => ({ ticker: h.ticker, quantity: h.quantity.toString(), name: h.name })));
          fetchPricesFor(data);
        }
      })
      .catch((err) => {
        if (err instanceof Error && err.message.includes("401")) handle401();
      })
      .finally(() => setInitialLoad(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchPricesFor(valid: StockHoldingDTO[]) {
    setLoading(true);
    setError("");
    try {
      setResult(await api.stockPreview(valid));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { handle401(); return; }
      setError(err instanceof Error ? err.message : "Fiyat alınamadı");
    } finally {
      setLoading(false);
    }
  }

  async function fetchPrices() {
    const valid = toDTO(holdings);
    if (!valid.length) { setError("En az bir ticker ve adet giriniz"); return; }
    await fetchPricesFor(valid);
  }

  async function saveHoldings() {
    const valid = toDTO(holdings);
    if (!valid.length) { setError("Kaydedilecek geçerli holding yok"); return; }
    setSaving(true);
    setError("");
    try {
      await api.saveStockHoldings(valid);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { handle401(); return; }
      setError(err instanceof Error ? err.message : "Kaydetme başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setError("");
    try {
      await api.exportStockHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export başarısız");
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const imported = await api.importStockHoldings(file);
      setHoldings(imported.map((h) => ({ ticker: h.ticker, quantity: h.quantity.toString(), name: h.name })));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      fetchPricesFor(imported);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { handle401(); return; }
      setError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  function addRow() { setHoldings((h) => [...h, { ticker: "", quantity: "", name: "" }]); }
  function removeRow(i: number) { setHoldings((h) => h.filter((_, idx) => idx !== i)); }
  function updateRow(i: number, field: keyof Holding, val: string) {
    setHoldings((h) => h.map((row, idx) => idx === i ? { ...row, [field]: val } : row));
  }

  const totalTL = result.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button onClick={() => router.push("/dashboard")} className="text-gray-400 hover:text-gray-600 text-sm">
          ← Geri
        </button>
        <h1 className="text-lg font-semibold text-gray-900">Hisse Senedi Portföyü</h1>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Hisse Holdingleri</h2>
          <p className="text-xs text-gray-400 mb-4">
            BIST için <span className="font-mono bg-gray-50 px-1 rounded">THYAO.IS</span> formatını,
            ABD için <span className="font-mono bg-gray-50 px-1 rounded">AAPL</span> formatını kullanın.
          </p>

          {initialLoad ? (
            <p className="text-sm text-gray-400">Yükleniyor...</p>
          ) : (
            <div className="space-y-3">
              {holdings.map((row, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input
                    placeholder="Ticker (THYAO.IS)"
                    value={row.ticker}
                    onChange={(e) => updateRow(i, "ticker", e.target.value.toUpperCase())}
                    className={`w-32 font-mono uppercase ${INPUT_CLS}`}
                    maxLength={12}
                  />
                  <input
                    placeholder="Adet"
                    type="number"
                    min="0"
                    value={row.quantity}
                    onChange={(e) => updateRow(i, "quantity", e.target.value)}
                    className={`w-32 ${INPUT_CLS}`}
                  />
                  <input
                    placeholder="İsim (opsiyonel)"
                    value={row.name}
                    onChange={(e) => updateRow(i, "name", e.target.value)}
                    className={`flex-1 ${INPUT_CLS}`}
                  />
                  {holdings.length > 1 && (
                    <button onClick={() => removeRow(i)} className="text-gray-300 hover:text-red-400 text-lg leading-none px-1">
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3 mt-4 items-center flex-wrap">
            <button onClick={addRow} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              + Hisse ekle
            </button>
            <button
              onClick={saveHoldings}
              disabled={saving}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {saved ? "✓ Kaydedildi" : saving ? "Kaydediliyor..." : "Kaydet"}
            </button>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {exporting ? "İndiriliyor..." : "Excel İndir"}
            </button>
            <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
              {importing ? "İçe aktarılıyor..." : "Excel Yükle"}
              <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleImport} disabled={importing} />
            </label>
            <button
              onClick={fetchPrices}
              disabled={loading}
              className="ml-auto px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {loading ? "Yükleniyor..." : "Fiyatları Getir"}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
        </div>

        {result.length > 0 && (
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
                  <th className="px-6 py-3 text-right">Ağırlık</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {result.map((pos) => {
                  const weight = totalTL > 0 ? (parseFloat(pos.total_value_tl) / totalTL) * 100 : 0;
                  const isTRY = pos.currency === "TRY";
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
        )}
      </main>
    </div>
  );
}
