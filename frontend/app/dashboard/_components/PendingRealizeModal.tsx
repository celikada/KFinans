"use client";
/**
 * Girişte (dashboard) tarihi geçmiş ama "gerçekleşti / gerçekleşmeyecek" olarak
 * işaretlenmemiş periyodik gelir ve giderler için uyarı popup'ı.
 *
 * Her satır: tanım + dönem + tutar; [Gerçekleşti] (realize → income/expense kaydı)
 * / [Gerçekleşmeyecek] (skip). Aksiyon sonrası satır listeden düşer; liste boşalınca
 * popup kapanır. A11Y: native <dialog> tabanlı Modal primitifi (focus + role native).
 */
import { useState } from "react";

import { api, PendingItemDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { fmtTL } from "@/lib/format";

function itemKey(it: PendingItemDTO): string {
  return `${it.kind}-${it.ref_id}-${it.period_year}-${it.period_month}`;
}

export function PendingRealizeModal({
  items,
  onClose,
}: {
  readonly items: PendingItemDTO[];
  readonly onClose: () => void;
}) {
  const { t } = useTranslation();
  const [pending, setPending] = useState<PendingItemDTO[]>(items);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  function removeItem(it: PendingItemDTO) {
    setPending((prev) => {
      const next = prev.filter((p) => itemKey(p) !== itemKey(it));
      if (next.length === 0) onClose();
      return next;
    });
  }

  async function runAction(it: PendingItemDTO, action: "realize" | "skip") {
    setBusy(itemKey(it));
    setError("");
    try {
      if (action === "skip") {
        await api.skipRecurring(it.kind, it.ref_id, it.period_year, it.period_month);
      } else if (it.kind === "income") {
        await api.realizeRecurringPeriod(it.ref_id, it.period_year, it.period_month);
      } else {
        await api.realizePlannedPeriod(it.ref_id, it.period_year, it.period_month);
      }
      removeItem(it);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.pending.error"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      labelledById="pending-realize-title"
      describedById="pending-realize-desc"
    >
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default">
        <h3 id="pending-realize-title" className="text-base font-semibold text-gray-900 mb-1">
          {t("content.pending.title")} <span className="text-gray-400">· {pending.length}</span>
        </h3>
        <p id="pending-realize-desc" className="text-xs text-gray-600 mb-4">
          {t("content.pending.desc")}
        </p>

        {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg mb-3">{error}</p>}

        <ul className="space-y-2 max-h-80 overflow-y-auto mb-4">
          {pending.map((it) => {
            const isIncome = it.kind === "income";
            const k = itemKey(it);
            return (
              <li key={k} className="rounded-lg border border-gray-100 px-3 py-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    <span className={`text-xs mr-1 ${isIncome ? "text-emerald-600" : "text-rose-600"}`}>
                      {isIncome ? t("content.pending.income") : t("content.pending.expense")}
                    </span>
                    {it.title}
                  </p>
                  <p className="text-xs text-gray-400">
                    {it.occurrence_date} ·{" "}
                    <span className={isIncome ? "text-emerald-600" : "text-rose-600"}>
                      {fmtTL(Number.parseFloat(it.amount))} ₺
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => runAction(it, "realize")}
                    disabled={busy === k}
                    className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {t("content.pending.realized")}
                  </button>
                  <button
                    type="button"
                    onClick={() => runAction(it, "skip")}
                    disabled={busy === k}
                    className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {t("content.pending.skip")}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            {t("content.pending.close")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
