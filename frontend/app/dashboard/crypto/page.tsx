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

  function toggleProvider(prov: string) {
    setHiddenProviders((prev) => {
      const next = new Set(prev);
      if (next.has(prov)) next.delete(prov);
      else next.add(prov);
      return next;
    });
  }

  useEffect(() => {
    api.getIntegrations().then((data) => {
      const crypto = data.filter((i) => i.provider in PROVIDER_LABELS);
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
    try {
      await api.removeIntegration(prov);
      setIntegrations((prev) => prev.filter((i) => i.provider !== prov));
      setPositions((prev) => prev.filter((p) => p.provider !== prov));
    } finally {
      setRemoving(null);
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
    </div>
  );
}
