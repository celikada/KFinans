"use client";
import { useState, ChangeEvent } from "react";
import { api, BillImportCommitInput, CurrencyType, CURRENCIES, ParsedBillDTO } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryMeta } from "./subscriptionMeta";

/**
 * Abonelik PDF faturası içe aktarma paneli (kredi kartı StatementImport deseni).
 *
 * İki adım: (1) PDF yüklenir → backend parse eder → düzenlenebilir önizleme;
 * (2) kullanıcı kontrol/düzeltir → commit ile issued fatura kaydı oluşur.
 * Görüntü-PDF / tanınmayan kurum / değişen format backend'de 422 döner; mesaj
 * kullanıcıya gösterilir (kayıt yok). matched_subscription_id null ise yeni abonelik.
 */
export function SubscriptionBillImport({ onImported }: Readonly<{ onImported: () => void }>) {
  const { t } = useTranslation();
  const [parsed, setParsed] = useState<ParsedBillDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Düzenlenebilir alanlar (preview sonrası doldurulur)
  const [subscriberNo, setSubscriberNo] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>("TRY");
  const [billDate, setBillDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [periodYear, setPeriodYear] = useState("");
  const [periodMonth, setPeriodMonth] = useState("");
  const [nextBillDate, setNextBillDate] = useState("");
  const [nextDueDate, setNextDueDate] = useState("");

  function reset() {
    setParsed(null);
    setError("");
    setSubscriberNo(""); setAmount(""); setCurrency("TRY");
    setBillDate(""); setDueDate(""); setPeriodYear(""); setPeriodMonth("");
    setNextBillDate(""); setNextDueDate("");
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // aynı dosya tekrar seçilebilsin
    if (!file) return;
    setLoading(true);
    setError("");
    setParsed(null);
    try {
      const p = await api.previewBillImport(file);
      setParsed(p);
      setSubscriberNo(p.subscriber_no);
      setAmount(p.bill_amount);
      setCurrency(p.currency);
      setBillDate(p.bill_date);
      setDueDate(p.due_date);
      setPeriodYear(String(p.period_year));
      setPeriodMonth(String(p.period_month));
      setNextBillDate(p.next_bill_date ?? "");
      setNextDueDate(p.next_due_date ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.subscriptions.import.previewFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!parsed) return;
    if (!subscriberNo.trim()) {
      setError(t("content.subscriptions.import.subscriberRequired"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: BillImportCommitInput = {
        provider_code: parsed.provider_code,
        subscriber_no: subscriberNo.trim(),
        bill_amount: Number.parseFloat(amount),
        currency,
        bill_date: billDate,
        due_date: dueDate,
        period_year: Number.parseInt(periodYear) || parsed.period_year,
        period_month: Number.parseInt(periodMonth) || parsed.period_month,
        next_bill_date: nextBillDate || null,
        next_due_date: nextDueDate || null,
        bill_no: parsed.bill_no ?? null,
        subscription_id: parsed.matched_subscription_id ?? null,
        label: parsed.matched_label ?? null,
      };
      await api.commitBillImport(payload);
      reset();
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.subscriptions.import.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  const matchLabel = parsed?.matched_label || parsed?.provider_name;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">{t("content.subscriptions.import.title")}</h3>
        <label className="px-3 py-1.5 bg-indigo-50 text-indigo-700 border border-indigo-200 text-sm font-medium rounded-lg cursor-pointer hover:bg-indigo-100">
          {loading ? t("content.subscriptions.import.uploading") : t("content.subscriptions.import.uploadBtn")}
          <input type="file" accept="application/pdf,.pdf" onChange={handleFile} disabled={loading} className="hidden" />
        </label>
      </div>
      <p className="text-xs text-gray-400">{t("content.subscriptions.import.hint")}</p>

      {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}

      {parsed && (
        <div className="space-y-4 pt-2 border-t border-gray-100">
          <p className="text-sm font-medium text-gray-700">{t("content.subscriptions.import.previewTitle")}</p>

          {/* Kurum + abonelik eşleşme bilgisi */}
          <div className={`text-xs px-3 py-2 rounded-lg ${parsed.matched_subscription_id ? "bg-blue-50 text-blue-800" : "bg-emerald-50 text-emerald-800"}`}>
            <span aria-hidden="true">{categoryMeta(parsed.category).icon} </span>
            {parsed.matched_subscription_id
              ? `${t("content.subscriptions.import.matchedSubscription")}: ${matchLabel}`
              : `${t("content.subscriptions.import.newSubscription")}: ${parsed.provider_name}`}
          </div>

          {/* Uyarılar */}
          {parsed.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900 space-y-1">
              {parsed.warnings.map((w) => (
                <p key={w}>⚠ {w}</p>
              ))}
            </div>
          )}

          {/* Kurum (salt-okunur) + abone no */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label htmlFor="bill_provider" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.providerLabel")}
              </label>
              <input id="bill_provider" value={parsed.provider_name} readOnly className={`bg-gray-50 ${INPUT_CLS}`} />
            </div>
            <div>
              <label htmlFor="bill_subscriber" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.subscriberNoLabel")}
              </label>
              <input
                id="bill_subscriber"
                value={subscriberNo}
                onChange={(e) => setSubscriberNo(e.target.value)}
                className={INPUT_CLS}
                maxLength={64}
              />
            </div>
          </div>

          {/* Tutar + tarihler */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <label htmlFor="bill_amount" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.import.amount")}
              </label>
              <div className="flex gap-2">
                <input
                  id="bill_amount"
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  min="0"
                  step="0.01"
                  className={`flex-1 min-w-0 ${INPUT_CLS}`}
                />
                <select
                  aria-label={t("form.currencyLabel")}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value as CurrencyType)}
                  className={`w-20 ${INPUT_CLS}`}
                >
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="bill_date" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.import.billDate")}
              </label>
              <input id="bill_date" type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} className={INPUT_CLS} />
            </div>
            <div>
              <label htmlFor="bill_due" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.import.dueDate")}
              </label>
              <input id="bill_due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={INPUT_CLS} />
            </div>
          </div>

          {/* Dönem yıl/ay */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <label htmlFor="bill_year" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.bill.year")}
              </label>
              <input id="bill_year" type="number" value={periodYear} onChange={(e) => setPeriodYear(e.target.value)} min="2000" max="2100" className={INPUT_CLS} />
            </div>
            <div>
              <label htmlFor="bill_month" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.bill.month")}
              </label>
              <input id="bill_month" type="number" value={periodMonth} onChange={(e) => setPeriodMonth(e.target.value)} min="1" max="12" className={INPUT_CLS} />
            </div>
          </div>

          {/* Sonraki dönem (opsiyonel) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label htmlFor="bill_next_bill" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.import.nextBillDate")}
              </label>
              <input id="bill_next_bill" type="date" value={nextBillDate} onChange={(e) => setNextBillDate(e.target.value)} className={INPUT_CLS} />
            </div>
            <div>
              <label htmlFor="bill_next_due" className="block text-xs text-gray-500 mb-1">
                {t("content.subscriptions.import.nextDueDate")}
              </label>
              <input id="bill_next_due" type="date" value={nextDueDate} onChange={(e) => setNextDueDate(e.target.value)} className={INPUT_CLS} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? t("form.saving") : t("content.subscriptions.import.save")}
            </button>
            <button
              type="button"
              onClick={reset}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
