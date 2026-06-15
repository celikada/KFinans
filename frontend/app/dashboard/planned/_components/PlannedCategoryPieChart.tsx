"use client";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { PlannedExpenseDTO, PLANNED_CATEGORY_LABELS } from "@/lib/api";
import { fmtTL } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly items: PlannedExpenseDTO[];
}

const COLORS = [
  "#4f46e5", "#16a34a", "#f97316", "#dc2626", "#9333ea",
  "#0891b2", "#ca8a04", "#65a30d", "#db2777", "#6b7280",
];

/**
 * Planlı harcamaların kategori bazlı dağılımını disk (donut) grafiğiyle gösterir.
 * Karışık para birimleri için ham `amount` toplanır (göreli dağılım amacıyla);
 * tooltip/etiket TL biçiminde gösterilir.
 */
export function PlannedCategoryPieChart({ items }: Props) {
  const { t } = useTranslation();

  // Kategori bazlı toplam
  const totals = new Map<string, number>();
  for (const pe of items) {
    const amt = Number.parseFloat(pe.amount);
    if (!Number.isFinite(amt)) continue;
    totals.set(pe.category, (totals.get(pe.category) ?? 0) + amt);
  }

  const grandTotal = [...totals.values()].reduce((s, v) => s + v, 0);

  if (totals.size === 0 || grandTotal <= 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 text-center text-sm text-gray-400">
        {t("content.planned.noCategoryData")}
      </div>
    );
  }

  const chartData = [...totals.entries()].map(([category, value]) => ({
    name: PLANNED_CATEGORY_LABELS[category as keyof typeof PLANNED_CATEGORY_LABELS] ?? category,
    value,
    pct: (value / grandTotal) * 100,
  }));

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.planned.categoryBreakdown")}</h2>
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
              formatter={(v) => fmtTL(v as number)}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
