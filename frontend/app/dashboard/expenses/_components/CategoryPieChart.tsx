"use client";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CategoryBreakdownDTO, CurrencyType, EXPENSE_CATEGORY_LABELS } from "@/lib/api";
import { fmtCurrency } from "@/app/_components/Money";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly data: CategoryBreakdownDTO[];
  // Faz B: görüntüleme para birimindeki toplam (total_display'lerin toplamı).
  readonly total: number;
  readonly currency: CurrencyType;
}

const COLORS = [
  "#2563eb", "#16a34a", "#f97316", "#dc2626", "#9333ea",
  "#0891b2", "#ca8a04", "#65a30d", "#db2777", "#6b7280",
];

export function CategoryPieChart({ data, total, currency }: Props) {
  const { t } = useTranslation();
  if (data.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 text-center text-sm text-gray-400">
        {t("content.expenses.noCategoryData")}
      </div>
    );
  }

  // Faz B: dilim değerleri tarihsel-kur bazlı total_display (çift-çevrim yok).
  const chartData = data.map((b) => ({
    name: EXPENSE_CATEGORY_LABELS[b.category] ?? b.category,
    value: Number.parseFloat(b.total_display),
    pct: total > 0 ? (Number.parseFloat(b.total_display) / total) * 100 : 0,
  }));

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.expenses.categoryBreakdown")}</h2>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={90}
              innerRadius={48}
              paddingAngle={2}
              label={(props) => {
                const pct = (props as { pct?: number }).pct;
                return pct === undefined ? "" : `${pct.toFixed(0)}%`;
              }}
              labelLine={false}
            >
              {chartData.map((entry, i) => (
                <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v) => fmtCurrency(v as number, currency)}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
