"use client";
import { useState } from "react";
import { api, IntegrationDTO } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { CryptoProvider } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly hasIntegrations: boolean;
  readonly loadingPositions: boolean;
  readonly onAdded: (added: IntegrationDTO) => void;
  readonly onRefresh: () => void;
}

export function IntegrationForm({ hasIntegrations, loadingPositions, onAdded, onRefresh }: Props) {
  const { t } = useTranslation();
  const [provider, setProvider] = useState<CryptoProvider>("binance");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const isIcrypex = provider === "icrypex";
  const keyLabel = isIcrypex ? t("content.crypto.emailLabel") : t("content.crypto.apiKeyLabel");
  const secretLabel = isIcrypex ? t("content.crypto.passwordLabel") : t("content.crypto.apiSecretLabel");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) { setFormError(t("content.crypto.keyRequired").replace("{label}", keyLabel)); return; }
    if (!apiSecret.trim()) { setFormError(t("content.crypto.keyRequired").replace("{label}", secretLabel)); return; }

    setSaving(true);
    setFormError("");
    try {
      const added = await api.addIntegration(provider, apiKey.trim(), apiSecret.trim() || undefined);
      onAdded(added);
      setApiKey("");
      setApiSecret("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t("content.crypto.addFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-5 space-y-3 border-t border-gray-50 pt-5">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        {t("content.crypto.addExchangeTitle")}
      </h3>
      <div className="flex gap-3 flex-wrap">
        <select
          value={provider}
          onChange={(e) => { setProvider(e.target.value as CryptoProvider); setApiSecret(""); }}
          className={`w-36 ${INPUT_CLS}`}
        >
          <option value="binance">Binance</option>
          <option value="binancetr">Binance TR</option>
          <option value="icrypex">iCrypex</option>
        </select>
        <input
          placeholder={keyLabel}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          className={`flex-1 min-w-0 ${isIcrypex ? "" : "font-mono"} text-xs ${INPUT_CLS}`}
        />
        <input
          placeholder={secretLabel}
          type={isIcrypex ? "password" : "text"}
          value={apiSecret}
          onChange={(e) => setApiSecret(e.target.value)}
          className={`flex-1 min-w-0 ${isIcrypex ? "" : "font-mono"} text-xs ${INPUT_CLS}`}
        />
      </div>
      {formError && (
        <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{formError}</p>
      )}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? t("common.saving") : t("common.save")}
        </button>
        {hasIntegrations && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loadingPositions}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {loadingPositions ? t("form.refreshing") : t("form.refresh")}
          </button>
        )}
      </div>
    </form>
  );
}
