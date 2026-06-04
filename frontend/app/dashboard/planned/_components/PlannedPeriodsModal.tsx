"use client";
/**
 * Bir planlı giderin dönemlerini (ay-yıl) gerçekleşme durumuyla listeler ve
 * realize / skip işaretlerini GERİ ALMA imkânı sunar.
 *
 * Kullanıcı geri bildirimi: realize/skip yanlış işaretlenirse düzeltmek çok zordu.
 * Her dönem: pending → [Gerçekleşti]/[Gerçekleşmeyecek]; realized → [Geri al]
 * (expense silinir); skipped → [Geri al] (skip silinir). Aksiyon sonrası liste
 * yeniden çekilir. A11Y: native <dialog> tabanlı Modal primitifi.
 */
import { useEffect, useState } from "react";

import { api, PeriodStatusDTO, PlannedExpenseDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export function PlannedPeriodsModal({
  pe,
  onClose,
  onChanged,
}: {
  readonly pe: PlannedExpenseDTO;
  readonly onClose: () => void;
  readonly onChanged?: () => void;
}) {
  const { t } = useTranslation();
  const [periods, setPeriods] = useState<PeriodStatusDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await api.getPlannedPeriods(pe.id);
      setPeriods(r.periods);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.planned.periods.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pe.id]);

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError("");
    try {
      await fn();
      await load();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.planned.periods.opFailed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal open onClose={onClose} labelledById="planned-periods-title" describedById="planned-periods-desc">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default">
        <h3 id="planned-periods-title" className="text-base font-semibold text-gray-900 mb-1">
          {t("content.planned.periods.title")} · <span className="text-gray-500">{pe.title}</span>
        </h3>
        <p id="planned-periods-desc" className="text-xs text-gray-600 mb-4">
          {t("content.planned.periods.desc")}
        </p>

        {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg mb-3">{error}</p>}

        {loading && <p className="text-sm text-gray-400 text-center py-6">{t("common.loading")}</p>}
        {!loading && periods.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">{t("content.planned.periods.empty")}</p>
        )}
        {!loading && periods.length > 0 && (
          <ul className="space-y-2 max-h-96 overflow-y-auto mb-4">
            {periods.map((p) => {
              const k = `${p.year}-${p.month}`;
              const monthName = t(`months.${p.month}`);
              const periodLabel = `${monthName} ${p.year}`;
              return (
                <li key={k} className="rounded-lg border border-gray-100 px-3 py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{periodLabel}</p>
                    <p className="text-xs">
                      {p.status === "realized" && <span className="text-emerald-600">✓ {t("content.planned.periods.realized")}</span>}
                      {p.status === "skipped" && <span className="text-gray-400">✕ {t("content.planned.periods.skipped")}</span>}
                      {p.status === "pending" && <span className="text-amber-600">• {t("content.planned.periods.pending")}</span>}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {p.status === "pending" && (
                      <>
                        <button
                          type="button"
                          disabled={busy === k}
                          onClick={() => act(k, () => api.realizePlannedPeriod(pe.id, p.year, p.month))}
                          className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          {t("content.planned.periods.markRealized")}
                        </button>
                        <button
                          type="button"
                          disabled={busy === k}
                          onClick={() => act(k, () => api.skipRecurring("expense", pe.id, p.year, p.month))}
                          className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                        >
                          {t("content.planned.periods.markSkipped")}
                        </button>
                      </>
                    )}
                    {p.status === "realized" && (
                      <button
                        type="button"
                        disabled={busy === k}
                        onClick={() => act(k, () => api.unrealizePlannedPeriod(pe.id, p.year, p.month))}
                        className="text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                      >
                        {t("content.planned.periods.undo")}
                      </button>
                    )}
                    {p.status === "skipped" && p.skip_id != null && (
                      <button
                        type="button"
                        disabled={busy === k}
                        onClick={() => act(k, () => api.unskipRecurring(p.skip_id as number))}
                        className="text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                      >
                        {t("content.planned.periods.undo")}
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
    </Modal>
  );
}
