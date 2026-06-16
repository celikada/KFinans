"use client";
import { SubscriptionDTO } from "@/lib/api";
import { fmtCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryMeta } from "./subscriptionMeta";

interface Props {
  readonly items: SubscriptionDTO[];
  /** Satıra tıklayınca Abonelikler sekmesine geçer (düzenleme orada). */
  readonly onGoToSubscriptions: () => void;
}

/**
 * Periyodik (planlı) sekmesinde aktif abonelikleri salt-okunur listeler —
 * planlı giderler gibi aylık tahmin görünümü. Düzenleme/silme YOK; satıra
 * tıklayınca Abonelikler sekmesine geçilir. Toplamları etkilemez (yalnız liste).
 */
export function SubscriptionsAsPlanned({ items, onGoToSubscriptions }: Props) {
  const { t } = useTranslation();
  const active = items.filter((s) => s.active);
  if (active.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50">
        <h3 className="text-sm font-semibold text-gray-700">{t("content.subscriptions.asPlannedTitle")}</h3>
      </div>
      <ul className="divide-y divide-gray-50">
        {active.map((sub) => {
          const meta = categoryMeta(sub.category);
          return (
            <li key={sub.id}>
              <button
                type="button"
                onClick={onGoToSubscriptions}
                className="w-full px-6 py-3 flex items-center justify-between gap-4 text-left hover:bg-gray-50 transition-colors focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className={`flex items-center justify-center w-8 h-8 rounded-lg border text-base shrink-0 ${meta.badgeCls}`}
                    aria-hidden="true"
                  >
                    {meta.icon}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {sub.label || sub.provider_name}
                      </span>
                      <span className="text-[10px] font-medium text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded shrink-0">
                        🔁 {t("content.subscriptions.asPlannedBadge")}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 truncate">{sub.provider_name}</p>
                  </div>
                </div>
                <span className="text-sm font-semibold text-gray-700 shrink-0">
                  {fmtCurrency(sub.budget_amount, sub.currency)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
