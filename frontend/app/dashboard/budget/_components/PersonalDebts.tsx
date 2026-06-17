"use client";
import { useEffect, useState, useCallback } from "react";
import { api, CURRENCIES } from "@/lib/api";
import type { PersonalDebtListDTO, DebtKind, CurrencyType } from "@/lib/api";
import { fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { getDefaultCurrency } from "@/lib/defaultCurrency";

export function PersonalDebts() {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const ccy = useDisplayCurrency();
  const [data, setData] = useState<PersonalDebtListDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showSettled, setShowSettled] = useState(false);

  // Form state
  const [counterparty, setCounterparty] = useState("");
  const [kind, setKind] = useState<DebtKind>("debt");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>(getDefaultCurrency());
  const [dueDate, setDueDate] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.listPersonalDebts(showSettled));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [showSettled, t, ccy]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const amt = Number.parseFloat(amount.replace(",", "."));
    if (!counterparty.trim() || !Number.isFinite(amt) || amt <= 0) return;
    setSaving(true);
    setError("");
    try {
      await api.createPersonalDebt({
        counterparty: counterparty.trim(),
        kind,
        amount: amt,
        currency,
        due_date: dueDate || null,
        note: note.trim() || null,
      });
      setCounterparty("");
      setAmount("");
      setDueDate("");
      setNote("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSettle(id: number) {
    await api.settlePersonalDebt(id).catch(() => undefined);
    refresh();
  }

  async function handleDelete(id: number) {
    if (!(await confirm(t("content.budgetV2.debts.confirmDelete"), { destructive: true }))) return;
    await api.deletePersonalDebt(id).catch(() => undefined);
    refresh();
  }

  return (
    <div className="space-y-6">
      {/* Özet */}
      {data && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.debts.totalDebt")}</p>
            <p className="text-xl font-bold text-red-600">{fmtCurrency(Number.parseFloat(data.total_debt_display), ccy)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.debts.totalReceivable")}</p>
            <p className="text-xl font-bold text-emerald-600">{fmtCurrency(Number.parseFloat(data.total_receivable_display), ccy)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("content.budgetV2.debts.netLabel")}</p>
            <p className={`text-xl font-bold ${Number.parseFloat(data.net_display) >= 0 ? "text-gray-900" : "text-red-600"}`}>
              {fmtCurrency(Number.parseFloat(data.net_display), ccy)}
            </p>
          </div>
        </div>
      )}

      {/* Ekleme formu */}
      <form onSubmit={handleAdd} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 grid grid-cols-1 sm:grid-cols-6 gap-3 items-end">
        <div className="sm:col-span-2">
          <label className="block text-xs text-gray-400 mb-1" htmlFor="pd-cp">{t("content.budgetV2.debts.counterparty")}</label>
          <input id="pd-cp" value={counterparty} onChange={(e) => setCounterparty(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" required />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1" htmlFor="pd-kind">{t("content.budgetV2.debts.kind")}</label>
          <select id="pd-kind" value={kind} onChange={(e) => setKind(e.target.value as DebtKind)}
            className="w-full px-2 py-2 border border-gray-200 rounded-lg text-sm">
            <option value="debt">{t("content.budgetV2.debts.debt")}</option>
            <option value="receivable">{t("content.budgetV2.debts.receivable")}</option>
          </select>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-xs text-gray-400 mb-1" htmlFor="pd-amt">{t("content.budgetV2.debts.amount")}</label>
            <input id="pd-amt" type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
              className="w-full px-2 py-2 border border-gray-200 rounded-lg text-sm" required />
          </div>
          <div>
            <span className="block text-xs text-gray-400 mb-1" aria-hidden="true">&nbsp;</span>
            <select id="pd-ccy" aria-label={t("content.budgetV2.debts.amount")} value={currency}
              onChange={(e) => setCurrency(e.target.value as CurrencyType)}
              className="px-2 py-2 border border-gray-200 rounded-lg text-sm">
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1" htmlFor="pd-due">{t("content.budgetV2.debts.dueDate")}</label>
          <input id="pd-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
            className="w-full px-2 py-2 border border-gray-200 rounded-lg text-sm" />
        </div>
        <button type="submit" disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {t("content.budgetV2.debts.add")}
        </button>
      </form>

      {error && <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>}

      <label className="flex items-center gap-2 text-xs text-gray-500">
        <input type="checkbox" checked={showSettled} onChange={(e) => setShowSettled(e.target.checked)} />
        {t("content.budgetV2.debts.showSettled")}
      </label>

      {/* Liste */}
      {loading && <p className="text-sm text-gray-400 text-center py-4">{t("common.loading")}</p>}
      {!loading && data?.items.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-6">{t("content.budgetV2.debts.empty")}</p>
      )}
      {!loading && data && data.items.length > 0 && (
        <div className="space-y-2">
          {data.items.map((d) => (
            <div key={d.id}
              className={`bg-white rounded-xl border border-gray-100 shadow-sm p-3 flex items-center gap-3 ${d.settled_at ? "opacity-50" : ""}`}>
              <span className={`text-xs px-2 py-0.5 rounded-full ${d.kind === "debt" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                {t(`content.budgetV2.debts.${d.kind}`)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-800 truncate">{d.counterparty}</p>
                {(d.note || d.due_date) && (
                  <p className="text-xs text-gray-400 truncate">
                    {d.due_date && <span>{t("content.budgetV2.debts.dueDate")}: {d.due_date}</span>}
                    {d.due_date && d.note && " · "}
                    {d.note}
                  </p>
                )}
              </div>
              <div className="text-right whitespace-nowrap">
                <p className="font-semibold tabular-nums text-gray-900">{fmtCurrency(Number.parseFloat(d.amount), d.currency)}</p>
                {d.currency !== ccy && (
                  <p className="text-[10px] text-gray-400 tabular-nums">≈ {fmtCurrency(Number.parseFloat(d.amount_display), ccy)}</p>
                )}
              </div>
              {!d.settled_at && (
                <button type="button" onClick={() => handleSettle(d.id)}
                  className="text-xs px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200">
                  {t("content.budgetV2.debts.settle")}
                </button>
              )}
              <button type="button" onClick={() => handleDelete(d.id)}
                className="text-gray-300 hover:text-red-500 focus-visible:ring-2 rounded"
                aria-label={`${d.counterparty} ${t("content.budgetV2.debts.delete")}`}>
                <span aria-hidden="true">✕</span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
