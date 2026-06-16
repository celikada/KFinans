// Abonelik kurum kategorisi → emoji ikon + Tailwind renk sınıfları.
// Liste/rozet/form'da görsel ayrım için tek kaynak.
import type { SubscriptionCategory } from "@/lib/api";

interface CategoryMeta {
  icon: string;
  /** Liste satırındaki ikon kabarcığı (arka plan + metin). */
  badgeCls: string;
}

const CATEGORY_META: Record<SubscriptionCategory, CategoryMeta> = {
  gas: { icon: "🔥", badgeCls: "bg-orange-50 text-orange-600 border-orange-100" },
  electricity: { icon: "⚡", badgeCls: "bg-yellow-50 text-yellow-600 border-yellow-100" },
  internet: { icon: "🌐", badgeCls: "bg-blue-50 text-blue-600 border-blue-100" },
  phone: { icon: "📱", badgeCls: "bg-purple-50 text-purple-600 border-purple-100" },
};

const FALLBACK: CategoryMeta = { icon: "📄", badgeCls: "bg-gray-50 text-gray-500 border-gray-100" };

export function categoryMeta(category: string): CategoryMeta {
  return CATEGORY_META[category as SubscriptionCategory] ?? FALLBACK;
}
