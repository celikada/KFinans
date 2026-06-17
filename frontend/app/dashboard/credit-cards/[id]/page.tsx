"use client";
import { useEffect, useState, useCallback, FormEvent, use } from "react";
import { useRouter } from "next/navigation";
import {
  api, CreditCardDetailDTO, StatementDTO, InstallmentDTO,
  StatementInput, InstallmentInput, CurrencyType, CURRENCIES,
} from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { Money, fmtCurrency } from "@/app/_components/Money";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useConfirm } from "@/app/_components/ConfirmDialog";
import { StatementImport } from "../StatementImport";
import { StatementPayModal } from "../_components/StatementPayModal";

const MONTH_KEYS = [
  "monthJan", "monthFeb", "monthMar", "monthApr", "monthMay", "monthJun",
  "monthJul", "monthAug", "monthSep", "monthOct", "monthNov", "monthDec",
];
const TODAY = new Date().toISOString().slice(0, 10);

export default function CreditCardDetailPage({ params }: Readonly<{ params: Promise<{ id: string }> }>) {
  const router = useRouter();
  const { t } = useTranslation();
  const { id } = use(params);
  const cardId = Number.parseInt(id);

  const [detail, setDetail] = useState<CreditCardDetailDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDetail(await api.getCreditCardDetail(cardId));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : t("content.creditCards.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [cardId, router, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title={t("pages.creditCards")} back="/dashboard/credit-cards" />
        <p className="text-sm text-gray-400 text-center py-12">{t("common.loading")}</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title={t("pages.creditCards")} back="/dashboard/credit-cards" />
        <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl mx-6 my-6">{error}</p>
      </div>
    );
  }
  if (!detail) return null;

  const c = detail.card;
  const limit = c.credit_limit ? Number.parseFloat(c.credit_limit) : null;
  const currentPeriod = Number.parseFloat(c.current_period_debt);
  const unpaid = Number.parseFloat(c.unpaid_statement_total);
  const future = Number.parseFloat(c.future_installment_total);
  const periodDebt = Number.parseFloat(c.period_debt);
  const totalDebt = Number.parseFloat(c.total_debt);
  const utilization = limit ? (totalDebt / limit) * 100 : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={c.name} back="/dashboard/credit-cards" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Üst panel: kart bilgisi + 4 borç metriği */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div>
              <p className="text-xs text-gray-400 mb-1">{t("content.creditCards.bankCard")}</p>
              <p className="text-base font-semibold text-gray-900">{c.bank_name ?? "—"}</p>
              {c.last_4 && <p className="text-xs text-gray-500 font-mono">**** {c.last_4}</p>}
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">{t("table.statementDue")}</p>
              <p className="text-sm text-gray-700">{t("content.creditCards.dayFlow").replace("{statement}", String(c.statement_day)).replace("{due}", String(c.payment_due_day))}</p>
              {limit !== null && (
                <p className="text-xs text-gray-400 mt-1">{t("content.creditCards.limitLabel")}: {fmtCurrency(limit, (c.currency ?? "TRY") as CurrencyType)}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">{t("table.totalDebt")}</p>
              <Money tl={totalDebt} className={`text-2xl font-bold tabular-nums ${totalDebt > 0 ? "text-rose-600" : "text-gray-400"}`} />
              {utilization !== null && limit !== null && limit > 0 && (
                <p className="text-xs text-gray-400 mt-1">{t("content.creditCards.utilization").replace("{pct}", utilization.toFixed(0))}</p>
              )}
            </div>
          </div>
          <div className="border-t border-gray-50 pt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-400">{t("empty.pendingNoStatement")}</p>
              <Money tl={currentPeriod} className="font-semibold text-gray-700 tabular-nums" />
            </div>
            <div>
              <p className="text-xs text-gray-400">{t("table.unpaidStatement")}</p>
              <Money tl={unpaid} className={`font-semibold tabular-nums ${unpaid > 0 ? "text-rose-600" : "text-gray-700"}`} />
              {c.unpaid_statement_count >= 2 && (
                <p className="text-[10px] text-amber-600 mt-0.5">⚠ {t("content.creditCards.recordCount").replace("{count}", String(c.unpaid_statement_count))}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-400">{t("dashboard.currentPeriodDebt")}</p>
              <Money tl={periodDebt} className="font-semibold text-rose-500 tabular-nums" />
            </div>
            <div>
              <p className="text-xs text-gray-400">{t("table.futureInstallment")}</p>
              <Money tl={future} className="font-semibold text-gray-700 tabular-nums" />
            </div>
          </div>
        </div>

        {/* Ekstre (PDF) içe aktarma — elle giriş yerine PDF'ten otomatik doldurma */}
        <StatementImport onSuccess={refresh} />

        {/* Ekstreler */}
        <StatementsSection
          cardId={cardId}
          cardCurrency={c.currency ?? "TRY"}
          items={detail.statements}
          onChange={refresh}
        />

        {/* Taksitler */}
        <InstallmentsSection
          cardId={cardId}
          cardCurrency={c.currency ?? "TRY"}
          items={detail.installments}
          onChange={refresh}
        />
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ekstreler bölümü
// ---------------------------------------------------------------------------
function StatementsSection({ cardId, cardCurrency, items, onChange }: Readonly<{
  cardId: number;
  cardCurrency: CurrencyType;
  items: StatementDTO[];
  onChange: () => void;
}>) {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const now = new Date();
  const [editing, setEditing] = useState<StatementDTO | null>(null);
  const [paying, setPaying] = useState<StatementDTO | null>(null);
  const [year, setYear] = useState(now.getFullYear().toString());
  const [month, setMonth] = useState((now.getMonth() + 1).toString());
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>(cardCurrency);
  const [stmtDate, setStmtDate] = useState(TODAY);
  const [dueDate, setDueDate] = useState(TODAY);
  const [paid, setPaid] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  function reset() {
    setEditing(null);
    setYear(now.getFullYear().toString());
    setMonth((now.getMonth() + 1).toString());
    setAmount(""); setCurrency(cardCurrency); setStmtDate(TODAY); setDueDate(TODAY); setPaid(false); setNotes("");
    setErr("");
  }

  function startEdit(s: StatementDTO) {
    setEditing(s);
    setYear(s.period_year.toString());
    setMonth(s.period_month.toString());
    setAmount(s.statement_amount);
    setCurrency(s.currency ?? cardCurrency);
    setStmtDate(s.statement_date);
    setDueDate(s.due_date);
    setPaid(!!s.paid_at);
    setNotes(s.notes ?? "");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!amount.trim()) { setErr(t("content.creditCards.amountRequired")); return; }
    setSaving(true); setErr("");
    try {
      const payload: StatementInput = {
        period_year: Number.parseInt(year),
        period_month: Number.parseInt(month),
        statement_amount: Number.parseFloat(amount),
        statement_date: stmtDate,
        due_date: dueDate,
        paid_at: paid ? new Date().toISOString() : null,
        notes: notes.trim() || null,
        currency,
      };
      if (editing) {
        await api.updateStatement(cardId, editing.id, payload);
      } else {
        await api.createStatement(cardId, payload);
      }
      reset();
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("content.creditCards.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(s: StatementDTO) {
    const periodLabel = `${s.period_year}-${t("content.creditCards." + MONTH_KEYS[s.period_month - 1])}`;
    if (!(await confirm(t("content.creditCards.deleteStatementConfirm").replace("{period}", periodLabel)))) return;
    try {
      await api.deleteStatement(cardId, s.id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("content.creditCards.deleteFailed"));
    }
  }

  let submitLabel: string;
  if (saving) submitLabel = t("form.saving");
  else if (editing) submitLabel = t("form.update");
  else submitLabel = t("form.add");

  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">{t("content.creditCards.monthlyStatements")}</h2>
        <span className="text-xs text-gray-400">{t("content.creditCards.recordCount").replace("{count}", String(items.length))}</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 pb-4 border-b border-gray-50">
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
          <input type="number" placeholder={t("content.creditCards.yearPlaceholder")} value={year} onChange={(e) => setYear(e.target.value)} min="2020" max="2100" className={INPUT_CLS} />
          <select value={month} onChange={(e) => setMonth(e.target.value)} className={INPUT_CLS}>
            {MONTH_KEYS.map((k, i) => <option key={i + 1} value={i + 1}>{t("content.creditCards." + k)}</option>)}
          </select>
          <input type="number" placeholder={t("content.creditCards.amountTlPlaceholder")} value={amount} onChange={(e) => setAmount(e.target.value)} step="0.01" min="0" className={INPUT_CLS} />
          <select aria-label={t("form.currencyLabel")} value={currency} onChange={(e) => setCurrency(e.target.value as CurrencyType)} className={INPUT_CLS}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="date" value={stmtDate} onChange={(e) => setStmtDate(e.target.value)} className={INPUT_CLS} title={t("content.creditCards.statementDateTitle")} />
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={INPUT_CLS} title={t("content.creditCards.dueDateTitle")} />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-gray-600 inline-flex items-center gap-2">
            <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} className="rounded" />
            {t("content.creditCards.paid")}
          </label>
          <input placeholder={t("content.creditCards.notesPlaceholder")} value={notes} onChange={(e) => setNotes(e.target.value)} className={`flex-1 ${INPUT_CLS}`} maxLength={500} />
        </div>
        {err && <p className="text-xs text-red-500">{err}</p>}
        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="text-sm bg-rose-600 text-white px-4 py-2 rounded-lg hover:bg-rose-700 disabled:opacity-50">{submitLabel}</button>
          {editing && <button type="button" onClick={reset} className="text-sm border border-gray-200 text-gray-600 px-4 py-2 rounded-lg">{t("common.cancel")}</button>}
        </div>
      </form>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">{t("empty.noStatement")}</p>
      ) : (
        <ul className="divide-y divide-gray-50">
          {items.map((s) => {
            const ccy = s.currency ?? cardCurrency;
            const total = Number.parseFloat(s.statement_amount);
            const paidAmt = s.paid_amount == null ? null : Number.parseFloat(s.paid_amount);
            // Kısmi: ödenmiş + tutar ekstre tutarından az. Tam: ödenmiş + eksik değil.
            const isPartial = !!s.paid_at && paidAmt != null && paidAmt < total;
            const isFull = !!s.paid_at && !isPartial;
            return (
              <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">
                    {s.period_year} · {t("content.creditCards." + MONTH_KEYS[s.period_month - 1])}
                    {isFull && <span className="ml-2 text-[10px] font-medium text-green-700 bg-green-50 px-1.5 py-0.5 rounded border border-green-200">{t("content.creditCards.paidBadge")} ✓</span>}
                    {isPartial && (
                      <span className="ml-2 text-[10px] font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                        {t("content.creditCards.pay.partialBadge")
                          .replace("{paid}", fmtCurrency(paidAmt, ccy))
                          .replace("{total}", fmtCurrency(total, ccy))}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">{t("content.creditCards.statementShort")}: {s.statement_date} · {t("content.creditCards.dueShort")}: {s.due_date}</p>
                  {s.notes && <p className="text-xs text-gray-400 mt-0.5">{s.notes}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-rose-600 tabular-nums">{fmtCurrency(total, ccy)}</span>
                  {!s.paid_at && (
                    <button onClick={() => setPaying(s)} className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700">✓ {t("content.creditCards.paid")}</button>
                  )}
                  <button onClick={() => startEdit(s)} className="text-xs text-gray-500 hover:text-gray-800">{t("common.edit")}</button>
                  <button onClick={() => handleDelete(s)} aria-label={t("content.creditCards.deleteStatementAria")} className="text-xs text-red-400 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"><span aria-hidden="true">✕</span></button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {paying && (
        <StatementPayModal
          cardId={cardId}
          statement={paying}
          onClose={() => setPaying(null)}
          onPaid={() => { setPaying(null); onChange(); }}
        />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Taksitler bölümü
// ---------------------------------------------------------------------------
function InstallmentsSection({ cardId, cardCurrency, items, onChange }: Readonly<{
  cardId: number;
  cardCurrency: CurrencyType;
  items: InstallmentDTO[];
  onChange: () => void;
}>) {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [editing, setEditing] = useState<InstallmentDTO | null>(null);
  const [description, setDescription] = useState("");
  const [monthlyAmount, setMonthlyAmount] = useState("");
  const [total, setTotal] = useState("12");
  const [firstDue, setFirstDue] = useState(TODAY);
  const [notes, setNotes] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>(cardCurrency);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  function reset() {
    setEditing(null);
    setDescription(""); setMonthlyAmount(""); setTotal("12");
    setFirstDue(TODAY); setNotes(""); setCurrency(cardCurrency); setErr("");
  }

  function startEdit(i: InstallmentDTO) {
    setEditing(i);
    setDescription(i.description);
    setMonthlyAmount(i.monthly_amount);
    setTotal(i.installments_total.toString());
    setFirstDue(i.first_due_date);
    setNotes(i.notes ?? "");
    setCurrency(i.currency ?? cardCurrency);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) { setErr(t("content.creditCards.descriptionRequired")); return; }
    setSaving(true); setErr("");
    try {
      const payload: InstallmentInput = {
        description: description.trim(),
        monthly_amount: Number.parseFloat(monthlyAmount),
        installments_total: Number.parseInt(total),
        first_due_date: firstDue,
        notes: notes.trim() || null,
        currency,
      };
      if (editing) {
        await api.updateInstallment(cardId, editing.id, payload);
      } else {
        await api.createInstallment(cardId, payload);
      }
      reset();
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("content.creditCards.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  // Toplam tutar canlı hesaplama (form preview)
  const monthlyNum = Number.parseFloat(monthlyAmount);
  const totalCount = Number.parseInt(total) || 0;
  const totalPreview = monthlyNum > 0 && totalCount > 0
    ? (monthlyNum * totalCount).toFixed(2)
    : null;

  async function handleDelete(i: InstallmentDTO) {
    if (!(await confirm(t("content.creditCards.deleteInstallmentConfirm").replace("{name}", i.description)))) return;
    try {
      await api.deleteInstallment(cardId, i.id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("content.creditCards.deleteFailed"));
    }
  }

  let submitLabel: string;
  if (saving) submitLabel = t("form.saving");
  else if (editing) submitLabel = t("form.update");
  else submitLabel = t("form.add");

  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">{t("content.creditCards.installments")}</h2>
        <span className="text-xs text-gray-400">{t("content.creditCards.recordCount").replace("{count}", String(items.length))}</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 pb-4 border-b border-gray-50">
        <input
          required placeholder={t("content.creditCards.installmentDescPlaceholder")} value={description}
          onChange={(e) => setDescription(e.target.value)} maxLength={200}
          className={INPUT_CLS}
        />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <input type="number" placeholder={t("content.creditCards.monthlyInstallmentPlaceholder")} value={monthlyAmount} onChange={(e) => setMonthlyAmount(e.target.value)} step="0.01" min="0.01" className={INPUT_CLS} />
          <select aria-label={t("form.currencyLabel")} value={currency} onChange={(e) => setCurrency(e.target.value as CurrencyType)} className={INPUT_CLS}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="number" placeholder={t("content.creditCards.installmentCountPlaceholder")} value={total} onChange={(e) => setTotal(e.target.value)} min="1" max="120" className={INPUT_CLS} />
          <input type="date" value={firstDue} onChange={(e) => setFirstDue(e.target.value)} className={INPUT_CLS} title={t("content.creditCards.firstDueTitle")} />
        </div>
        {totalPreview && (
          <p className="text-xs text-gray-500">
            {t("content.creditCards.totalLabel")}: <span className="font-semibold text-gray-700">{fmtCurrency(Number(totalPreview), currency)}</span> · {t("content.creditCards.remainingAutoHint")}
          </p>
        )}
        <input
          placeholder={t("content.creditCards.notesPlaceholder")} value={notes} onChange={(e) => setNotes(e.target.value)}
          className={INPUT_CLS} maxLength={500}
        />
        {err && <p className="text-xs text-red-500">{err}</p>}
        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="text-sm bg-rose-600 text-white px-4 py-2 rounded-lg hover:bg-rose-700 disabled:opacity-50">{submitLabel}</button>
          {editing && <button type="button" onClick={reset} className="text-sm border border-gray-200 text-gray-600 px-4 py-2 rounded-lg">{t("common.cancel")}</button>}
        </div>
      </form>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">{t("empty.noInstallment")}</p>
      ) : (
        <ul className="divide-y divide-gray-50">
          {items.map((i) => (
            <li key={i.id} className="py-3 flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{i.description}</p>
                <p className="text-xs text-gray-500">
                  {t("content.creditCards.installmentsRemaining").replace("{remaining}", String(i.installments_remaining)).replace("{total}", String(i.installments_total))} ·
                  {" "}{t("content.creditCards.firstDueLabel")} {i.first_due_date}
                </p>
                {i.notes && <p className="text-xs text-gray-400 mt-0.5">{i.notes}</p>}
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-sm font-semibold text-rose-600 tabular-nums">
                    {fmtCurrency(Number.parseFloat(i.monthly_amount), i.currency ?? cardCurrency)} {t("content.creditCards.perMonth")}
                  </p>
                  <p className="text-[10px] text-gray-400">
                    {t("content.creditCards.totalLabel")}: {fmtCurrency(Number.parseFloat(i.total_amount), i.currency ?? cardCurrency)}
                  </p>
                </div>
                <button onClick={() => startEdit(i)} className="text-xs text-gray-500 hover:text-gray-800">{t("common.edit")}</button>
                <button onClick={() => handleDelete(i)} aria-label={t("content.creditCards.deleteInstallmentAria")} className="text-xs text-red-400 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"><span aria-hidden="true">✕</span></button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
