"use client";
import { useState, useEffect, useMemo } from "react";
import { api, WalletDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { LivePortfolioBar } from "@/app/_components/LivePortfolioBar";
import { useLivePortfolio } from "@/app/_hooks/useLivePortfolio";
import { WalletList } from "./_components/WalletList";
import { WalletForm } from "./_components/WalletForm";
import { WalletPositionsTable } from "./_components/WalletPositionsTable";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function WalletsPage() {
  const { t } = useTranslation();
  const [wallets, setWallets] = useState<WalletDTO[]>([]);
  const [removing, setRemoving] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [posError, setPosError] = useState("");
  // Tam-adres export: şifre doğrulama modalı
  const [showExportPw, setShowExportPw] = useState(false);
  const [exportPw, setExportPw] = useState("");
  const [exportErr, setExportErr] = useState("");

  // Pozisyon listesi artık sunucu-cache'ten (/portfolio/live) okunur — her
  // açılışta ağır zincir taraması tetiklenmez. Cüzdan ekleme/silme/import sonrası
  // live.refresh() ile arka planda yeniden hesaplanır.
  const live = useLivePortfolio();
  const positions = useMemo(
    () => (live.data?.sections.wallets?.positions ?? []).filter((p) => Number.parseFloat(p.total_value_tl) > 0.01),
    [live.data],
  );
  const loadingPositions = live.loading;

  // Cache section'ındaki kaynak-bazlı hatalar (ör. RPC down) kullanıcıya gösterilir.
  const sectionErrors = useMemo(() => {
    const errs = live.data?.sections.wallets?.errors ?? {};
    const keys = Object.keys(errs);
    if (keys.length === 0) return "";
    return keys.map((k) => `${k}: ${errs[k]}`).join(" | ");
  }, [live.data]);

  // Per-cüzdan hatalar (wallet_id → mesaj) — sorunlu cüzdan satırında ⚠ gösterir.
  const walletErrors = live.data?.sections.wallets?.wallet_errors ?? {};

  useEffect(() => {
    api.getWallets().then(setWallets).catch(() => {});
  }, []);

  function handleAdded(added: WalletDTO) {
    setWallets((prev) => [...prev, added]);
    live.refresh();
  }

  // "Excel indir" → tam adres için şifre sor (xpub sızması koruması).
  function handleExport() {
    setExportErr("");
    setExportPw("");
    setShowExportPw(true);
  }

  async function submitExport() {
    if (!exportPw) {
      setExportErr(t("content.wallets.exportPasswordRequired"));
      return;
    }
    setExporting(true);
    setExportErr("");
    try {
      await api.exportWalletsFull(exportPw);
      setShowExportPw(false);
      setExportPw("");
    } catch (err) {
      // 403 → "Şifre hatalı — tam adres verilmedi." (backend mesajı)
      setExportErr(err instanceof Error ? err.message : t("content.wallets.errorExportFailed"));
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
      if (imported.length > 0) live.refresh();
    } catch (err) {
      setPosError(err instanceof Error ? err.message : t("content.wallets.errorImportFailed"));
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  async function handleRemove(walletId: string) {
    setRemoving(walletId);
    setPosError("");
    try {
      await api.removeWallet(walletId);
      setWallets((prev) => prev.filter((w) => w.id !== walletId));
      // Pozisyon listesi cache'ten geliyor → arka planda yeniden hesaplat.
      live.refresh();
    } catch (err) {
      // Sessiz yutma yok: silme hatası kullanıcıya gösterilir (ör. backend 500/OOM).
      setPosError(err instanceof Error ? err.message : t("content.wallets.errorRemoveFailed"));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.wallets")} />

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div className="flex justify-end">
          <LivePortfolioBar
            refreshedAt={live.data?.refreshed_at ?? null}
            stale={live.data?.stale ?? false}
            refreshing={live.refreshing}
            onRefresh={live.refresh}
          />
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.wallets.savedWallets")}</h2>
          <WalletList
            wallets={wallets}
            removing={removing}
            onRemove={handleRemove}
            walletErrors={walletErrors}
            onRefreshWallet={live.refreshWallet}
            refreshingWalletId={live.refreshingWalletId}
          />
          <WalletForm
            hasWallets={wallets.length > 0}
            loadingPositions={loadingPositions}
            exporting={exporting}
            importing={importing}
            onAdded={handleAdded}
            onRefresh={live.refresh}
            onExport={handleExport}
            onImport={handleImport}
          />
        </div>

        {loadingPositions && (
          <p className="text-sm text-gray-400 text-center py-4">
            {t("content.wallets.queryingBalances")}
          </p>
        )}

        {(posError || live.error || sectionErrors) && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{posError || live.error || sectionErrors}</p>
        )}

        {!loadingPositions && positions.length > 0 && (
          <WalletPositionsTable positions={positions} />
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
            aria-labelledby="export-pw-title"
            className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-sm w-full text-left relative z-10"
          >
            <h3 id="export-pw-title" className="text-base font-semibold text-gray-900 mb-1">
              {t("content.wallets.exportPasswordTitle")}
            </h3>
            <p className="text-xs text-gray-500 mb-4">{t("content.wallets.exportPasswordHint")}</p>
            <form
              onSubmit={(e) => { e.preventDefault(); submitExport(); }}
            >
              <input
                type="password"
                autoFocus
                autoComplete="current-password"
                value={exportPw}
                onChange={(e) => setExportPw(e.target.value)}
                placeholder={t("content.wallets.passwordPlaceholder")}
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
                  {exporting ? t("form.downloading") : t("content.wallets.exportFullBtn")}
                </button>
              </div>
            </form>
          </dialog>
        </div>
      )}
    </div>
  );
}
