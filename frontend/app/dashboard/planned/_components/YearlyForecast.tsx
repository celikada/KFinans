"use client";
import { ForecastResultDTO, MONTH_NAMES } from "@/lib/api";
import { Money, formatTlAs, useRates, useDisplayCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly data: ForecastResultDTO;
  readonly year: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  loan:         "bg-blue-100 text-blue-700",
  tax:          "bg-red-100 text-red-700",
  insurance:    "bg-purple-100 text-purple-700",
  subscription: "bg-orange-100 text-orange-700",
  rent:         "bg-teal-100 text-teal-700",
  utility:      "bg-yellow-100 text-yellow-700",
  other:        "bg-gray-100 text-gray-600",
};

export function YearlyForecast({ data, year }: Props) {
  const { t } = useTranslation();
  const rates = useRates();
  const displayCurrency = useDisplayCurrency();
  const maxTotal = Math.max(...data.months.map((m) => Number.parseFloat(m.total)), 1);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-50 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">{year} {t("content.planned.forecastTitle")}</h3>
        <span className="text-sm font-bold text-gray-900 flex items-center gap-1">
          {t("content.planned.totalLabel")}: <Money tl={data.year_total} className="text-sm font-bold text-gray-900" />
        </span>
      </div>

      <div className="divide-y divide-gray-50">
        {data.months.map((m) => {
          const total = Number.parseFloat(m.total);
          const barWidth = total > 0 ? Math.max((total / maxTotal) * 100, 4) : 0;
          const isEmpty = m.items.length === 0;

          return (
            <div key={m.month} className="px-6 py-3">
              <div className="flex items-center gap-4">
                <span className="text-xs font-medium text-gray-500 w-10 shrink-0">
                  {MONTH_NAMES[m.month - 1]}
                </span>

                <div className="flex-1">
                  {isEmpty ? (
                    <div className="h-6 flex items-center">
                      <span className="text-xs text-gray-300">—</span>
                    </div>
                  ) : (
                    <div className="relative h-6 flex items-center">
                      <div
                        className="absolute left-0 top-0 h-full bg-indigo-100 rounded-r"
                        style={{ width: `${barWidth}%` }}
                      />
                      <div className="relative flex flex-wrap gap-1 px-1 py-0.5">
                        {m.items.map((item) => {
                          const estSuffix = item.is_estimated ? ` (${t("content.planned.estimatedBadge")})` : "";
                          return (
                            <span
                              key={item.id}
                              className={`text-xs px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[item.category] ?? "bg-gray-100 text-gray-600"}`}
                              title={`${item.title} — ${formatTlAs(Number.parseFloat(item.amount), displayCurrency, rates)}${estSuffix}`}
                            >
                              {item.title}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <span className={`text-xs tabular-nums w-24 text-right shrink-0 font-semibold ${isEmpty ? "text-gray-300" : "text-gray-800"}`}>
                  {isEmpty ? "—" : formatTlAs(total, displayCurrency, rates)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
