"use client";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  year: number;
  month: number;
  onChange: (year: number, month: number) => void;
}

export function MonthSelector({ year, month, onChange }: Props) {
  const { t } = useTranslation();
  const now = new Date();
  const currentYear = now.getFullYear();
  const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1];

  return (
    <div className="flex gap-2 items-center">
      <select
        value={month}
        onChange={(e) => onChange(year, parseInt(e.target.value))}
        className={`w-32 ${INPUT_CLS}`}
      >
        {Array.from({ length: 12 }, (_, i) => (
          <option key={i} value={i + 1}>{t(`months.${i + 1}`)}</option>
        ))}
      </select>
      <select
        value={year}
        onChange={(e) => onChange(parseInt(e.target.value), month)}
        className={`w-24 ${INPUT_CLS}`}
      >
        {years.map((y) => (
          <option key={y} value={y}>{y}</option>
        ))}
      </select>
    </div>
  );
}
