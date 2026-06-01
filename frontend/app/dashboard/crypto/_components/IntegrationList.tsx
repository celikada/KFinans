"use client";
import { IntegrationDTO } from "@/lib/api";
import { PROVIDER_LABELS } from "./constants";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  integrations: IntegrationDTO[];
  removing: string | null;
  onRemove: (provider: string) => void;
}

export function IntegrationList({ integrations, removing, onRemove }: Props) {
  const { t } = useTranslation();
  if (integrations.length === 0) {
    return <p className="text-sm text-gray-400">{t("content.crypto.noExchangeYet")}</p>;
  }

  return (
    <div className="space-y-2">
      {integrations.map((intg) => (
        <div
          key={intg.provider}
          className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg"
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-400" />
            <span className="text-sm font-medium text-gray-800">
              {PROVIDER_LABELS[intg.provider] ?? intg.provider}
            </span>
          </div>
          <button
            onClick={() => onRemove(intg.provider)}
            disabled={removing === intg.provider}
            className="text-xs text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40"
          >
            {removing === intg.provider ? t("content.crypto.removing") : t("content.crypto.remove")}
          </button>
        </div>
      ))}
    </div>
  );
}
