"use client";
/**
 * i18n-001 (FAZ H): Client-side internationalization provider.
 *
 * Foundation kapsamli — sayfa bazli `app/[lang]/...` routing yok.
 * Yerine cookie tabanli locale state + React Context. Avantaj:
 *   - Mevcut 17 dashboard sayfasini tasimaya gerek yok.
 *   - Locale degisiminde sayfa reload yok (Context push).
 * Dezavantaj:
 *   - Server Component'lerde dil cevirisi yok (gerekli olursa sayfa
 *     `"use client"` yapilmali). MVP'de tum sayfalar zaten client.
 *
 * Kullanim:
 *   const { t, locale, setLocale } = useTranslation();
 *   <h1>{t("auth.login")}</h1>
 *
 * Eksik anahtarlarda key string'i geri doner (sessiz fallback).
 */
import * as React from "react";

import enDict from "./dictionaries/en.json";
import trDict from "./dictionaries/tr.json";

export type Locale = "tr" | "en";

const dictionaries = { tr: trDict, en: enDict } as const;
const COOKIE_NAME = "kfinans-locale";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 yil

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = React.createContext<I18nContextValue>({
  locale: "tr",
  setLocale: () => {},
  t: (k) => k,
});

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie.split("; ");
  for (const c of cookies) {
    const [k, v] = c.split("=");
    if (k === name) return decodeURIComponent(v ?? "");
  }
  return null;
}

function writeCookie(name: string, value: string, maxAge: number): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; samesite=lax`;
}

function lookupKey(locale: Locale, key: string): string {
  const dict: Record<string, unknown> = dictionaries[locale];
  const parts = key.split(".");
  let val: unknown = dict;
  for (const p of parts) {
    if (val !== null && typeof val === "object" && p in (val as Record<string, unknown>)) {
      val = (val as Record<string, unknown>)[p];
    } else {
      return key;
    }
  }
  return typeof val === "string" ? val : key;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = React.useState<Locale>("tr");

  React.useEffect(() => {
    const saved = readCookie(COOKIE_NAME);
    if (saved === "en" || saved === "tr") {
      setLocaleState(saved);
    }
  }, []);

  const setLocale = React.useCallback((l: Locale) => {
    setLocaleState(l);
    writeCookie(COOKIE_NAME, l, COOKIE_MAX_AGE);
    // <html lang> attribute guncelleme — ekran okuyuculara dil degisikligi.
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("lang", l);
    }
  }, []);

  const t = React.useCallback((key: string) => lookupKey(locale, key), [locale]);

  const value = React.useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18nContextValue {
  return React.useContext(I18nContext);
}
