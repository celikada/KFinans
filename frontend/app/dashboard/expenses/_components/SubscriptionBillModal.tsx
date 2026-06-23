"use client";
/**
 * Abonelik fatura modal'ı — iki işlev:
 *  1. "Fatura geldi" (issue): budget/issued dönemde fatura tutarı + tarihleri gir
 *     → POST /bills/issue (budget → issued; aynı dönem varsa günceller).
 *  2. "Ödendi" (pay): ödenmemiş (issued) faturada ödeme şekli seç (Nakit / Kredi Kartı)
 *     → POST /bills/{billId}/pay. Kredi kartı seçilirse kart ZORUNLU.
 *
 * A11Y: native <dialog> tabanlı Modal primitifi.
 */
import { useEffect, useState } from "react";

import {
  api,
  CreditCardDTO,
  SubscriptionDTO,
  SubscriptionPaymentMethod,
} from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

const TODAY = new Date().toISOString().slice(0, 10);

interface Props {
  readonly sub: SubscriptionDTO;
  /**
   * "issue" → fatura gir; "pay" → ödeme al. "pay" için billId zorunlu.
   */
  readonly mode: "issue" | "pay";
  readonly billId?: number | null;
  readonly onClose: () => void;
  readonly onDone: () => void;
}

export function SubscriptionBillModal({ sub, mode, billId, onClose, onDone }: Props) {
  const { t } = useTranslation();
  const now = new Date();

  // issue alanları
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [billAmount, setBillAmount] = useState(sub.budget_amount ?? "");
  const [billDate, setBillDate] = useState(TODAY);
  const [dueDate, setDueDate] = useState(TODAY);
  const [notes, setNotes] = useState("");

  // pay alanları — son kullanılan ödeme şekli/kartı varsayılan ön-seçili gelir
  const [paymentMethod, setPaymentMethod] = useState<SubscriptionPaymentMethod>(
    sub.default_payment_method === "credit_card" ? "credit_card" : "cash",
  );
  const [creditCardId, setCreditCardId] = useState(
    sub.default_credit_card_id != null ? String(sub.default_credit_card_id) : "",
  );
  const [cards, setCards] = useState<CreditCardDTO[]>([]);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode === "pay") {
      api.listCreditCards().then((s) => setCards(s.cards)).catch(() => {});
    }
  }, [mode]);

  async function handleIssue() {
    await api.issueSubscriptionBill(sub.id, {
      period_year: year,
      period_month: month,
      bill_amount: Number.parseFloat(billAmount),
      bill_date: billDate,
      due_date: dueDate,
      notes: notes.trim() || null,
    });
  }

  async function handlePay() {
    if (billId == null) return;
    await api.paySubscriptionBill(sub.id, billId, {
      payment_method: paymentMethod,
      credit_card_id: paymentMethod === "credit_card" ? Number.parseInt(creditCardId) : null,
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "pay" && paymentMethod === "credit_card" && !creditCardId) {
      setError(t("content.subscriptions.bill.cardRequired"));
      return;
    }
    setSaving(true);
    try {
      if (mode === "issue") await handleIssue();
      else await handlePay();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  const titleId = "sub-bill-title";
  const title = mode === "issue"
    ? t("content.subscriptions.bill.issueTitle")
    : t("content.subscriptions.bill.payTitle");

  return (
    <Modal open onClose={onClose} labelledById={titleId}>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-md w-full text-left cursor-default">
        <h3 id={titleId} className="text-base font-semibold text-gray-900 mb-1">
          {title}
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          {sub.provider_name}{sub.label ? ` · ${sub.label}` : ""}
        </p>

        {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg mb-3">{error}</p>}

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "issue" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="sub_bill_year" className="block text-xs text-gray-500 mb-1">
                    {t("content.subscriptions.bill.year")}
                  </label>
                  <input
                    id="sub_bill_year"
                    type="number"
                    className={INPUT_CLS}
                    value={year}
                    onChange={(e) => setYear(Number.parseInt(e.target.value) || now.getFullYear())}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="sub_bill_month" className="block text-xs text-gray-500 mb-1">
                    {t("content.subscriptions.bill.month")}
                  </label>
                  <select
                    id="sub_bill_month"
                    className={INPUT_CLS}
                    value={month}
                    onChange={(e) => setMonth(Number.parseInt(e.target.value))}
                  >
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <option key={m} value={m}>{t(`months.${m}`)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="sub_bill_amount" className="block text-xs text-gray-500 mb-1">
                  {t("content.subscriptions.bill.amount")} ({sub.currency})
                </label>
                <input
                  id="sub_bill_amount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  className={INPUT_CLS}
                  value={billAmount}
                  onChange={(e) => setBillAmount(e.target.value)}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="sub_bill_date" className="block text-xs text-gray-500 mb-1">
                    {t("content.subscriptions.bill.billDate")}
                  </label>
                  <input
                    id="sub_bill_date"
                    type="date"
                    className={INPUT_CLS}
                    value={billDate}
                    onChange={(e) => setBillDate(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="sub_due_date" className="block text-xs text-gray-500 mb-1">
                    {t("content.subscriptions.bill.dueDate")}
                  </label>
                  <input
                    id="sub_due_date"
                    type="date"
                    className={INPUT_CLS}
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <label htmlFor="sub_bill_notes" className="block text-xs text-gray-500 mb-1">{t("form.notes")}</label>
                <input
                  id="sub_bill_notes"
                  className={INPUT_CLS}
                  placeholder={t("form.optional")}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  maxLength={500}
                />
              </div>
            </>
          )}

          {mode === "pay" && (
            <>
              <fieldset>
                <legend className="block text-xs text-gray-500 mb-1">{t("content.subscriptions.bill.paymentMethod")}</legend>
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 text-sm text-gray-700">
                    <input
                      type="radio"
                      name="payment_method"
                      value="cash"
                      checked={paymentMethod === "cash"}
                      onChange={() => setPaymentMethod("cash")}
                    />
                    💵 {t("content.subscriptions.bill.cash")}
                  </label>
                  <label className="flex items-center gap-1.5 text-sm text-gray-700">
                    <input
                      type="radio"
                      name="payment_method"
                      value="credit_card"
                      checked={paymentMethod === "credit_card"}
                      onChange={() => setPaymentMethod("credit_card")}
                    />
                    💳 {t("content.subscriptions.bill.creditCard")}
                  </label>
                </div>
              </fieldset>

              {paymentMethod === "credit_card" && (
                <div>
                  <label htmlFor="sub_pay_card" className="block text-xs text-gray-500 mb-1">
                    {t("content.subscriptions.bill.selectCard")}
                  </label>
                  <select
                    id="sub_pay_card"
                    className={INPUT_CLS}
                    value={creditCardId}
                    onChange={(e) => setCreditCardId(e.target.value)}
                    required
                  >
                    <option value="">{t("content.subscriptions.bill.selectCardPlaceholder")}</option>
                    {cards.map((c) => (
                      <option key={c.id} value={c.id}>
                        💳 {c.name}{c.last_4 ? ` (**** ${c.last_4})` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50"
            >
              {saving ? t("form.saving") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
