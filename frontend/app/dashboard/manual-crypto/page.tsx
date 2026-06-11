"use client";
import { useEffect, useState, useCallback, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, AssetCatalogItem, LinkedSource, ManualCryptoPositionDTO, ManualCryptoPriceSource, ManualCryptoSummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { TLValue } from "@/app/_components/TLValue";
import { fmtNum, fmtTL, INPUT_CLS, TOOLBAR_BTN_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useConfirm } from "@/app/_components/ConfirmDialog";

const LINKED_SOURCE_BADGE_CLS: Record<LinkedSource, string> = {
  commodity: "bg-amber-100 text-amber-800",
  binance: "bg-yellow-100 text-yellow-800",
  coingecko: "bg-green-100 text-green-800",
  tefas: "bg-blue-100 text-blue-800",
};

function linkedSourceBadgeClass(source: LinkedSource): string {
  return LINKED_SOURCE_BADGE_CLS[source] ?? "bg-blue-100 text-blue-800";
}

const EXCHANGE_VALUES: { value: string; label: string | null }[] = [
  { value: "binancetr", label: "Binance TR" },
  { value: "icrypex", label: "iCrypex" },
  { value: "btcturk", label: "BtcTurk" },
  { value: "paribu", label: "Paribu" },
  { value: "bybit", label: "Bybit" },
  { value: "kucoin", label: "KuCoin" },
  { value: "bitget", label: "Bitget" },
  { value: "other", label: null },
];

export default function ManualCryptoPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const confirm = useConfirm();

  // Exchange options — proper nouns stay constant except "other", which is translated.
  const EXCHANGE_OPTIONS = EXCHANGE_VALUES.map((o) => ({
    value: o.value,
    label: o.label ?? t("content.manualCrypto.exchangeOther"),
  }));

  const PRICE_SOURCE_OPTIONS: { value: ManualCryptoPriceSource; label: string; hint: string }[] = [
    { value: "auto",   label: t("content.manualCrypto.sourceAuto"),   hint: t("content.manualCrypto.sourceAutoHint") },
    { value: "manual", label: t("content.manualCrypto.sourceManual"), hint: t("content.manualCrypto.sourceManualHint") },
    { value: "linked", label: t("content.manualCrypto.sourceLinked"), hint: t("content.manualCrypto.sourceLinkedHint") },
  ];

  const PRICE_SOURCE_LABEL: Record<ManualCryptoPriceSource, string> = {
    auto: t("content.manualCrypto.sourceLabelAuto"),
    manual: t("content.manualCrypto.sourceLabelManual"),
    linked: t("content.manualCrypto.sourceLabelLinked"),
  };

  const LINKED_SOURCE_LABEL: Record<LinkedSource, string> = {
    binance: "Binance",
    coingecko: "CoinGecko",
    tefas: "TEFAS",
    commodity: t("content.manualCrypto.linkedCommodity"),
  };
  const [summary, setSummary] = useState<ManualCryptoSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Düzenleme modu: null → yeni kayıt, sayı → o id'li pozisyonu güncelle
  const [editingId, setEditingId] = useState<number | null>(null);

  // Form state
  const [exchange, setExchange] = useState("binancetr");
  const [label, setLabel] = useState("");
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [priceSource, setPriceSource] = useState<ManualCryptoPriceSource>("auto");
  const [manualPrice, setManualPrice] = useState("");
  const [notes, setNotes] = useState("");

  // Linked: arama kutusu state
  const [linkedQuery, setLinkedQuery] = useState("");
  const [linkedResults, setLinkedResults] = useState<AssetCatalogItem[]>([]);
  const [linkedSelected, setLinkedSelected] = useState<AssetCatalogItem | null>(null);
  const [searching, setSearching] = useState(false);

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
      setError(err instanceof Error ? err.message : t("content.manualCrypto.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [router, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Linked arama — debounced (250ms)
  useEffect(() => {
    if (priceSource !== "linked") {
      setLinkedResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.searchAssetCatalog({ q: linkedQuery, limit: 15 });
        setLinkedResults(res);
      } catch {
        setLinkedResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [linkedQuery, priceSource]);

  function resetForm() {
    setEditingId(null);
    setExchange("binancetr");
    setLabel("");
    setSymbol("");
    setQuantity("");
    setAvgCost("");
    setPriceSource("auto");
    setManualPrice("");
    setLinkedQuery("");
    setLinkedSelected(null);
    setNotes("");
  }

  function startEdit(p: ManualCryptoPositionDTO) {
    setEditingId(p.id);
    setExchange(p.exchange);
    setLabel(p.label ?? "");
    setSymbol(p.symbol);
    setQuantity(p.quantity);
    setAvgCost(p.avg_cost_tl ?? "");
    setPriceSource(p.price_source);
    setManualPrice(p.manual_unit_price_tl ?? "");
    setNotes(p.notes ?? "");
    setLinkedQuery("");
    // linked pozisyonda seçili varlığı yeniden kur (name yoksa id'yi göster).
    if (p.price_source === "linked" && p.linked_source && p.linked_id) {
      setLinkedSelected({ source: p.linked_source, id: p.linked_id, symbol: null, name: p.linked_id });
    } else {
      setLinkedSelected(null);
    }
    setError("");
    // jsdom scrollIntoView'i implemente etmez → opsiyonel cagri.
    formRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!exchange || !symbol.trim() || !quantity.trim()) {
      setError(t("content.manualCrypto.requiredFields"));
      return;
    }
    if (priceSource === "manual" && (!manualPrice.trim() || Number.parseFloat(manualPrice) <= 0)) {
      setError(t("content.manualCrypto.manualPriceRequired"));
      return;
    }
    if (priceSource === "linked" && !linkedSelected) {
      setError(t("content.manualCrypto.linkedRequired"));
      return;
    }
    setSaving(true);
    setError("");
    const payload = {
      exchange,
      label: label.trim() || null,
      symbol: symbol.trim().toUpperCase(),
      quantity: Number.parseFloat(quantity),
      avg_cost_tl: avgCost.trim() ? Number.parseFloat(avgCost) : null,
      price_source: priceSource,
      manual_unit_price_tl: priceSource === "manual" ? Number.parseFloat(manualPrice) : null,
      linked_source: priceSource === "linked" ? linkedSelected!.source : null,
      linked_id: priceSource === "linked" ? linkedSelected!.id : null,
      notes: notes.trim() || null,
    };
    try {
      if (editingId === null) {
        await api.createManualCrypto(payload);
      } else {
        await api.updateManualCrypto(editingId, payload);
      }
      resetForm();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.manualCrypto.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, sym: string) {
    if (!(await confirm(t("content.manualCrypto.confirmDelete").replace("{symbol}", sym)))) return;
    try {
      await api.deleteManualCrypto(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.manualCrypto.deleteFailed"));
    }
  }

  async function handleExport() {
    try {
      await api.exportManualCrypto();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.manualCrypto.exportFailed"));
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
        setError(
          t("content.manualCrypto.importResult")
            .replace("{imported}", String(result.imported))
            .replace("{errorCount}", String(result.errors.length))
            .replace("{errors}", result.errors.slice(0, 3).join("; ")),
        );
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.manualCrypto.importFailed"));
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  const totalTL = summary ? Number.parseFloat(summary.total_value_tl) : 0;
  const positions = summary?.positions ?? [];
  const unknownSymbols = summary?.unknown_symbols ?? [];

  let submitLabel: string;
  if (saving) submitLabel = t("common.saving");
  else if (editingId === null) submitLabel = t("form.add");
  else submitLabel = t("form.update");

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.manualCrypto")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Bilgi banner */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-900">
          <p className="font-medium mb-1">{t("content.manualCrypto.bannerTitle")}</p>
          <p className="text-xs text-blue-700">
            {t("content.manualCrypto.bannerText")}
          </p>
        </div>

        {/* Bilinmeyen sembol uyarısı */}
        {unknownSymbols.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
            <p className="font-medium mb-1">{t("content.manualCrypto.unknownSymbolTitle")}</p>
            <p className="text-xs">
              {(() => {
                const [before, after] = t("content.manualCrypto.unknownSymbolText").split("{symbols}");
                return (
                  <>
                    {before}
                    <strong>{unknownSymbols.join(", ")}</strong>
                    {after}
                  </>
                );
              })()}
            </p>
          </div>
        )}

        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex flex-wrap gap-6 justify-between items-start">
            <div>
              <p className="text-xs text-gray-400 mb-1">{t("content.manualCrypto.totalManualCrypto")}</p>
              <TLValue
                tl={totalTL}
                className="text-3xl font-bold text-gray-900"
                usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums"
              />
              <p className="text-xs text-gray-400 mt-1">
                {t("content.manualCrypto.positionsExchanges")
                  .replace("{positions}", String(positions.length))
                  .replace("{exchanges}", String(new Set(positions.map((p) => p.exchange)).size))}
              </p>
            </div>
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
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleImport}
              />
            </div>
          </div>
        </div>

        {/* Yeni kayıt formu */}
        <form
          ref={formRef}
          onSubmit={handleSubmit}
          className={`bg-white rounded-2xl border shadow-sm p-6 space-y-3 ${
            editingId === null ? "border-gray-100" : "border-blue-300 ring-1 ring-blue-200"
          }`}
        >
          <h2 className="text-sm font-semibold text-gray-700">
            {editingId === null
              ? t("content.manualCrypto.newPositionTitle")
              : t("content.manualCrypto.editPositionTitle")}
          </h2>
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
              placeholder={t("content.manualCrypto.symbolPlaceholder")}
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className={`sm:col-span-1 ${INPUT_CLS}`}
              maxLength={20}
            />
            <input
              type="number"
              placeholder={t("content.manualCrypto.quantityPlaceholder")}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              min="0"
              step="any"
              className={`sm:col-span-1 ${INPUT_CLS}`}
            />
            <input
              type="number"
              placeholder={t("content.manualCrypto.avgCostPlaceholder")}
              value={avgCost}
              onChange={(e) => setAvgCost(e.target.value)}
              min="0"
              step="0.01"
              className={`sm:col-span-2 ${INPUT_CLS}`}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              placeholder={t("content.manualCrypto.labelPlaceholder")}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={INPUT_CLS}
              maxLength={100}
            />
            <input
              placeholder={t("content.manualCrypto.notesPlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={INPUT_CLS}
              maxLength={500}
            />
          </div>

          {/* Fiyat kaynağı seçimi */}
          <div className="space-y-2 pt-2 border-t border-gray-50">
            <label className="text-xs font-medium text-gray-600">{t("content.manualCrypto.priceSource")}</label>
            <div className="grid grid-cols-3 gap-2">
              {PRICE_SOURCE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`cursor-pointer text-xs px-3 py-2 rounded-lg border ${
                    priceSource === opt.value
                      ? "bg-blue-50 border-blue-400 text-blue-900"
                      : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                  title={opt.hint}
                >
                  <input
                    type="radio"
                    className="sr-only"
                    name="price_source"
                    value={opt.value}
                    checked={priceSource === opt.value}
                    onChange={() => setPriceSource(opt.value)}
                  />
                  <p className="font-medium">{opt.label}</p>
                  <p className="text-[10px] text-gray-400 leading-tight mt-0.5">{opt.hint}</p>
                </label>
              ))}
            </div>
            {priceSource === "manual" && (
              <input
                type="number"
                placeholder={t("content.manualCrypto.unitPriceTlPlaceholder")}
                value={manualPrice}
                onChange={(e) => setManualPrice(e.target.value)}
                min="0"
                step="0.000001"
                className={`w-full ${INPUT_CLS}`}
              />
            )}
            {priceSource === "linked" && (
              <div className="space-y-2">
                {linkedSelected ? (
                  <div className="flex items-center gap-2 text-xs bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                    <span className="font-medium text-green-800">
                      ✓ {LINKED_SOURCE_LABEL[linkedSelected.source]}: {linkedSelected.id}
                    </span>
                    <span className="text-green-700">— {linkedSelected.name}</span>
                    <button
                      type="button"
                      onClick={() => { setLinkedSelected(null); setLinkedQuery(""); }}
                      className="ml-auto text-green-600 hover:text-green-800"
                    >
                      {t("content.manualCrypto.change")}
                    </button>
                  </div>
                ) : (
                  <>
                    <input
                      type="text"
                      placeholder={t("content.manualCrypto.linkedSearchPlaceholder")}
                      value={linkedQuery}
                      onChange={(e) => setLinkedQuery(e.target.value)}
                      className={`w-full ${INPUT_CLS}`}
                    />
                    {(searching || linkedResults.length > 0) && (
                      <div className="max-h-60 overflow-y-auto border border-gray-200 rounded-lg divide-y divide-gray-50 bg-white">
                        {searching && (
                          <p className="text-xs text-gray-400 px-3 py-2">{t("content.manualCrypto.searching")}</p>
                        )}
                        {!searching && linkedResults.length === 0 && (
                          <p className="text-xs text-gray-400 px-3 py-2">{t("content.manualCrypto.noResults")}</p>
                        )}
                        {linkedResults.map((r) => (
                          <button
                            key={`${r.source}:${r.id}`}
                            type="button"
                            onClick={() => setLinkedSelected(r)}
                            className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-3"
                          >
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${linkedSourceBadgeClass(r.source)}`}>
                              {LINKED_SOURCE_LABEL[r.source]}
                            </span>
                            <span className="font-medium text-gray-900">{r.symbol || r.id}</span>
                            <span className="text-gray-500 truncate">{r.name}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {submitLabel}
            </button>
            {editingId !== null && (
              <button
                type="button"
                onClick={resetForm}
                disabled={saving}
                className="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 disabled:opacity-50"
              >
                {t("common.cancel")}
              </button>
            )}
          </div>
        </form>

        {/* Liste */}
        {loading && <p className="text-sm text-gray-400 text-center py-4">{t("common.loading")}</p>}
        {!loading && positions.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">{t("empty.noManualCrypto")}</p>
        )}
        {!loading && positions.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">{t("table.exchange")}</th>
                  <th className="px-4 py-3 text-left">{t("table.symbol")}</th>
                  <th className="px-4 py-3 text-right">{t("table.quantity")}</th>
                  <th className="px-4 py-3 text-right">{t("table.livePrice")}</th>
                  <th className="px-4 py-3 text-right">{t("table.tlValue")}</th>
                  <th className="px-4 py-3 text-right">{t("table.gainLoss")}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {positions.map((p) => {
                  const exchangeLabel = EXCHANGE_OPTIONS.find((o) => o.value === p.exchange)?.label ?? p.exchange;
                  const gainLoss = p.gain_loss_tl ? Number.parseFloat(p.gain_loss_tl) : null;
                  const gainPct = p.gain_loss_pct;
                  return (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{exchangeLabel}</p>
                        {p.label && <p className="text-xs text-gray-400">{p.label}</p>}
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 tabular-nums">{p.symbol}</p>
                        {p.price_source !== "auto" && (
                          <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100">
                            {p.price_source === "linked" && p.linked_source && p.linked_id
                              ? `→ ${LINKED_SOURCE_LABEL[p.linked_source]}:${p.linked_id}`
                              : PRICE_SOURCE_LABEL[p.price_source]}
                          </span>
                        )}
                        {p.notes && <p className="text-xs text-gray-400 mt-0.5">{p.notes}</p>}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                        {fmtNum(p.quantity, 8)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 tabular-nums">
                        {Number.parseFloat(p.unit_price_tl) > 0 ? `${fmtTL(p.unit_price_tl)} ₺` : <span className="text-amber-600">—</span>}
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
                        <div className="flex items-center justify-end gap-3">
                          <button
                            onClick={() => startEdit(p)}
                            className="text-gray-400 hover:text-blue-600 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded"
                            title={t("common.edit")}
                            aria-label={t("content.manualCrypto.editAria").replace("{symbol}", p.symbol)}
                          >
                            <span aria-hidden="true">✎</span>
                          </button>
                          <button
                            onClick={() => handleDelete(p.id, p.symbol)}
                            className="text-gray-400 hover:text-red-500 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                            title={t("common.delete")}
                            aria-label={t("content.manualCrypto.deleteAria").replace("{symbol}", p.symbol)}
                          >
                            <span aria-hidden="true">✕</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-gray-400 text-center">
          {t("content.manualCrypto.footerNote")}
        </p>
      </main>
    </div>
  );
}
