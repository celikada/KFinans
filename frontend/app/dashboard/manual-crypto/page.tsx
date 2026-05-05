"use client";
import { useEffect, useState, useCallback, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ManualCryptoSummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { TLValue } from "@/app/_components/TLValue";
import { fmtNum, fmtTL, INPUT_CLS, TOOLBAR_BTN_CLS } from "@/lib/format";

const EXCHANGE_OPTIONS = [
  { value: "binancetr", label: "Binance TR" },
  { value: "icrypex", label: "iCrypex" },
  { value: "btcturk", label: "BTC Türk" },
  { value: "paribu", label: "Paribu" },
  { value: "bybit", label: "Bybit" },
  { value: "kucoin", label: "KuCoin" },
  { value: "bitget", label: "Bitget" },
  { value: "other", label: "Diğer" },
];

export default function ManualCryptoPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<ManualCryptoSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  // Form state
  const [exchange, setExchange] = useState("binancetr");
  const [label, setLabel] = useState("");
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [notes, setNotes] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.listManualCrypto());
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
      return;
    }
    refresh();
  }, [refresh, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!exchange || !symbol.trim() || !quantity.trim()) {
      setError("Borsa, sembol ve miktar zorunlu");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.createManualCrypto({
        exchange,
        label: label.trim() || null,
        symbol: symbol.trim().toUpperCase(),
        quantity: parseFloat(quantity),
        avg_cost_tl: avgCost.trim() ? parseFloat(avgCost) : null,
        notes: notes.trim() || null,
      });
      setLabel("");
      setSymbol("");
      setQuantity("");
      setAvgCost("");
      setNotes("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, sym: string) {
    if (!confirm(`${sym} silinsin mi?`)) return;
    try {
      await api.deleteManualCrypto(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silme başarısız");
    }
  }

  async function handleExport() {
    try {
      await api.exportManualCrypto();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export başarısız");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const result = await api.importManualCrypto(file);
      if (result.errors.length > 0) {
        setError(`${result.imported} satır yüklendi, ${result.errors.length} hata: ${result.errors.slice(0, 3).join("; ")}`);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  const totalTL = summary ? parseFloat(summary.total_value_tl) : 0;
  const positions = summary?.positions ?? [];
  const unknownSymbols = summary?.unknown_symbols ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Manuel Kripto (API'siz Borsalar)" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Bilgi banner */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-900">
          <p className="font-medium mb-1">API erişimi olmayan borsalar için manuel giriş</p>
          <p className="text-xs text-blue-700">
            BinanceTR, iCrypex gibi public read-only API anahtarı vermeyen borsaları buraya ekleyebilirsin.
            Anlık fiyat Binance USDT pariteleri üzerinden hesaplanır. İleride API geldiğinde geçişi yaparız.
          </p>
        </div>

        {/* Bilinmeyen sembol uyarısı */}
        {unknownSymbols.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
            <p className="font-medium mb-1">⚠ Fiyatı bulunamayan semboller</p>
            <p className="text-xs">
              <strong>{unknownSymbols.join(", ")}</strong> için Binance USDT pariteni bulamadık.
              Bu pozisyonların TL değeri 0 olarak gösteriliyor.
              Sembol yazımını kontrol edin (BTC, ETH, USDT...) — küçük altcoin'ler dinlenmiyor olabilir.
            </p>
          </div>
        )}

        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex flex-wrap gap-6 justify-between items-start">
            <div>
              <p className="text-xs text-gray-400 mb-1">Toplam manuel kripto</p>
              <TLValue
                tl={totalTL}
                className="text-3xl font-bold text-gray-900"
                usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums"
              />
              <p className="text-xs text-gray-400 mt-1">
                {positions.length} pozisyon · {new Set(positions.map((p) => p.exchange)).size} borsa
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={handleExport} className={TOOLBAR_BTN_CLS}>
                Excel İndir
              </button>
              <button
                onClick={() => importRef.current?.click()}
                disabled={importing}
                className={TOOLBAR_BTN_CLS}
              >
                {importing ? "Yükleniyor..." : "Excel Yükle"}
              </button>
              <input
                ref={importRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleImport}
              />
            </div>
          </div>
        </div>

        {/* Yeni kayıt formu */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3"
        >
          <h2 className="text-sm font-semibold text-gray-700">Yeni Pozisyon</h2>
          <div className="grid grid-cols-1 sm:grid-cols-6 gap-2">
            <select
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              className={`sm:col-span-2 ${INPUT_CLS}`}
            >
              {EXCHANGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              placeholder="Sembol (BTC)"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className={`sm:col-span-1 ${INPUT_CLS}`}
              maxLength={20}
            />
            <input
              type="number"
              placeholder="Miktar"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              min="0"
              step="any"
              className={`sm:col-span-1 ${INPUT_CLS}`}
            />
            <input
              type="number"
              placeholder="Ort. maliyet TL (ops.)"
              value={avgCost}
              onChange={(e) => setAvgCost(e.target.value)}
              min="0"
              step="0.01"
              className={`sm:col-span-2 ${INPUT_CLS}`}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              placeholder="Etiket (BinanceTR Earn... ops.)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={INPUT_CLS}
              maxLength={100}
            />
            <input
              placeholder="Not (ops.)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={INPUT_CLS}
              maxLength={500}
            />
          </div>
          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Kaydediliyor..." : "Ekle"}
          </button>
        </form>

        {/* Liste */}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && positions.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">Henüz manuel kripto kaydı yok.</p>
        )}
        {!loading && positions.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">Borsa</th>
                  <th className="px-4 py-3 text-left">Sembol</th>
                  <th className="px-4 py-3 text-right">Miktar</th>
                  <th className="px-4 py-3 text-right">Anlık Fiyat</th>
                  <th className="px-4 py-3 text-right">TL Değer</th>
                  <th className="px-4 py-3 text-right">Kâr/Zarar</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {positions.map((p) => {
                  const exchangeLabel = EXCHANGE_OPTIONS.find((o) => o.value === p.exchange)?.label ?? p.exchange;
                  const gainLoss = p.gain_loss_tl ? parseFloat(p.gain_loss_tl) : null;
                  const gainPct = p.gain_loss_pct;
                  return (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{exchangeLabel}</p>
                        {p.label && <p className="text-xs text-gray-400">{p.label}</p>}
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 tabular-nums">{p.symbol}</p>
                        {p.notes && <p className="text-xs text-gray-400 mt-0.5">{p.notes}</p>}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                        {fmtNum(p.quantity, 8)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 tabular-nums">
                        {parseFloat(p.unit_price_tl) > 0 ? `${fmtTL(p.unit_price_tl)} ₺` : <span className="text-amber-600">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <TLValue tl={p.total_value_tl} className="font-semibold text-gray-900" />
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {gainLoss !== null && gainPct !== null ? (
                          <span className={gainLoss >= 0 ? "text-green-600" : "text-red-600"}>
                            {gainLoss >= 0 ? "+" : ""}{fmtTL(gainLoss)} ₺
                            <span className="block text-xs">
                              {gainLoss >= 0 ? "+" : ""}{gainPct.toFixed(1)}%
                            </span>
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDelete(p.id, p.symbol)}
                          className="text-gray-400 hover:text-red-500 text-sm"
                          title="Sil"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-gray-400 text-center">
          Anlık fiyatlar Binance USDT pariteleri ve TCMB USD/TRY kuru üzerinden hesaplanır.
        </p>
      </main>
    </div>
  );
}
