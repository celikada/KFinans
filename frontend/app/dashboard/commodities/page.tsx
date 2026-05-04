"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, type CommoditySummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL, TOOLBAR_BTN_CLS } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { CommodityForm } from "./_components/CommodityForm";
import { CommodityList } from "./_components/CommodityList";

export default function CommoditiesPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<CommoditySummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.getCommodities());
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    refresh();
  }, [refresh, router]);

  async function handleExport() {
    try {
      await api.exportCommodities();
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
      await api.importCommodities(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  const goldTotal = summary ? parseFloat(summary.total_value_tl) > 0
    ? summary.positions.filter(p => p.metal === "gold").reduce((s, p) => s + parseFloat(p.total_value_tl), 0)
    : 0 : 0;
  const silverTotal = summary ? summary.positions.filter(p => p.metal === "silver").reduce((s, p) => s + parseFloat(p.total_value_tl), 0) : 0;
  const totalTL = summary ? parseFloat(summary.total_value_tl) : 0;
  const goldPrice = summary ? parseFloat(summary.gold_price_tl) : null;
  const silverPrice = summary ? parseFloat(summary.silver_price_tl) : null;
  const hasGoldPositions = summary ? summary.positions.some(p => p.metal === "gold") : false;
  const hasSilverPositions = summary ? summary.positions.some(p => p.metal === "silver") : false;
  const goldUnavailable = summary ? !summary.gold_price_available : false;
  const silverUnavailable = summary ? !summary.silver_price_available && hasSilverPositions : false;
  // Altın yoksa bile (yeni hesap) altın çekilemiyorsa kullanıcıya bildir — fiyat panelini boş bırakmamak için
  const showGoldWarning = goldUnavailable;
  const showSilverWarning = silverUnavailable;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Altın & Gümüş" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {(showGoldWarning || showSilverWarning) && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <div className="text-sm text-amber-800">
              <p className="font-semibold">
                {showGoldWarning && showSilverWarning
                  ? "Altın ve gümüş fiyatları şu an çekilemiyor"
                  : showGoldWarning
                  ? "Altın fiyatı şu an çekilemiyor"
                  : "Gümüş fiyatı şu an çekilemiyor"}
              </p>
              <p className="text-xs mt-0.5 text-amber-700">
                Yahoo Finance fiyat endpoint&apos;i geçici olarak yanıt vermiyor.
                {showGoldWarning && hasGoldPositions && " Altın pozisyonlarınız toplam portföy değerine dahil edilmedi."}
                {showSilverWarning && " Gümüş pozisyonlarınız toplam portföy değerine dahil edilmedi."}
                {(hasGoldPositions || hasSilverPositions) && " Toplam, gerçek değerden düşük gözüküyor olabilir."}
                {" "}30 saniye sonra otomatik tekrar denenecek — sayfayı yenileyebilirsiniz.
              </p>
            </div>
          </div>
        )}

        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex flex-wrap gap-6 justify-between items-start">
            <div>
              <p className="text-xs text-gray-400 mb-1">Toplam değer</p>
              <TLValue tl={totalTL} className="text-3xl font-bold text-amber-600" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
              {summary && (
                <p className="text-xs text-gray-400 mt-1">{summary.positions.length} pozisyon</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {goldTotal > 0 && (
                <div className="text-right">
                  <p className="text-xs text-gray-400 mb-1">Altın</p>
                  <p className="text-lg font-semibold text-amber-700">{fmtTL(goldTotal)} ₺</p>
                  <p className="text-xs text-gray-400">{parseFloat(summary?.total_gold_gram ?? "0").toFixed(2)} g</p>
                </div>
              )}
              {silverTotal > 0 && (
                <div className="text-right">
                  <p className="text-xs text-gray-400 mb-1">Gümüş</p>
                  <p className="text-lg font-semibold text-gray-600">{fmtTL(silverTotal)} ₺</p>
                  <p className="text-xs text-gray-400">{parseFloat(summary?.total_silver_gram ?? "0").toFixed(2)} g</p>
                </div>
              )}
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
                  accept=".xlsx"
                  className="hidden"
                  onChange={handleImport}
                />
              </div>
            </div>
          </div>

          {/* Anlık kurlar */}
          {goldPrice !== null && (
            <div className="mt-4 pt-4 border-t border-gray-50 flex gap-6 text-xs text-gray-400">
              <span>Altın: <span className="text-gray-600 font-medium">{fmtTL(goldPrice)} ₺/g</span></span>
              {silverPrice !== null && silverPrice > 0 && (
                <span>Gümüş: <span className="text-gray-600 font-medium">{fmtTL(silverPrice)} ₺/g</span></span>
              )}
              <span className="ml-auto">Yahoo Finance · TCMB (5dk önbellek)</span>
            </div>
          )}
        </div>

        <CommodityForm onAdded={refresh} />

        {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && summary && <CommodityList positions={summary.positions} onDeleted={refresh} />}
      </main>
    </div>
  );
}
