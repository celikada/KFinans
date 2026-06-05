"use client";
import { useEffect, useState, useCallback, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, CreditCardDTO, CreditCardInput, CreditCardSummaryDTO, CurrencyType, CURRENCIES } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { Money } from "@/app/_components/Money";
import { fmtTL, INPUT_CLS } from "@/lib/format";
import { getDefaultCurrency } from "@/lib/defaultCurrency";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { StatementImport } from "./StatementImport";

export default function CreditCardsPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [summary, setSummary] = useState<CreditCardSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<CreditCardDTO | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [bankName, setBankName] = useState("");
  const [last4, setLast4] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [statementDay, setStatementDay] = useState("1");
  const [paymentDueDay, setPaymentDueDay] = useState("10");
  const [currentDebt, setCurrentDebt] = useState("");
  const [notes, setNotes] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>(getDefaultCurrency());
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.listCreditCards());
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : t("content.creditCards.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [router, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function startEdit(c: CreditCardDTO) {
    setEditing(c);
    setName(c.name);
    setBankName(c.bank_name ?? "");
    setLast4(c.last_4 ?? "");
    setCreditLimit(c.credit_limit ?? "");
    setStatementDay(c.statement_day.toString());
    setPaymentDueDay(c.payment_due_day.toString());
    setCurrentDebt(c.current_period_debt);
    setNotes(c.notes ?? "");
    setCurrency(c.currency ?? getDefaultCurrency());
  }

  function cancelEdit() {
    setEditing(null);
    setName(""); setBankName(""); setLast4("");
    setCreditLimit(""); setStatementDay("1"); setPaymentDueDay("10");
    setCurrentDebt(""); setNotes(""); setCurrency(getDefaultCurrency());
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError(t("content.creditCards.nameRequired"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: CreditCardInput = {
        name: name.trim(),
        bank_name: bankName.trim() || null,
        last_4: last4.trim() || null,
        credit_limit: creditLimit.trim() ? Number.parseFloat(creditLimit) : null,
        statement_day: Number.parseInt(statementDay) || 1,
        payment_due_day: Number.parseInt(paymentDueDay) || 10,
        current_period_debt: currentDebt.trim() ? Number.parseFloat(currentDebt) : 0,
        notes: notes.trim() || null,
        currency,
      };
      if (editing) {
        await api.updateCreditCard(editing.id, payload);
      } else {
        await api.createCreditCard(payload);
      }
      cancelEdit();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.creditCards.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, cardName: string) {
    if (!(await confirm(t("content.creditCards.deleteConfirm").replace("{name}", cardName)))) return;
    try {
      await api.deleteCreditCard(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.creditCards.deleteFailed"));
    }
  }

  const totalDebtAll = summary ? Number.parseFloat(summary.total_debt) : 0;
  const totalPeriodAll = summary ? Number.parseFloat(summary.total_period_debt) : 0;
  const cards = summary?.cards ?? [];
  // Birden fazla ödenmemiş ekstresi olan kartlar (data hijyeni uyarısı)
  const cardsWithMultipleUnpaid = cards.filter((c) => c.unpaid_statement_count >= 2);

  let submitLabel: string;
  if (saving) submitLabel = t("form.saving");
  else if (editing) submitLabel = t("form.update");
  else submitLabel = t("form.add");

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.creditCards")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Birden fazla ödenmemiş ekstre uyarısı */}
        {cardsWithMultipleUnpaid.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
            <p className="font-medium mb-1">⚠ {t("content.creditCards.multiUnpaidTitle").replace("{count}", String(cardsWithMultipleUnpaid.length))}</p>
            <p className="text-xs text-amber-800">
              {t("content.creditCards.multiUnpaidPre")} <strong>{t("content.creditCards.multiUnpaidEmphasis")}</strong>:{" "}
              <strong>{cardsWithMultipleUnpaid.map((c) => `${c.name} (${c.unpaid_statement_count})`).join(", ")}</strong>.{" "}
              {t("content.creditCards.multiUnpaidPost")}
            </p>
          </div>
        )}

        {/* Özet panel: 2 metrik */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("table.totalDebt")}</p>
            <Money tl={totalDebtAll} className="text-3xl font-bold text-rose-600" />
            <p className="text-xs text-gray-400 mt-1">{t("content.creditCards.totalDebtHint").replace("{count}", String(cards.length))}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">{t("dashboard.currentPeriodDebt")}</p>
            <Money tl={totalPeriodAll} className="text-3xl font-bold text-rose-500" />
            <p className="text-xs text-gray-400 mt-1">{t("content.creditCards.periodDebtHint")}</p>
          </div>
        </div>

        {/* Ekstre (PDF) içe aktarma */}
        <StatementImport onSuccess={refresh} />

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3"
        >
          <h3 className="text-sm font-semibold text-gray-700">{editing ? t("content.creditCards.editCard") : t("content.creditCards.newCard")}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              required
              placeholder={t("content.creditCards.cardNamePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`sm:col-span-2 ${INPUT_CLS}`}
              maxLength={100}
            />
            <input
              placeholder={t("content.creditCards.bankNamePlaceholder")}
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              className={INPUT_CLS}
              maxLength={60}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <input
              placeholder={t("content.creditCards.last4Placeholder")}
              value={last4}
              onChange={(e) => setLast4(e.target.value)}
              maxLength={4}
              pattern="\d{4}"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder={t("content.creditCards.limitPlaceholder")}
              value={creditLimit}
              onChange={(e) => setCreditLimit(e.target.value)}
              min="0"
              step="0.01"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder={t("content.creditCards.statementDayPlaceholder")}
              value={statementDay}
              onChange={(e) => setStatementDay(e.target.value)}
              min="1"
              max="28"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder={t("content.creditCards.dueDayPlaceholder")}
              value={paymentDueDay}
              onChange={(e) => setPaymentDueDay(e.target.value)}
              min="1"
              max="28"
              className={INPUT_CLS}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <input
              type="number"
              placeholder={t("content.creditCards.currentDebtPlaceholder")}
              value={currentDebt}
              onChange={(e) => setCurrentDebt(e.target.value)}
              min="0"
              step="0.01"
              className={INPUT_CLS}
            />
            <select
              aria-label={t("form.currencyLabel")}
              value={currency}
              onChange={(e) => setCurrency(e.target.value as CurrencyType)}
              className={INPUT_CLS}
            >
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input
              placeholder={t("content.creditCards.notesPlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={`sm:col-span-2 ${INPUT_CLS}`}
              maxLength={500}
            />
          </div>
          {error && <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-rose-600 text-white text-sm font-medium rounded-lg hover:bg-rose-700 disabled:opacity-50"
            >
              {submitLabel}
            </button>
            {editing && (
              <button
                type="button"
                onClick={cancelEdit}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
              >
                {t("common.cancel")}
              </button>
            )}
          </div>
        </form>

        {/* Liste */}
        {loading && <p className="text-sm text-gray-400 text-center py-4">{t("common.loading")}</p>}
        {!loading && cards.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">{t("content.creditCards.noCards")}</p>
        )}
        {!loading && cards.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">{t("table.card")}</th>
                  <th className="px-4 py-3 text-center">{t("table.statementDue")}</th>
                  <th className="px-4 py-3 text-right">{t("table.periodPending")}</th>
                  <th className="px-4 py-3 text-right">{t("table.unpaidStatement")}</th>
                  <th className="px-4 py-3 text-right">{t("table.futureInstallment")}</th>
                  <th className="px-4 py-3 text-right">{t("table.totalDebt")}</th>
                  <th className="px-4 py-3 text-right">{t("table.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {cards.map((c) => {
                  const currentPeriod = Number.parseFloat(c.current_period_debt);
                  const unpaid = Number.parseFloat(c.unpaid_statement_total);
                  const future = Number.parseFloat(c.future_installment_total);
                  const total = Number.parseFloat(c.total_debt);
                  return (
                    <tr key={c.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">
                          {c.name}
                          {c.currency && c.currency !== "TRY" && (
                            <span className="ml-1.5 text-[10px] font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded align-middle">
                              {c.currency}
                            </span>
                          )}
                        </p>
                        {c.bank_name && <p className="text-xs text-gray-500">{c.bank_name}</p>}
                        {c.last_4 && (
                          <p className="text-xs text-gray-400 font-mono">**** {c.last_4}</p>
                        )}
                        {c.notes && <p className="text-xs text-gray-400 mt-0.5">{c.notes}</p>}
                      </td>
                      <td className="px-4 py-3 text-center text-gray-600 text-xs">
                        {t("content.creditCards.statementShort")}: {c.statement_day}.<br />
                        {t("content.creditCards.dueShort")}: {c.payment_due_day}.
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {fmtTL(currentPeriod)} ₺
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span className={unpaid > 0 ? "text-rose-600" : "text-gray-400"}>
                          {fmtTL(unpaid)} ₺
                        </span>
                        {c.unpaid_statement_count >= 2 && (
                          <p className="text-[10px] text-amber-600 mt-0.5">
                            ⚠ {t("content.creditCards.recordCount").replace("{count}", String(c.unpaid_statement_count))}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {fmtTL(future)} ₺
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`font-semibold tabular-nums ${total > 0 ? "text-rose-600" : "text-gray-400"}`}>
                          {fmtTL(total)} ₺
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            type="button"
                            onClick={() => router.push(`/dashboard/credit-cards/${c.id}`)}
                            className="text-xs px-2 py-1 rounded text-rose-700 border border-rose-200 hover:bg-rose-50"
                          >
                            {t("content.creditCards.statementInstallment")}
                          </button>
                          <button
                            type="button"
                            onClick={() => startEdit(c)}
                            className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                          >
                            {t("common.edit")}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(c.id, c.name)}
                            className="text-gray-400 hover:text-red-500 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                            title={t("common.delete")}
                            aria-label={t("content.creditCards.deleteCardAria").replace("{name}", c.name)}
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
      </main>
    </div>
  );
}
