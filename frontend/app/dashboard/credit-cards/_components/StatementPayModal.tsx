"use client";
/**
 * Ekstre ödeme modal'ı — tam veya kısmi ödeme.
 *
 *  - "Tam ödeme" (varsayılan): paid_amount = ekstre tutarı.
 *  - "Kısmi ödeme": 0 < tutar ≤ ekstre tutarı; tutar < toplam ise backend kalanı
 *    kartın dönem-içi borcuna ekler (frontend yalnızca çağırır + kullanıcıyı bilgilendirir).
 *
 * POST /credit-cards/{cardId}/statements/{statementId}/pay → güncel StatementDTO.
 * paid_amount > statement_amount → backend 422 → hata gösterilir.
 *
 * A11Y: native <dialog> tabanlı Modal primitifi.
 */
import { useState } from "react";

import { api, CurrencyType, StatementDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { fmtCurrency } from "@/app/_components/Money";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

/**
 * Modal yalnızca bu alanları gerektirir; detay sayfası tam `StatementDTO` geçer,
 * hatırlatma popup'ı `DuePaymentItemDTO`'dan minimal nesne kurar.
 */
export type PayableStatement = Pick<StatementDTO, "id" | "statement_amount"> &
  Partial<Pick<StatementDTO, "currency">>;

interface Props {
  readonly cardId: number;
  readonly statement: PayableStatement;
  readonly onClose: () => void;
  readonly onPaid: (updated: StatementDTO) => void;
}

export function StatementPayModal({ cardId, statement, onClose, onPaid }: Props) {
  const { t } = useTranslation();
  const currency: CurrencyType = statement.currency ?? "TRY";
  const total = Number.parseFloat(statement.statement_amount);
  // 0 (veya geçersiz) tutar: ödenecek borç yok → yine de "ödendi" işaretlemeye izin ver
  // (backend paid_amount ge=0 kabul eder). Tam/kısmi seçimi gizlenir, doğrudan 0 ödenir.
  // Önceki bug: total=0 → paidAmount=0 → validPartial(>0) false → submit hep "geçersiz".
  const isZero = !(total > 0);

  const [mode, setMode] = useState<"full" | "partial">("full");
  const [amount, setAmount] = useState(statement.statement_amount);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const paidAmount = mode === "full" ? total : Number.parseFloat(amount);
  const validFull = mode === "full" && Number.isFinite(total) && total >= 0;
  const validPartial =
    mode === "partial" && Number.isFinite(paidAmount) && paidAmount > 0 && paidAmount <= total;
  const valid = validFull || validPartial;
  const remainder = validPartial && paidAmount < total ? total - paidAmount : 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!valid) {
      setError(t("content.creditCards.pay.amountInvalid"));
      return;
    }
    setSaving(true);
    try {
      const updated = await api.payStatement(cardId, statement.id, {
        paid_amount: paidAmount,
        paid_at: new Date().toISOString(),
      });
      onPaid(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.creditCards.pay.failed"));
    } finally {
      setSaving(false);
    }
  }

  const titleId = "stmt-pay-title";

  return (
    <Modal open onClose={onClose} labelledById={titleId}>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-md w-full text-left cursor-default">
        <h3 id={titleId} className="text-base font-semibold text-gray-900 mb-1">
          {t("content.creditCards.pay.title")}
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          {t("content.creditCards.pay.statementAmount")}:{" "}
          <span className="font-semibold text-gray-700 tabular-nums">
            {fmtCurrency(total, currency)}
          </span>
        </p>

        {error && (
          <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg mb-3">{error}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {isZero ? (
            <p className="text-xs text-amber-700 bg-amber-50 px-3 py-2 rounded-lg">
              {t("content.creditCards.pay.zeroNote")}
            </p>
          ) : (
            <>
              <fieldset className="space-y-2">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name="pay_mode"
                    value="full"
                    checked={mode === "full"}
                    onChange={() => setMode("full")}
                  />
                  {t("content.creditCards.pay.full")}
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name="pay_mode"
                    value="partial"
                    checked={mode === "partial"}
                    onChange={() => setMode("partial")}
                  />
                  {t("content.creditCards.pay.partial")}
                </label>
              </fieldset>

              {mode === "partial" && (
                <div>
                  <label htmlFor="stmt_pay_amount" className="block text-xs text-gray-500 mb-1">
                    {t("content.creditCards.pay.amountLabel")} ({currency})
                  </label>
                  <input
                    id="stmt_pay_amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={statement.statement_amount}
                    className={INPUT_CLS}
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    required
                  />
                  {remainder > 0 && (
                    <p className="text-xs text-amber-600 mt-1.5">
                      {t("content.creditCards.pay.remainderNote").replace(
                        "{amount}",
                        fmtCurrency(remainder, currency),
                      )}
                    </p>
                  )}
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
              {saving ? t("form.saving") : t("content.creditCards.pay.submit")}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
