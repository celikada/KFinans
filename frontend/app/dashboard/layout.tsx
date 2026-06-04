"use client";

// FE-005 (FAZ H): Dashboard tek noktadan auth guard.
// Onceden 17 sayfanin her birinde `if (!localStorage.getItem("access_token"))
// router.replace("/login")` boilerplate'i vardi (race condition + token sync).
// Artik sadece bu layout kontrol eder; alt sayfalar guarded varsayar.
//
// proxy.ts (server-side middleware) cookie tabanli early redirect yapar; bu
// layout localStorage tabanli safety net (cookie senkron disindaki tek-frame
// FOUC'u onler). Login akisinda setAuth ikisini birden set eder.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { cacheDefaultCurrency } from "@/lib/defaultCurrency";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function DashboardLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const { t } = useTranslation();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const hasToken = globalThis.window !== undefined
      && localStorage.getItem("access_token") !== null;
    if (!hasToken) {
      router.replace("/login");
      return;
    }
    setAuthChecked(true);
    // v0.3.0: kullanıcının varsayılan para birimini formlar için önbelleğe al
    // (best-effort — başarısız olursa formlar "TRY" varsayar).
    api.getMe()
      .then((u) => cacheDefaultCurrency(u.default_currency))
      .catch(() => {});
  }, [router]);

  if (!authChecked) {
    // FOUC onleme: token yokken hicbir sey render etme
    return null;
  }

  // A11Y-001 (FAZ H): Skip-to-content link — klavye kullanicisi tab tusu ile
  // her sayfada nav menu'sunu atlayip ana icerige ulasabilsin (WCAG 2.4.1).
  // sr-only default; focus alindiginda gorunur olur.
  // Sayfalar kendi <main> elementlerine sahip — wrapper olarak <div> kullaniyoruz
  // (cift main landmark olusmasini onlemek icin).
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg focus:shadow-lg"
      >
        {t("common.skipToContent")}
      </a>
      {/* LanguageSwitcher dashboard header'larina (page.tsx + PageHeader) yerlestirildi —
          fixed position Ayarlar/Cikis butonlariyla cakisiyordu (kullanici 2026-05-10). */}
      <div id="main-content">{children}</div>
    </>
  );
}
