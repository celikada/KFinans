import { EXPENSE_CATEGORY_LABELS } from "@/lib/api";
import type { BudgetBucket } from "@/lib/api";

/**
 * Kategori etiketi: gider kategorisi → TR sabit etiket; "savings" → çeviri;
 * aksi (ağırlıklı periyodik kalemin serbest başlığı) → olduğu gibi.
 */
export function categoryLabel(category: string, t: (k: string) => string): string {
  if (category === "savings") return t("content.budgetV2.savings");
  const label = EXPENSE_CATEGORY_LABELS[category as keyof typeof EXPENSE_CATEGORY_LABELS];
  return label ?? category;
}

export function bucketLabel(bucket: BudgetBucket, t: (k: string) => string): string {
  return t(`content.budgetV2.buckets.${bucket}`);
}

export const BUCKET_ORDER: BudgetBucket[] = ["fundamental", "fun", "future"];

/** Kova renk paleti (Tailwind class parçaları). */
export const BUCKET_STYLES: Record<BudgetBucket, { bar: string; chip: string; text: string }> = {
  fundamental: { bar: "bg-blue-500", chip: "bg-blue-50 text-blue-700", text: "text-blue-700" },
  fun: { bar: "bg-amber-500", chip: "bg-amber-50 text-amber-700", text: "text-amber-700" },
  future: { bar: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-700", text: "text-emerald-700" },
};
