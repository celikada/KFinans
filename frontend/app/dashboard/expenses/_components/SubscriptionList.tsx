"use client";
import { useState } from "react";

import { api, SubscriptionDTO } from "@/lib/api";
import { fmtCurrency } from "@/app/_components/Money";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryMeta } from "./subscriptionMeta";
import { SubscriptionBillModal } from "./SubscriptionBillModal";
import { SubscriptionPeriodsModal } from "./SubscriptionPeriodsModal";

interface Props {
  readonly items: SubscriptionDTO[];
  readonly onChanged: () => void;
  readonly onDeleted: (id: number) => void;
  readonly onEdit: (sub: SubscriptionDTO) => void;
}

/** Bu-ay durum rozeti (budget / issued / paid). */
function StatusBadge({ sub }: { readonly sub: SubscriptionDTO }) {
  const { t } = useTranslation();
  if (sub.current_status === "paid") {
    return (
      <span className="text-[10px] font-medium text-green-700 bg-green-50 border border-green-100 px-1.5 py-0.5 rounded">
        ✓ {t("content.subscriptions.status.paid")}
      </span>
    );
  }
  if (sub.current_status === "issued") {
    return (
      <span className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-100 px-1.5 py-0.5 rounded">
        {t("content.subscriptions.status.issued")}: {fmtCurrency(sub.current_amount, sub.currency)}
      </span>
    );
  }
  return (
    <span className="text-[10px] font-medium text-gray-500 bg-gray-50 border border-gray-100 px-1.5 py-0.5 rounded">
      {t("content.subscriptions.status.budget")}
    </span>
  );
}

export function SubscriptionList({ items, onChanged, onDeleted, onEdit }: Props) {
  const confirm = useConfirm();
  const { t } = useTranslation();
  // Fatura modal'ı (issue / pay) — satır aksiyonundan açılır.
  const [billFor, setBillFor] = useState<{ sub: SubscriptionDTO; mode: "issue" | "pay"; billId?: number | null } | null>(null);
  // Dönem yönetim modalı.
  const [periodsFor, setPeriodsFor] = useState<SubscriptionDTO | null>(null);

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <p className="text-sm text-gray-400 text-center py-4">{t("content.subscriptions.empty")}</p>
      </div>
    );
  }

  async function handleDelete(sub: SubscriptionDTO) {
    const name = sub.label || sub.provider_name;
    if (!(await confirm(`"${name}" ${t("content.subscriptions.confirmDeleteSuffix")}`, { destructive: true }))) return;
    await api.deleteSubscription(sub.id);
    onDeleted(sub.id);
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50">
        <h3 className="text-sm font-semibold text-gray-700">{t("content.subscriptions.listTitle")}</h3>
      </div>
      <ul className="divide-y divide-gray-50">
        {items.map((sub) => {
          const meta = categoryMeta(sub.category);
          // "Fatura geldi" budget/issued durumda; paid'de gizli.
          const canIssue = sub.current_status === "budget" || sub.current_status === "issued";
          const canPay = sub.current_status === "issued" && sub.current_bill_id != null;
          return (
            <li key={sub.id} className="px-6 py-4 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <span
                  className={`flex items-center justify-center w-9 h-9 rounded-lg border text-lg shrink-0 ${meta.badgeCls}`}
                  aria-hidden="true"
                >
                  {meta.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900 truncate">
                      {sub.label || sub.provider_name}
                    </span>
                    {!sub.active && (
                      <span className="text-[10px] text-gray-400 bg-gray-50 border border-gray-100 px-1.5 py-0.5 rounded">
                        {t("content.subscriptions.inactiveBadge")}
                      </span>
                    )}
                    <StatusBadge sub={sub} />
                  </div>
                  <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-400">
                    <span>{sub.provider_name}</span>
                    <span>·</span>
                    <span>{t("content.subscriptions.subscriberNoShort")}: {sub.subscriber_no}</span>
                    <span>· {t("content.subscriptions.budgetShort")}: {fmtCurrency(sub.budget_amount, sub.currency)}</span>
                    {sub.due_day && <span>· {t("content.subscriptions.dueDayShort")}: {sub.due_day}</span>}
                  </div>
                  {sub.notes && <p className="text-xs text-gray-400 mt-1 italic">{sub.notes}</p>}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <div className="flex items-center gap-1.5">
                  {canPay && (
                    <button
                      type="button"
                      onClick={() => setBillFor({ sub, mode: "pay", billId: sub.current_bill_id })}
                      className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700"
                    >
                      {t("content.subscriptions.payAction")}
                    </button>
                  )}
                  {canIssue && (
                    <button
                      type="button"
                      onClick={() => setBillFor({ sub, mode: "issue" })}
                      className="text-xs px-2 py-1 rounded text-amber-700 border border-amber-200 hover:bg-amber-50"
                    >
                      {t("content.subscriptions.issueAction")}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setPeriodsFor(sub)}
                    className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                  >
                    {t("content.subscriptions.periods.manage")}
                  </button>
                  <button
                    type="button"
                    onClick={() => onEdit(sub)}
                    className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                  >
                    {t("common.edit")}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(sub)}
                  aria-label={`${sub.label || sub.provider_name} ${t("content.subscriptions.deleteAriaSuffix")}`}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors focus-visible:ring-2 focus-visible:ring-red-500 rounded"
                >
                  {t("common.delete")}
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {billFor && (
        <SubscriptionBillModal
          sub={billFor.sub}
          mode={billFor.mode}
          billId={billFor.billId}
          onClose={() => setBillFor(null)}
          onDone={() => {
            setBillFor(null);
            onChanged();
          }}
        />
      )}
      {periodsFor && (
        <SubscriptionPeriodsModal sub={periodsFor} onClose={() => setPeriodsFor(null)} onChanged={onChanged} />
      )}
    </div>
  );
}
