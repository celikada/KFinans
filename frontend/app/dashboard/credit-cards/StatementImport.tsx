"use client";
import { useState, ChangeEvent } from "react";
import { api, CurrencyType, CURRENCIES, ParsedStatementDTO, StatementImportCommitInput } from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { getDefaultCurrency } from "@/lib/defaultCurrency";
import { useTranslation } from "@/app/_i18n/I18nProvider";

/**
 * Kredi kartı ekstresi (PDF) içe aktarma paneli.
 *
 * İki adım: (1) PDF yüklenir → backend parse eder → düzenlenebilir önizleme;
 * (2) kullanıcı kontrol/düzeltir → commit ile kalıcılaştırılır. Tanınmayan banka
 * veya değişen format backend'de 422 döner; mesaj kullanıcıya gösterilir (kayıt yok).
 */
export function StatementImport({ onSuccess }: Readonly<{ onSuccess: () => void }>) {
  const { t } = useTranslation();
  const [parsed, setParsed] = useState<ParsedStatementDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Düzenlenebilir alanlar (preview sonrası doldurulur)
  const [name, setName] = useState("");
  const [bankName, setBankName] = useState("");
  const [last4, setLast4] = useState("");
  const [limit, setLimit] = useState("");
  const [statementDay, setStatementDay] = useState("1");
  const [dueDay, setDueDay] = useState("1");
  const [amount, setAmount] = useState("");
  const [statementDate, setStatementDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState<CurrencyType>(getDefaultCurrency());
  const [installments, setInstallments] = useState<ParsedStatementDTO["installments"]>([]);

  function reset() {
    setParsed(null);
    setError("");
    setName(""); setBankName(""); setLast4(""); setLimit("");
    setStatementDay("1"); setDueDay("1"); setAmount("");
    setStatementDate(""); setDueDate(""); setInstallments([]);
    setCurrency(getDefaultCurrency());
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // aynı dosya tekrar seçilebilsin
    if (!file) return;
    setLoading(true);
    setError("");
    setParsed(null);
    try {
      const p = await api.previewStatementImport(file);
      setParsed(p);
      setName(p.bank_name);
      setBankName(p.bank_name);
      setLast4(p.last_4 ?? "");
      setLimit(p.credit_limit ?? "");
      setStatementDay(String(p.statement_day));
      setDueDay(String(p.payment_due_day));
      setAmount(p.statement_amount);
      setStatementDate(p.statement_date);
      setDueDate(p.due_date);
      setInstallments(p.installments);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.creditCards.import.previewFailed"));
    } finally {
      setLoading(false);
    }
  }

  function removeInstallment(idx: number) {
    setInstallments((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave() {
    if (!parsed) return;
    if (!name.trim()) {
      setError(t("content.creditCards.nameRequired"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: StatementImportCommitInput = {
        target_card_id: parsed.matched_card_id,
        name: name.trim(),
        bank_name: bankName.trim() || null,
        last_4: last4.trim() || null,
        credit_limit: limit.trim() ? Number.parseFloat(limit) : null,
        statement_day: Number.parseInt(statementDay) || 1,
        payment_due_day: Number.parseInt(dueDay) || 1,
        currency,
        statement: {
          period_year: parsed.period_year,
          period_month: parsed.period_month,
          statement_amount: amount,
          statement_date: statementDate,
          due_date: dueDate,
        },
        installments: installments.map((i) => ({
          description: i.description,
          monthly_amount: i.monthly_amount,
          installments_total: i.installments_total,
          first_due_date: i.first_due_date,
        })),
      };
      await api.commitStatementImport(payload);
      reset();
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.creditCards.import.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">{t("content.creditCards.import.title")}</h3>
        <label className="px-3 py-1.5 bg-rose-50 text-rose-700 border border-rose-200 text-sm font-medium rounded-lg cursor-pointer hover:bg-rose-100">
          {loading ? t("content.creditCards.import.uploading") : t("content.creditCards.import.uploadBtn")}
          <input type="file" accept="application/pdf,.pdf" onChange={handleFile} disabled={loading} className="hidden" />
        </label>
      </div>
      <p className="text-xs text-gray-400">{t("content.creditCards.import.hint")}</p>

      {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}

      {parsed && (
        <div className="space-y-4 pt-2 border-t border-gray-100">
          <p className="text-sm font-medium text-gray-700">{t("content.creditCards.import.previewTitle")}</p>

          {/* Kart eşleşme bilgisi */}
          <div className={`text-xs px-3 py-2 rounded-lg ${parsed.matched_card_id ? "bg-blue-50 text-blue-800" : "bg-emerald-50 text-emerald-800"}`}>
            {parsed.matched_card_id ? t("content.creditCards.import.matchedCard") : t("content.creditCards.import.newCard")}
          </div>

          {/* Uyarılar */}
          {parsed.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900 space-y-1">
              {parsed.warnings.map((w) => (
                <p key={w}>⚠ {w}</p>
              ))}
            </div>
          )}

          {/* Kart alanları */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("content.creditCards.import.cardName")} className={`sm:col-span-2 ${INPUT_CLS}`} maxLength={100} />
            <input value={bankName} onChange={(e) => setBankName(e.target.value)} placeholder={t("content.creditCards.import.bank")} className={INPUT_CLS} maxLength={60} />
            <select
              aria-label={t("form.currencyLabel")}
              value={currency}
              onChange={(e) => setCurrency(e.target.value as CurrencyType)}
              className={INPUT_CLS}
            >
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <input value={last4} onChange={(e) => setLast4(e.target.value)} placeholder={t("content.creditCards.import.last4")} maxLength={4} pattern="\d{4}" className={INPUT_CLS} />
            <input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder={t("content.creditCards.import.limit")} min="0" step="0.01" className={INPUT_CLS} />
            <input type="number" value={statementDay} onChange={(e) => setStatementDay(e.target.value)} placeholder={t("content.creditCards.import.statementDay")} min="1" max="28" className={INPUT_CLS} />
            <input type="number" value={dueDay} onChange={(e) => setDueDay(e.target.value)} placeholder={t("content.creditCards.import.dueDay")} min="1" max="28" className={INPUT_CLS} />
          </div>

          {/* Ekstre alanları */}
          <p className="text-xs font-medium text-gray-500">
            {t("content.creditCards.import.statementSection")} — {parsed.period_year}/{String(parsed.period_month).padStart(2, "0")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={t("content.creditCards.import.amount")} min="0" step="0.01" className={INPUT_CLS} />
            <input type="date" value={statementDate} onChange={(e) => setStatementDate(e.target.value)} className={INPUT_CLS} />
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={INPUT_CLS} />
          </div>

          {/* Taksitler */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">
              {t("content.creditCards.import.installments")} ({installments.length})
            </p>
            {installments.length === 0 ? (
              <p className="text-xs text-gray-400">{t("content.creditCards.import.noInstallments")}</p>
            ) : (
              <div className="border border-gray-100 rounded-lg divide-y divide-gray-50">
                {installments.map((inst, idx) => (
                  <div key={`${inst.description}-${inst.first_due_date}-${idx}`} className="flex items-center justify-between px-3 py-2 text-sm">
                    <div>
                      <p className="text-gray-800">{inst.description}</p>
                      <p className="text-xs text-gray-400">
                        {inst.installments_total} × {inst.monthly_amount} ₺ · {inst.first_due_date}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeInstallment(idx)}
                      className="text-gray-400 hover:text-red-500 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                      aria-label={t("content.creditCards.import.removeInstallment").replace("{desc}", inst.description)}
                    >
                      <span aria-hidden="true">✕</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-rose-600 text-white text-sm font-medium rounded-lg hover:bg-rose-700 disabled:opacity-50"
            >
              {saving ? t("form.saving") : t("content.creditCards.import.save")}
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
