"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, TefasPosition } from "@/lib/api";

interface Holding {
  code: string;
  quantity: string;
  name: string;
}

function fmt(val: string) {
  return parseFloat(val).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtTL(val: string) {
  return parseFloat(val).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function TefasPage() {
  const router = useRouter();
  const [holdings, setHoldings] = useState<Holding[]>([
    { code: "", quantity: "", name: "" },
  ]);
  const [result, setResult] = useState<TefasPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function addRow() {
    setHoldings((h) => [...h, { code: "", quantity: "", name: "" }]);
  }

  function removeRow(i: number) {
    setHoldings((h) => h.filter((_, idx) => idx !== i));
  }

  function updateRow(i: number, field: keyof Holding, val: string) {
    setHoldings((h) => h.map((row, idx) => idx === i ? { ...row, [field]: val } : row));
  }

  async function fetchPrices() {
    setError("");
    const valid = holdings.filter((h) => h.code.trim() && parseFloat(h.quantity) > 0);
    if (!valid.length) { setError("En az bir fon kodu ve adet giriniz"); return; }
    setLoading(true);
    try {
      const data = await api.tefasPreview(
        valid.map((h) => ({ code: h.code.trim().toUpperCase(), quantity: parseFloat(h.quantity), name: h.name.trim() }))
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata oluştu");
    } finally {
      setLoading(false);
    }
  }

  const totalTL = result.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button onClick={() => router.push("/dashboard")} className="text-gray-400 hover:text-gray-600 text-sm">
          ← Geri
        </button>
        <h1 className="text-lg font-semibold text-gray-900">TEFAS Fon Portföyü</h1>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {/* Giriş formu */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Fon Holdingleri</h2>

          <div className="space-y-3">
            {holdings.map((row, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  placeholder="Fon Kodu (YAC)"
                  value={row.code}
                  onChange={(e) => updateRow(i, "code", e.target.value.toUpperCase())}
                  className="w-28 px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono uppercase focus:outline-none focus:ring-2 focus:ring-blue-500"
                  maxLength={6}
                />
                <input
                  placeholder="Adet"
                  type="number"
                  min="0"
                  value={row.quantity}
                  onChange={(e) => updateRow(i, "quantity", e.target.value)}
                  className="w-32 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  placeholder="İsim (opsiyonel)"
                  value={row.name}
                  onChange={(e) => updateRow(i, "name", e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {holdings.length > 1 && (
                  <button onClick={() => removeRow(i)} className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-3 mt-4">
            <button
              onClick={addRow}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              + Fon ekle
            </button>
            <button
              onClick={fetchPrices}
              disabled={loading}
              className="ml-auto px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? "Yükleniyor..." : "Fiyatları Getir"}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
        </div>

        {/* Sonuçlar */}
        {result.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Portföy</h2>
              <span className="text-lg font-bold text-gray-900">{fmtTL(totalTL.toString())} ₺</span>
            </div>

            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-6 py-3 text-left">Fon</th>
                  <th className="px-6 py-3 text-right">Adet</th>
                  <th className="px-6 py-3 text-right">Birim Fiyat</th>
                  <th className="px-6 py-3 text-right">Toplam Değer</th>
                  <th className="px-6 py-3 text-right">Ağırlık</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {result.map((pos) => {
                  const weight = totalTL > 0 ? (parseFloat(pos.total_value_tl) / totalTL) * 100 : 0;
                  return (
                    <tr key={pos.code} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4">
                        <span className="font-mono font-semibold text-gray-900">{pos.code}</span>
                        {pos.name && (
                          <p className="text-xs text-gray-400 mt-0.5 truncate max-w-48">{pos.name}</p>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right text-gray-600">{fmt(pos.quantity)}</td>
                      <td className="px-6 py-4 text-right text-gray-600">{fmt(pos.unit_price_tl)} ₺</td>
                      <td className="px-6 py-4 text-right font-semibold text-gray-900">{fmtTL(pos.total_value_tl)} ₺</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 bg-gray-100 rounded-full h-1.5">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
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
