"use client";
/**
 * Girişte (dashboard) kredi kartı hatırlatma popup'ı:
 *  1. Hesap kesim tarihi geçmiş ama ekstresi yüklenmemiş kartlar → "Ekstre yükle".
 *  2. Son ödeme tarihi yaklaşan/geçmiş, ödenmemiş ekstreler → tutar + tarih +
 *     opsiyonel "Google Takvim'e ekle" (OAuth'suz, ön-doldurulmuş etkinlik linki).
 *
 * A11Y: native <dialog> tabanlı Modal primitifi.
 */
import { useRouter } from "next/navigation";

import { CreditCardRemindersDTO, DuePaymentItemDTO } from "@/lib/api";
import { Modal } from "@/app/_components/Modal";
import { fmtTL } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

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

/** OAuth'suz Google Takvim "etkinlik ekle" linki (kullanıcı tıklar, kaydeder). */
function googleCalendarUrl(item: DuePaymentItemDTO, title: string, details: string): string {
  const start = ymd(item.due_date);
  const end = nextDayYmd(item.due_date);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${start}/${end}`,
    details,
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function CreditCardRemindersModal({
  data,
  onClose,
}: {
  readonly data: CreditCardRemindersDTO;
  readonly onClose: () => void;
}) {
  const { t } = useTranslation();
  const router = useRouter();

  function openCard(cardId: number) {
    onClose();
    router.push(`/dashboard/credit-cards/${cardId}`);
  }

  return (
    <Modal open onClose={onClose} labelledById="cc-reminders-title" describedById="cc-reminders-desc">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default">
        <h3 id="cc-reminders-title" className="text-base font-semibold text-gray-900 mb-1">
          {t("content.ccReminders.title")}
        </h3>
        <p id="cc-reminders-desc" className="text-xs text-gray-600 mb-4">
          {t("content.ccReminders.desc")}
        </p>

        {/* 1) Ekstresi yüklenmemiş kartlar */}
        {data.pending_statements.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              {t("content.ccReminders.uploadSection")}
            </p>
            <ul className="space-y-2">
              {data.pending_statements.map((p) => (
                <li key={`ps-${p.card_id}`} className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {p.name}
                      {p.last_4 && <span className="text-gray-400"> ···{p.last_4}</span>}
                    </p>
                    <p className="text-xs text-gray-500">
                      {t(`months.${p.period_month}`)} {p.period_year} · {t("content.ccReminders.cutoff")}: {p.cutoff_date}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => openCard(p.card_id)}
                    className="text-xs px-2.5 py-1 rounded bg-amber-600 text-white hover:bg-amber-700 shrink-0"
                  >
                    {t("content.ccReminders.uploadBtn")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 2) Ödemesi yaklaşan / geçmiş ekstreler */}
        {data.due_payments.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              {t("content.ccReminders.dueSection")}
            </p>
            <ul className="space-y-2">
              {data.due_payments.map((d) => {
                const overdue = d.days_until_due < 0;
                const today = d.days_until_due === 0;
                const calTitle = `KFinans: ${d.card_name} ${t("content.ccReminders.calTitleSuffix")}`;
                const calDetails = `${t("content.ccReminders.calDetailsDue")}: ${d.due_date} · ${t("content.ccReminders.calDetailsAmount")}: ${fmtTL(Number.parseFloat(d.statement_amount))} ₺`;
                // Gecikme/yaklaşma metni + rengi (nested ternary yerine düz hesap — S3358)
                let dueLabel: string;
                let dueColor: string;
                if (overdue) {
                  dueLabel = t("content.ccReminders.overdue").replace("{n}", String(-d.days_until_due));
                  dueColor = "text-red-600 font-medium";
                } else if (today) {
                  dueLabel = t("content.ccReminders.dueToday");
                  dueColor = "text-amber-600 font-medium";
                } else {
                  dueLabel = t("content.ccReminders.dueInDays").replace("{n}", String(d.days_until_due));
                  dueColor = "text-gray-500";
                }
                return (
                  <li key={`dp-${d.statement_id}`} className={`rounded-lg border px-3 py-2 ${overdue ? "border-red-100 bg-red-50" : "border-gray-100"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{d.card_name}</p>
                        <p className="text-xs text-gray-500">
                          {t("content.ccReminders.dueDate")}: {d.due_date}
                          {" · "}
                          <span className={dueColor}>{dueLabel}</span>
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-gray-900 tabular-nums shrink-0">
                        {fmtTL(Number.parseFloat(d.statement_amount))} ₺
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <a
                        href={googleCalendarUrl(d, calTitle, calDetails)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        📅 {t("content.ccReminders.addToCalendar")}
                      </a>
                      <button
                        type="button"
                        onClick={() => openCard(d.card_id)}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        {t("content.ccReminders.openCard")}
                      </button>
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
            {t("content.ccReminders.close")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
