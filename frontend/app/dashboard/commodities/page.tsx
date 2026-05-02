"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type CommoditySummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { CommodityForm } from "./_components/CommodityForm";
import { CommodityList } from "./_components/CommodityList";

export default function CommoditiesPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<CommoditySummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  const goldTotal = summary ? parseFloat(summary.total_value_tl) > 0
    ? summary.positions.filter(p => p.metal === "gold").reduce((s, p) => s + parseFloat(p.total_value_tl), 0)
    : 0 : 0;
  const silverTotal = summary ? summary.positions.filter(p => p.metal === "silver").reduce((s, p) => s + parseFloat(p.total_value_tl), 0) : 0;
  const totalTL = summary ? parseFloat(summary.total_value_tl) : 0;
  const goldPrice = summary ? parseFloat(summary.gold_price_tl) : null;
  const silverPrice = summary ? parseFloat(summary.silver_price_tl) : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Altın & Gümüş" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex flex-wrap gap-6 justify-between items-start">
            <div>
              <p className="text-xs text-gray-400 mb-1">Toplam değer</p>
              <p className="text-3xl font-bold text-amber-600">{fmtTL(totalTL)} ₺</p>
              {summary && (
                <p className="text-xs text-gray-400 mt-1">{summary.positions.length} pozisyon</p>
              )}
            </div>
            <div className="flex gap-6">
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
