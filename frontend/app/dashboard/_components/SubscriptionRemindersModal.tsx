"use client";
/**
 * Girişte (dashboard) abonelik hatırlatma popup'ı:
 *  1. Fatura girilmesi gereken dönemler (pending_bills) → "Fatura gir".
 *  2. Son ödeme tarihi yaklaşan/geçmiş, ödenmemiş faturalar (due_payments) →
 *     tutar + tarih + opsiyonel "Google Takvim'e ekle".
 *
 * Her iki aksiyon da kullanıcıyı /dashboard/expenses?tab=abonelikler'e yönlendirir
 * (ödeme/fatura işlemi orada yapılır). A11Y: native <dialog> tabanlı Modal.
 */
import { useRouter } from "next/navigation";

import { SubscriptionRemindersDTO, SubscriptionDuePaymentDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { fmtCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";

const SUBS_TAB_HREF = "/dashboard/expenses?tab=abonelikler";

/** YYYY-MM-DD → YYYYMMDD (Google Calendar all-day format). */
function ymd(d: string): string {
  return d.replaceAll("-", "");
}

/** Verilen ISO tarihin ertesi günü (all-day etkinlik bitişi, end-exclusive). */
function nextDayYmd(d: string): string {
  const dt = new Date(`${d}T00:00:00`);
  dt.setDate(dt.getDate() + 1);
  return `${dt.getFullYear()}${String(dt.getMonth() + 1).padStart(2, "0")}${String(dt.getDate()).padStart(2, "0")}`;
}

/** OAuth'suz Google Takvim "etkinlik ekle" linki. */
function googleCalendarUrl(item: SubscriptionDuePaymentDTO, title: string, details: string): string {
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${ymd(item.due_date)}/${nextDayYmd(item.due_date)}`,
    details,
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function SubscriptionRemindersModal({
  data,
  onClose,
}: {
  readonly data: SubscriptionRemindersDTO;
  readonly onClose: () => void;
}) {
  const { t } = useTranslation();
  const router = useRouter();
  const { due_payments: duePayments, pending_bills: pendingBills } = data;

  function openSubs() {
    onClose();
    router.push(SUBS_TAB_HREF);
  }

  return (
    <Modal open onClose={onClose} labelledById="sub-reminders-title" describedById="sub-reminders-desc">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default">
        <h3 id="sub-reminders-title" className="text-base font-semibold text-gray-900 mb-1">
          {t("content.subReminders.title")}
        </h3>
        <p id="sub-reminders-desc" className="text-xs text-gray-600 mb-4">
          {t("content.subReminders.desc")}
        </p>

        {/* 1) Fatura girilecek dönemler */}
        {pendingBills.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              {t("content.subReminders.pendingSection")}
            </p>
            <ul className="space-y-2">
              {pendingBills.map((p) => (
                <li
                  key={`pb-${p.subscription_id}-${p.period_year}-${p.period_month}`}
                  className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 flex items-center justify-between gap-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {p.label || p.provider_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {t(`months.${p.period_month}`)} {p.period_year}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={openSubs}
                    className="text-xs px-2.5 py-1 rounded bg-amber-600 text-white hover:bg-amber-700 shrink-0"
                  >
                    {t("content.subReminders.enterBillBtn")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 2) Ödemesi yaklaşan / geçmiş faturalar */}
        {duePayments.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              {t("content.subReminders.dueSection")}
            </p>
            <ul className="space-y-2">
              {duePayments.map((d) => {
                const overdue = d.days_until_due < 0;
                const today = d.days_until_due === 0;
                const name = d.label || d.provider_name;
                const calTitle = `KFinans: ${name} ${t("content.subReminders.calTitleSuffix")}`;
                const calDetails = `${t("content.subReminders.calDetailsDue")}: ${d.due_date} · ${t("content.subReminders.calDetailsAmount")}: ${fmtCurrency(d.bill_amount, d.currency)}`;
                let dueLabel: string;
                let dueColor: string;
                if (overdue) {
                  dueLabel = t("content.subReminders.overdue").replace("{n}", String(-d.days_until_due));
                  dueColor = "text-red-600 font-medium";
                } else if (today) {
                  dueLabel = t("content.subReminders.dueToday");
                  dueColor = "text-amber-600 font-medium";
                } else {
                  dueLabel = t("content.subReminders.dueInDays").replace("{n}", String(d.days_until_due));
                  dueColor = "text-gray-500";
                }
                return (
                  <li key={`dp-${d.bill_id}`} className={`rounded-lg border px-3 py-2 ${overdue ? "border-red-100 bg-red-50" : "border-gray-100"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{name}</p>
                        <p className="text-xs text-gray-500">
                          {t("content.subReminders.dueDate")}: {d.due_date}
                          {" · "}
                          <span className={dueColor}>{dueLabel}</span>
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-gray-900 tabular-nums shrink-0">
                        {fmtCurrency(d.bill_amount, d.currency)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <button
                        type="button"
                        onClick={openSubs}
                        className="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700"
                      >
                        {t("content.subReminders.payBtn")}
                      </button>
                      <a
                        href={googleCalendarUrl(d, calTitle, calDetails)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        📅 {t("content.subReminders.addToCalendar")}
                      </a>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            {t("content.subReminders.close")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
