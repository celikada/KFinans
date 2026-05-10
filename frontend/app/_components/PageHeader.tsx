"use client";
import { useRouter } from "next/navigation";

import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";

interface PageHeaderProps {
  title: string;
  back?: string;  // varsayilan: /dashboard
}

export function PageHeader({ title, back = "/dashboard" }: PageHeaderProps) {
  const router = useRouter();
  return (
    <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
      <button
        onClick={() => router.push(back)}
        className="text-gray-400 hover:text-gray-600 text-sm"
      >
        ← Geri
      </button>
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      <div className="ml-auto">
        <LanguageSwitcher />
      </div>
    </header>
  );
}
