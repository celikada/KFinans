"use client";
import { useState, useEffect } from "react";
import { api, IntegrationDTO, CryptoPositionDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { IntegrationList } from "./_components/IntegrationList";
import { IntegrationForm } from "./_components/IntegrationForm";
import { ProviderSummaryCards } from "./_components/ProviderSummaryCards";
import { PositionsTable } from "./_components/PositionsTable";
import { PROVIDER_LABELS } from "./_components/constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function CryptoPage() {
  const { t } = useTranslation();
  const [integrations, setIntegrations] = useState<IntegrationDTO[]>([]);
  const [positions, setPositions] = useState<CryptoPositionDTO[]>([]);
  const [loadingPositions, setLoadingPositions] = useState(false);
  const [posError, setPosError] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [hiddenProviders, setHiddenProviders] = useState<Set<string>>(new Set());
  // Şifre korumalı API key export + import
  const [showExportPw, setShowExportPw] = useState(false);
  const [exportPw, setExportPw] = useState("");
  const [exportErr, setExportErr] = useState("");
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  function toggleProvider(prov: string) {
    setHiddenProviders((prev) => {
      const next = new Set(prev);
      if (next.has(prov)) next.delete(prov);
      else next.add(prov);
      return next;
    });
  }

  useEffect(() => {
    api
      .getIntegrations()
      .then((data) => {
        const crypto = data.filter((i) => i.provider in PROVIDER_LABELS);
        setIntegrations(crypto);
        if (crypto.length > 0) fetchPositions();
      })
      .catch((err) => {
        // Sessiz hata yerine kullanıcıya göster (yoksa "bağlı borsa yok" sanılır).
        setPosError(err instanceof Error ? err.message : t("content.crypto.positionsLoadFailed"));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchPositions() {
    setLoadingPositions(true);
    setPosError("");
    try {
      const { positions, errors } = await api.getCryptoPositions();
      setPositions(positions.filter((p) => Number.parseFloat(p.total_value_tl) > 0.01));
      if (Object.keys(errors).length > 0) {
        const msgs = Object.entries(errors)
          .map(([prov, err]) => `${PROVIDER_LABELS[prov] ?? prov}: ${err}`)
          .join(" | ");
        setPosError(msgs);
      }
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.crypto.positionsLoadFailed"));
    } finally {
      setLoadingPositions(false);
    }
  }

  function handleAdded(added: IntegrationDTO) {
    setIntegrations((prev) => [...prev.filter((i) => i.provider !== added.provider), added]);
    fetchPositions();
  }

  async function handleRemove(prov: string) {
    setRemoving(prov);
    setPosError("");
    try {
      await api.removeIntegration(prov);
      setIntegrations((prev) => prev.filter((i) => i.provider !== prov));
      setPositions((prev) => prev.filter((p) => p.provider !== prov));
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.crypto.removeFailed"));
    } finally {
      setRemoving(null);
    }
  }

  // "API anahtarlarını indir" → tam (açık) key'ler hassas, şifre sorulur.
  function handleExport() {
    setExportErr("");
    setExportPw("");
    setShowExportPw(true);
  }

  async function submitExport() {
    if (!exportPw) {
      setExportErr(t("content.crypto.exportPasswordRequired"));
      return;
    }
    setExporting(true);
    setExportErr("");
    try {
      await api.exportIntegrationsFull(exportPw);
      setShowExportPw(false);
      setExportPw("");
    } catch (err) {
      setExportErr(err instanceof Error ? err.message : t("content.crypto.exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setPosError("");
    try {
      const imported = await api.importIntegrations(file);
      const crypto = imported.filter((i) => i.provider in PROVIDER_LABELS);
      setIntegrations(crypto);
      if (crypto.length > 0) fetchPositions();
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.crypto.importFailed"));
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  const visiblePositions = positions.filter((p) => !hiddenProviders.has(p.provider));

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.crypto")} />

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.crypto.connectedExchanges")}</h2>
          <IntegrationList
            integrations={integrations}
            removing={removing}
            onRemove={handleRemove}
          />
          <IntegrationForm
            hasIntegrations={integrations.length > 0}
            loadingPositions={loadingPositions}
            onAdded={handleAdded}
            onRefresh={fetchPositions}
          />

          <div className="flex gap-3 mt-4 items-center flex-wrap border-t border-gray-100 pt-4">
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting || integrations.length === 0}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
            >
              {exporting ? t("form.downloading") : t("content.crypto.exportKeys")}
            </button>
            <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
              {importing ? t("form.uploading") : t("content.crypto.importKeys")}
              <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleImport} disabled={importing} />
            </label>
          </div>
        </div>

        {loadingPositions && (
          <p className="text-sm text-gray-400 text-center py-4">
            {t("content.crypto.fetchingBalances")}
          </p>
        )}

        {posError && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{posError}</p>
        )}

        {!loadingPositions && positions.length > 0 && (
          <>
            <ProviderSummaryCards
              positions={positions}
              hidden={hiddenProviders}
              onToggle={toggleProvider}
            />
            <PositionsTable positions={visiblePositions} />
          </>
        )}
      </main>

      {showExportPw && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-50">
          <button
            type="button"
            aria-label={t("common.close")}
            onClick={() => { if (!exporting) setShowExportPw(false); }}
            className="absolute inset-0 bg-black/40 cursor-default"
          />
          <dialog
            open
            aria-modal="true"
            aria-labelledby="intg-export-pw-title"
            className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-sm w-full text-left relative z-10"
          >
            <h3 id="intg-export-pw-title" className="text-base font-semibold text-gray-900 mb-1">
              {t("content.crypto.exportPasswordTitle")}
            </h3>
            <p className="text-xs text-gray-500 mb-4">{t("content.crypto.exportPasswordHint")}</p>
            <form onSubmit={(e) => { e.preventDefault(); submitExport(); }}>
              <input
                type="password"
                autoFocus
                autoComplete="current-password"
                value={exportPw}
                onChange={(e) => setExportPw(e.target.value)}
                placeholder={t("content.crypto.passwordPlaceholder")}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-400"
              />
              {exportErr && (
                <p className="mt-2 text-xs text-red-500 bg-red-50 px-3 py-2 rounded-lg" role="alert">{exportErr}</p>
              )}
              <div className="flex gap-2 justify-end mt-4">
                <button
                  type="button"
                  onClick={() => setShowExportPw(false)}
                  disabled={exporting}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={exporting}
                  className="px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
                >
                  {exporting ? t("form.downloading") : t("content.crypto.exportFullBtn")}
                </button>
              </div>
            </form>
          </dialog>
        </div>
      )}
    </div>
  );
}
