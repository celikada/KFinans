"use client";
import { useState, useEffect } from "react";
import { api, WalletDTO, WalletPositionDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { WalletList } from "./_components/WalletList";
import { WalletForm } from "./_components/WalletForm";
import { WalletPositionsTable } from "./_components/WalletPositionsTable";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function WalletsPage() {
  const { t } = useTranslation();
  const [wallets, setWallets] = useState<WalletDTO[]>([]);
  const [positions, setPositions] = useState<WalletPositionDTO[]>([]);
  const [loadingPositions, setLoadingPositions] = useState(false);
  const [posError, setPosError] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    api.getWallets().then((data) => {
      setWallets(data);
      if (data.length > 0) fetchPositions();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchPositions() {
    setLoadingPositions(true);
    setPosError("");
    try {
      const { positions, errors } = await api.getWalletPositions();
      setPositions(positions.filter((p) => Number.parseFloat(p.total_value_tl) > 0.01));
      if (Object.keys(errors).length > 0) {
        const msgs = Object.entries(errors)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" | ");
        setPosError(msgs);
      }
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.wallets.errorPositions"));
    } finally {
      setLoadingPositions(false);
    }
  }

  function handleAdded(added: WalletDTO) {
    setWallets((prev) => [...prev, added]);
    fetchPositions();
  }

  async function handleExport() {
    setExporting(true);
    try {
      await api.exportWallets();
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.wallets.errorExportFailed"));
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
      const imported = await api.importWallets(file);
      setWallets(imported);
      if (imported.length > 0) fetchPositions();
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.wallets.errorImportFailed"));
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  async function handleRemove(walletId: string) {
    setRemoving(walletId);
    try {
      await api.removeWallet(walletId);
      setWallets((prev) => prev.filter((w) => w.id !== walletId));
      setPositions((prev) => prev.filter((p) => p.wallet_id !== walletId));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.wallets")} />

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.wallets.savedWallets")}</h2>
          <WalletList wallets={wallets} removing={removing} onRemove={handleRemove} />
          <WalletForm
            hasWallets={wallets.length > 0}
            loadingPositions={loadingPositions}
            exporting={exporting}
            importing={importing}
            onAdded={handleAdded}
            onRefresh={fetchPositions}
            onExport={handleExport}
            onImport={handleImport}
          />
        </div>

        {loadingPositions && (
          <p className="text-sm text-gray-400 text-center py-4">
            {t("content.wallets.queryingBalances")}
          </p>
        )}

        {posError && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{posError}</p>
        )}

        {!loadingPositions && positions.length > 0 && (
          <WalletPositionsTable positions={positions} />
        )}
      </main>
    </div>
  );
}
