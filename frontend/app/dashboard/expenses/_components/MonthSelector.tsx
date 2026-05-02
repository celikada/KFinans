"use client";
import { INPUT_CLS } from "@/lib/format";

const MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

interface Props {
  year: number;
  month: number;
  onChange: (year: number, month: number) => void;
}

export function MonthSelector({ year, month, onChange }: Props) {
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
        {MONTHS.map((label, i) => (
          <option key={i} value={i + 1}>{label}</option>
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
