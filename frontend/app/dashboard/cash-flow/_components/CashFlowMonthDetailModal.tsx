"use client";
/**
 * Bir ayın nakit akışı dökümü — o ayın gelir/gider TOPLAMINI oluşturan kalemleri
 * tek tek listeler (gerçekleşen + tahmini). Nakit akışı tablosunda/grafiğinde bir
 * aya tıklanınca açılır.
 *
 * Kalemler kendi para biriminde gösterilir; toplamlar görüntüleme para biriminde
 * (Money pattern). Kredi kartı taksitleri "kalan/toplam + ilk vade" bilgisiyle
 * gelir — taksit projeksiyonunu şeffaf kılar.
 */
import { useEffect, useState } from "react";

import { api, CashFlowItemDTO, CashFlowMonthDetailDTO, CurrencyType } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { formatTlAs, useRates, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";

// İçerik-bazlı satır anahtarı (array index kullanmadan — S6479). Kalemler statik
// ve yeniden sıralanmadığı için bu bileşik anahtar yeterince benzersiz.
function itemKey(prefix: string, it: CashFlowItemDTO): string {
  return `${prefix}-${it.kind}-${it.category}-${it.label}-${it.date ?? ""}-${it.amount_tl}`;
}

function ItemRow({
  item,
  displayCurrency,
  rates,
  t,
}: {
  readonly item: CashFlowItemDTO;
  readonly displayCurrency: CurrencyType;
  readonly rates: Record<string, number> | null;
  readonly t: (k: string) => string;
}) {
  const tl = Number.parseFloat(item.amount_tl);
  const isIncome = item.category === "income" || item.category === "recurring_income";
  const amountColor = isIncome ? "text-emerald-600" : "text-rose-600";
  const ownAmount = `${item.amount} ${item.currency}`;
  const showOwn = item.currency !== "TRY";
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-2.5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm text-gray-800">{item.label}</span>
          <span
            className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
              item.kind === "actual" ? "bg-gray-100 text-gray-500" : "bg-amber-50 text-amber-600"
            }`}
          >
            {item.kind === "actual" ? t("content.cashFlow.detail.actual") : t("content.cashFlow.detail.forecast")}
          </span>
        </div>
        {item.sub_label && <p className="mt-0.5 truncate text-xs text-gray-400">{item.sub_label}</p>}
      </div>
      <div className="shrink-0 text-right">
        <span className={`text-sm font-semibold tabular-nums ${amountColor}`}>{formatTlAs(tl, displayCurrency, rates)}</span>
        {showOwn && <p className="text-[11px] text-gray-400 tabular-nums">{ownAmount}</p>}
      </div>
    </div>
  );
}

export function CashFlowMonthDetailModal({
  year,
  month,
  monthName,
  onClose,
}: {
  readonly year: number;
  readonly month: number;
  readonly monthName: string;
  readonly onClose: () => void;
}) {
  const { t } = useTranslation();
  const rates = useRates();
  const displayCurrency = useDisplayCurrency();
  const [data, setData] = useState<CashFlowMonthDetailDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .getCashFlowMonthDetail(year, month)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : t("content.cashFlow.loadFailed"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [year, month, t]);

  const titleId = "cf-detail-title";
  const incomeTotal = data ? Number.parseFloat(data.income_total) : 0;
  const expenseTotal = data ? Number.parseFloat(data.expense_total) : 0;
  const net = data ? Number.parseFloat(data.net) : 0;

  return (
    <Modal open onClose={onClose} labelledById={titleId}>
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h3 id={titleId} className="text-sm font-semibold text-gray-800">
          {monthName} {year} · {t("content.cashFlow.detail.title")}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
          className="rounded p-1 text-gray-400 hover:text-gray-700 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>

      <div className="max-h-[70vh] overflow-y-auto">
        {loading && <p className="px-4 py-8 text-center text-sm text-gray-400">{t("common.loading")}</p>}
        {error && <p className="m-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-500">{error}</p>}

        {!loading && !error && data && (
          <>
            {/* Gelirler */}
            <section>
              <div className="flex items-center justify-between bg-emerald-50/60 px-4 py-2">
                <span className="text-xs font-semibold tracking-wide text-emerald-700 uppercase">
                  {t("content.cashFlow.income")}
                </span>
                <span className="text-sm font-bold text-emerald-700 tabular-nums">{formatTlAs(incomeTotal, displayCurrency, rates)}</span>
              </div>
              {data.income_items.length === 0 ? (
                <p className="px-4 py-3 text-xs text-gray-400">{t("content.cashFlow.detail.noIncome")}</p>
              ) : (
                <div className="divide-y divide-gray-50">
                  {data.income_items.map((it) => (
                    <ItemRow key={itemKey("inc", it)} item={it} displayCurrency={displayCurrency} rates={rates} t={t} />
                  ))}
                </div>
              )}
            </section>

            {/* Giderler */}
            <section className="border-t border-gray-100">
              <div className="flex items-center justify-between bg-rose-50/60 px-4 py-2">
                <span className="text-xs font-semibold tracking-wide text-rose-700 uppercase">
                  {t("content.cashFlow.expense")}
                </span>
                <span className="text-sm font-bold text-rose-700 tabular-nums">{formatTlAs(expenseTotal, displayCurrency, rates)}</span>
              </div>
              {data.expense_items.length === 0 ? (
                <p className="px-4 py-3 text-xs text-gray-400">{t("content.cashFlow.detail.noExpense")}</p>
              ) : (
                <div className="divide-y divide-gray-50">
                  {data.expense_items.map((it) => (
                    <ItemRow key={itemKey("exp", it)} item={it} displayCurrency={displayCurrency} rates={rates} t={t} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      {/* Net */}
      {!loading && !error && data && (
        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-4 py-3">
          <span className="text-sm font-semibold text-gray-700">{t("table.net")}</span>
          <span className={`text-base font-bold tabular-nums ${net >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
            {net >= 0 ? "+" : ""}
            {formatTlAs(net, displayCurrency, rates)}
          </span>
        </div>
      )}
      </div>
    </Modal>
  );
}
