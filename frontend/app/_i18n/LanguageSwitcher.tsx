"use client";
/**
 * i18n-001 (FAZ H): TR/EN dil secici toggle butonu.
 *
 * Iki segmentli pill button — kucuk footprint, dashboard layout'unda
 * skip-link yaninda kullanilir. ARIA: role="group" + her butonun
 * aria-pressed state'i.
 */
import * as React from "react";

import { useTranslation, type Locale } from "./I18nProvider";

const LOCALES: Locale[] = ["tr", "en"];
const LABEL: Record<Locale, string> = { tr: "TR", en: "EN" };

export function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { locale, setLocale, t } = useTranslation();

  return (
    <div
      role="group"
      aria-label={t("common.languageSwitcher")}
      className={`inline-flex items-center gap-0.5 rounded-lg border border-gray-200 bg-white p-0.5 text-xs ${className}`}
    >
      {LOCALES.map((l) => {
        const active = l === locale;
        return (
          <button
            key={l}
            type="button"
            onClick={() => setLocale(l)}
            aria-pressed={active}
            className={`rounded-md px-2 py-1 font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
              active
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {LABEL[l]}
          </button>
        );
      })}
    </div>
  );
}
