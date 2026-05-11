"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, StockPositionDTO, StockHoldingDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { HoldingsForm, StockHoldingRow } from "./_components/HoldingsForm";
import { Toolbar } from "./_components/Toolbar";
import { StockPositionsTable } from "./_components/StockPositionsTable";
import { MkkHint } from "@/app/_components/MkkHint";
import { useTranslation } from "@/app/_i18n/I18nProvider";

function toDTO(holdings: StockHoldingRow[]): StockHoldingDTO[] {
  return holdings
    .filter((h) => h.ticker.trim() && Number.parseFloat(h.quantity) > 0)
    .map((h) => ({
      ticker: h.ticker.trim().toUpperCase(),
      quantity: Number.parseFloat(h.quantity),
      name: h.name.trim(),
      avg_cost_tl: h.avg_cost_tl.trim() ? Number.parseFloat(h.avg_cost_tl) : null,
      distributor: h.distributor.trim() || null,
    }));
}

export default function StocksPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [holdings, setHoldings] = useState<StockHoldingRow[]>([{ ticker: "", quantity: "", name: "", avg_cost_tl: "", distributor: "" }]);
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
    api.getStockHoldings()
      .then((data) => {
        if (data.length > 0) {
          setHoldings(data.map((h) => ({ ticker: h.ticker, quantity: h.quantity.toString(), name: h.name, avg_cost_tl: h.avg_cost_tl?.toString() ?? "", distributor: h.distributor ?? "" })));
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

  async function handleMkkUpload(file: File) {
    setError("");
    const imported = await api.importStockMkk(file);
    setHoldings(imported.map((h) => ({
      ticker: h.ticker,
      quantity: h.quantity.toString(),
      name: h.name,
      avg_cost_tl: h.avg_cost_tl?.toString() ?? "",
      distributor: h.distributor ?? "",
    })));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    fetchPricesFor(imported);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const imported = await api.importStockHoldings(file);
      setHoldings(imported.map((h) => ({ ticker: h.ticker, quantity: h.quantity.toString(), name: h.name, avg_cost_tl: h.avg_cost_tl?.toString() ?? "", distributor: h.distributor ?? "" })));
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

  function addRow() { setHoldings((h) => [...h, { ticker: "", quantity: "", name: "", avg_cost_tl: "", distributor: "" }]); }
  function removeRow(i: number) { setHoldings((h) => h.filter((_, idx) => idx !== i)); }
  function updateRow(i: number, field: keyof StockHoldingRow, val: string) {
    setHoldings((h) => h.map((row, idx) => idx === i ? { ...row, [field]: val } : row));
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.stocks")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Hisse Holdingleri</h2>
          <p className="text-xs text-gray-400 mb-2">
            BIST için <span className="font-mono bg-gray-50 px-1 rounded">THYAO.IS</span> formatını,
            ABD için <span className="font-mono bg-gray-50 px-1 rounded">AAPL</span> formatını kullanın.
          </p>
          <MkkHint onUpload={handleMkkUpload} />

          <HoldingsForm
            holdings={holdings}
            initialLoad={initialLoad}
            onUpdate={updateRow}
            onRemove={removeRow}
          />

          <Toolbar
            saved={saved}
            saving={saving}
            exporting={exporting}
            importing={importing}
            loading={loading}
            onAddRow={addRow}
            onSave={saveHoldings}
            onExport={handleExport}
            onImport={handleImport}
            onFetchPrices={fetchPrices}
          />

          {error && (
            <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
        </div>

        {result.length > 0 && <StockPositionsTable positions={result} />}
      </main>
    </div>
  );
}
