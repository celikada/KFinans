"use client";
import { useState, useRef } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { LivePortfolioBar } from "@/app/_components/LivePortfolioBar";
import { useLivePortfolio } from "@/app/_hooks/useLivePortfolio";
import { fmtTL, TOOLBAR_BTN_CLS } from "@/lib/format";
import { TLValue } from "@/app/_components/TLValue";
import { CommodityForm } from "./_components/CommodityForm";
import { CommodityList } from "./_components/CommodityList";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function CommoditiesPage() {
  const { t } = useTranslation();
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  // Kıymetli maden özeti sunucu-cache'ten (/portfolio/live). Ekleme/silme/import
  // sonrası live.refresh() arka planda yeniden hesaplatır.
  const live = useLivePortfolio();
  const summary = live.data?.sections.commodities ?? null;
  const loading = live.loading;

  async function handleExport() {
    try {
      await api.exportCommodities();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.commodities.exportFailed"));
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      await api.importCommodities(file);
      await live.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.commodities.importFailed"));
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  const totalTL = Number.parseFloat(summary?.total_value_tl ?? "0");
  const sumMetal = (metal: string) =>
    (summary?.positions ?? [])
      .filter(p => p.metal === metal)
      .reduce((s, p) => s + Number.parseFloat(p.total_value_tl), 0);
  const goldTotal = totalTL > 0 ? sumMetal("gold") : 0;
  const silverTotal = sumMetal("silver");
  const goldPrice = summary ? Number.parseFloat(summary.gold_price_tl) : null;
  const silverPrice = summary ? Number.parseFloat(summary.silver_price_tl) : null;
  const hasGoldPositions = summary ? summary.positions.some(p => p.metal === "gold") : false;
  const hasSilverPositions = summary ? summary.positions.some(p => p.metal === "silver") : false;
  const goldUnavailable = summary ? !summary.gold_price_available : false;
  const silverUnavailable = summary ? !summary.silver_price_available && hasSilverPositions : false;
  // Altın yoksa bile (yeni hesap) altın çekilemiyorsa kullanıcıya bildir — fiyat panelini boş bırakmamak için
  const showGoldWarning = goldUnavailable;
  const showSilverWarning = silverUnavailable;

  let warningTitle = t("content.commodities.silverUnavailable");
  if (showGoldWarning && showSilverWarning) warningTitle = t("content.commodities.bothUnavailable");
  else if (showGoldWarning) warningTitle = t("content.commodities.goldUnavailable");

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.commodities")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="flex justify-end">
          <LivePortfolioBar
            refreshedAt={live.data?.refreshed_at ?? null}
            stale={live.data?.stale ?? false}
            refreshing={live.refreshing}
            onRefresh={live.refresh}
          />
        </div>

        {(showGoldWarning || showSilverWarning) && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <div className="text-sm text-amber-800">
              <p className="font-semibold">
                {warningTitle}
              </p>
              <p className="text-xs mt-0.5 text-amber-700">
                {t("content.commodities.unavailableIntro")}
                {showGoldWarning && hasGoldPositions && ` ${t("content.commodities.goldExcluded")}`}
                {showSilverWarning && ` ${t("content.commodities.silverExcluded")}`}
                {(hasGoldPositions || hasSilverPositions) && ` ${t("content.commodities.totalLower")}`}
                {" "}{t("content.commodities.retryNote")}
              </p>
            </div>
          </div>
        )}

        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex flex-wrap gap-6 justify-between items-start">
            <div>
              <p className="text-xs text-gray-400 mb-1">{t("content.commodities.totalValue")}</p>
              <TLValue tl={totalTL} className="text-3xl font-bold text-amber-600" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
              {summary && (
                <p className="text-xs text-gray-400 mt-1">{summary.positions.length} {t("content.commodities.positions")}</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {goldTotal > 0 && (
                <div className="text-right">
                  <p className="text-xs text-gray-400 mb-1">{t("content.commodities.gold")}</p>
                  <p className="text-lg font-semibold text-amber-700">{fmtTL(goldTotal)} ₺</p>
                  <p className="text-xs text-gray-400">{Number.parseFloat(summary?.total_gold_gram ?? "0").toFixed(2)} g</p>
                </div>
              )}
              {silverTotal > 0 && (
                <div className="text-right">
                  <p className="text-xs text-gray-400 mb-1">{t("content.commodities.silver")}</p>
                  <p className="text-lg font-semibold text-gray-600">{fmtTL(silverTotal)} ₺</p>
                  <p className="text-xs text-gray-400">{Number.parseFloat(summary?.total_silver_gram ?? "0").toFixed(2)} g</p>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={handleExport} className={TOOLBAR_BTN_CLS}>
                  {t("form.excelDownload")}
                </button>
                <button
                  onClick={() => importRef.current?.click()}
                  disabled={importing}
                  className={TOOLBAR_BTN_CLS}
                >
                  {importing ? t("form.refreshing") : t("form.excelUpload")}
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
              <span>{t("content.commodities.goldRate")} <span className="text-gray-600 font-medium">{t("content.commodities.pricePerGram").replace("{price}", fmtTL(goldPrice))}</span></span>
              {silverPrice !== null && silverPrice > 0 && (
                <span>{t("content.commodities.silverRate")} <span className="text-gray-600 font-medium">{t("content.commodities.pricePerGram").replace("{price}", fmtTL(silverPrice))}</span></span>
              )}
              <span className="ml-auto">{t("content.commodities.priceSource")}</span>
            </div>
          )}
        </div>

        <CommodityForm onAdded={live.refresh} />

        {(error || live.error) && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error || live.error}</p>}
        {loading && <p className="text-sm text-gray-400 text-center py-4">{t("common.loading")}</p>}
        {!loading && summary && <CommodityList positions={summary.positions} onDeleted={live.refresh} />}
      </main>
    </div>
  );
}
