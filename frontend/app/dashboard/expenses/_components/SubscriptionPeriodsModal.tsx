"use client";
/**
 * Bir aboneliğin dönemlerini (ay-yıl) durumuyla (budget / issued / paid) listeler
 * ve her dönemde uygun aksiyonu sunar:
 *   budget → "Fatura geldi" (issue modal'ını açar)
 *   issued → "Ödendi" (pay modal'ını açar) | "Faturayı sil"
 *   paid   → "Ödemeyi geri al" (unpay)
 *
 * PlannedPeriodsModal deseninin abonelik karşılığı. A11Y: native <dialog> Modal.
 */
import { useEffect, useState } from "react";

import { api, SubscriptionDTO, SubscriptionPeriodDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { fmtCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { SubscriptionBillModal } from "./SubscriptionBillModal";

export function SubscriptionPeriodsModal({
  sub,
  onClose,
  onChanged,
}: {
  readonly sub: SubscriptionDTO;
  readonly onClose: () => void;
  readonly onChanged?: () => void;
}) {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [periods, setPeriods] = useState<SubscriptionPeriodDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  // İç fatura modal'ı (issue / pay) — dönem satırından açılır.
  const [billModal, setBillModal] = useState<{ mode: "issue" | "pay"; billId?: number | null } | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await api.listSubscriptionBills(sub.id);
      setPeriods(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.subscriptions.periods.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub.id]);

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError("");
    try {
      await fn();
      await load();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.subscriptions.periods.opFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteBill(p: SubscriptionPeriodDTO, key: string) {
    if (p.bill_id == null) return;
    if (!(await confirm(t("content.subscriptions.periods.confirmDeleteBill"), { destructive: true }))) return;
    await act(key, () => api.deleteSubscriptionBill(sub.id, p.bill_id as number));
  }

  function statusLabel(status: SubscriptionPeriodDTO["status"]) {
    if (status === "paid") return <span className="text-emerald-600">✓ {t("content.subscriptions.status.paid")}</span>;
    if (status === "issued") return <span className="text-amber-600">• {t("content.subscriptions.status.issued")}</span>;
    return <span className="text-gray-400">○ {t("content.subscriptions.status.budget")}</span>;
  }

  return (
    <Modal open onClose={onClose} labelledById="sub-periods-title" describedById="sub-periods-desc">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default">
        <h3 id="sub-periods-title" className="text-base font-semibold text-gray-900 mb-1">
          {t("content.subscriptions.periods.title")} · <span className="text-gray-500">{sub.provider_name}</span>
        </h3>
        <p id="sub-periods-desc" className="text-xs text-gray-600 mb-4">
          {t("content.subscriptions.periods.desc")}
        </p>

        {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg mb-3">{error}</p>}

        {loading && <p className="text-sm text-gray-400 text-center py-6">{t("common.loading")}</p>}
        {!loading && periods.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">{t("content.subscriptions.periods.empty")}</p>
        )}
        {!loading && periods.length > 0 && (
          <ul className="space-y-2 max-h-96 overflow-y-auto mb-4">
            {periods.map((p) => {
              const k = `${p.period_year}-${p.period_month}`;
              const monthName = t(`months.${p.period_month}`);
              const periodLabel = `${monthName} ${p.period_year}`;
              return (
                <li key={k} className="rounded-lg border border-gray-100 px-3 py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{periodLabel}</p>
                    <p className="text-xs flex items-center gap-2">
                      {statusLabel(p.status)}
                      <span className="text-gray-500 tabular-nums">{fmtCurrency(p.amount, p.currency)}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {p.status === "budget" && (
                      <button
                        type="button"
                        disabled={busy === k}
                        onClick={() => setBillModal({ mode: "issue" })}
                        className="text-xs px-2 py-1 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
                      >
                        {t("content.subscriptions.periods.markIssued")}
                      </button>
                    )}
                    {p.status === "issued" && (
                      <>
                        <button
                          type="button"
                          disabled={busy === k}
                          onClick={() => setBillModal({ mode: "pay", billId: p.bill_id })}
                          className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          {t("content.subscriptions.periods.markPaid")}
                        </button>
                        <button
                          type="button"
                          disabled={busy === k}
                          onClick={() => handleDeleteBill(p, k)}
                          className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                        >
                          {t("content.subscriptions.periods.deleteBill")}
                        </button>
                      </>
                    )}
                    {p.status === "paid" && p.bill_id != null && (
                      <button
                        type="button"
                        disabled={busy === k}
                        onClick={() => act(k, () => api.unpaySubscriptionBill(sub.id, p.bill_id as number))}
                        className="text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                      >
                        {t("content.subscriptions.periods.undoPay")}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            {t("common.close")}
          </button>
        </div>
      </div>

      {billModal && (
        <SubscriptionBillModal
          sub={sub}
          mode={billModal.mode}
          billId={billModal.billId}
          onClose={() => setBillModal(null)}
          onDone={() => {
            setBillModal(null);
            void load();
            onChanged?.();
          }}
        />
      )}
    </Modal>
  );
}
