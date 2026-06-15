"use client";
import { useState } from "react";
import {
  api,
  PlannedExpenseDTO,
  PLANNED_CATEGORY_LABELS,
  PLANNED_RECURRENCE_LABELS,
} from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";
import { fmtTL } from "@/lib/format";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { PlannedPeriodsModal } from "./PlannedPeriodsModal";

interface Props {
  readonly items: PlannedExpenseDTO[];
  readonly onDeleted: (id: number) => void;
  readonly onEdit: (pe: PlannedExpenseDTO) => void;
}

export function PlannedList({ items, onDeleted, onEdit }: Props) {
  const confirm = useConfirm();
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  // Dönem yönetim modalı (realize/skip geri alma) — açık olduğu planlı gider
  const [periodsFor, setPeriodsFor] = useState<PlannedExpenseDTO | null>(null);

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <p className="text-sm text-gray-400 text-center py-4">{t("empty.noPlanned")}</p>
      </div>
    );
  }

  async function handleDelete(id: number, title: string) {
    if (!(await confirm(`"${title}" ${t("content.planned.confirmDeleteSuffix")}`))) return;
    await api.deletePlannedExpense(id);
    onDeleted(id);
  }

  async function handleRealizeThisMonth(pe: PlannedExpenseDTO) {
    const now = new Date();
    setBusy(`r-${pe.id}`);
    setMsg("");
    try {
      const r = await api.realizePlannedPeriod(pe.id, now.getFullYear(), now.getMonth() + 1);
      setMsg(
        r.realized > 0
          ? `✓ "${pe.title}" ${t("content.planned.realizedThisMonth")}`
          : `"${pe.title}" ${t("content.planned.alreadyRealized")}`,
      );
    } catch (err) {
      setMsg(err instanceof Error ? err.message : t("content.planned.opFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function handleRealizePast(pe: PlannedExpenseDTO) {
    if (!(await confirm(`"${pe.title}" ${t("content.planned.confirmRealizePast")}`, { destructive: false }))) return;
    setBusy(`rp-${pe.id}`);
    setMsg("");
    try {
      const r = await api.realizePlannedPast(pe.id);
      setMsg(`✓ "${pe.title}": ${r.realized} ${t("content.planned.pastResultPrefix")} ${r.skipped} ${t("content.planned.pastResultSuffix")}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : t("content.planned.opFailed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50">
        <h3 className="text-sm font-semibold text-gray-700">{t("content.planned.listTitle")}</h3>
      </div>
      {msg && (
        <p
          className={`mx-6 mt-3 text-xs px-3 py-2 rounded-lg border ${
            msg.startsWith("✓") ? "bg-emerald-50 border-emerald-100 text-emerald-700" : "bg-red-50 border-red-100 text-red-700"
          }`}
        >
          {msg}
        </p>
      )}
      <ul className="divide-y divide-gray-50">
        {items.map((pe) => (
          <li key={pe.id} className="px-6 py-4 flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-900 truncate">{pe.title}</span>
                {pe.is_estimated && (
                  <span className="text-xs bg-amber-50 text-amber-600 border border-amber-100 px-1.5 py-0.5 rounded">
                    {t("content.planned.estimatedBadge")}
                  </span>
                )}
                {pe.credit_card_id && (
                  <span
                    className="text-[10px] font-medium text-rose-700 bg-rose-50 border border-rose-100 px-1.5 py-0.5 rounded"
                    title={t("content.planned.cardBadgeTitle")}
                  >
                    💳 {t("content.planned.cardBadge")}
                  </span>
                )}
                {pe.is_paid && (
                  <span className="text-[10px] font-medium text-green-700 bg-green-50 border border-green-100 px-1.5 py-0.5 rounded">
                    ✓ {t("content.planned.paidBadge")}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-400">
                <span>{PLANNED_CATEGORY_LABELS[pe.category] ?? pe.category}</span>
                <span>·</span>
                <span>{PLANNED_RECURRENCE_LABELS[pe.recurrence] ?? pe.recurrence}</span>
                {pe.remaining_count && <span>· {pe.remaining_count} {t("content.planned.installments")}</span>}
                {pe.end_date && <span>· {t("content.planned.endLabel")} {pe.end_date}</span>}
                {pe.months && pe.months.length > 0 && (
                  <span>· {t("content.planned.monthsLabel")}: {pe.months.join(", ")}</span>
                )}
              </div>
              {pe.notes && <p className="text-xs text-gray-400 mt-1 italic">{pe.notes}</p>}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {!pe.currency || pe.currency === "TRY" ? (
                <TLValue tl={pe.amount} className="text-sm font-semibold text-gray-900 tabular-nums" usdClassName="block text-[10px] text-gray-400 font-normal mt-0.5 tabular-nums text-right" />
              ) : (
                <span className="text-sm font-semibold text-gray-900 tabular-nums">
                  {fmtTL(pe.amount)} {pe.currency}
                </span>
              )}
              <div className="flex flex-col items-end gap-1">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleRealizeThisMonth(pe)}
                    disabled={busy === `r-${pe.id}`}
                    className="text-xs px-2 py-1 rounded text-rose-700 border border-rose-200 hover:bg-rose-50 disabled:opacity-50"
                    title={t("content.planned.realizeThisMonth")}
                  >
                    {t("content.planned.realizeThisMonth")} ✓
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRealizePast(pe)}
                    disabled={busy === `rp-${pe.id}`}
                    className="text-xs px-2 py-1 rounded text-blue-700 border border-blue-200 hover:bg-blue-50 disabled:opacity-50"
                    title={t("content.planned.realizePast")}
                  >
                    {t("content.planned.realizePast")} ✓
                  </button>
                  <button
                    type="button"
                    onClick={() => setPeriodsFor(pe)}
                    className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                    title={t("content.planned.periods.manage")}
                  >
                    {t("content.planned.periods.manage")}
                  </button>
                  <button
                    type="button"
                    onClick={() => onEdit(pe)}
                    className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                    title={t("common.edit")}
                  >
                    {t("common.edit")}
                  </button>
                </div>
                <button
                  onClick={() => handleDelete(pe.id, pe.title)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors"
                >
                  {t("common.delete")}
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {periodsFor && (
        <PlannedPeriodsModal pe={periodsFor} onClose={() => setPeriodsFor(null)} />
      )}
    </div>
  );
}
