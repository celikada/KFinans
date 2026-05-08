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

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const hasToken = typeof window !== "undefined"
      && localStorage.getItem("access_token") !== null;
    if (!hasToken) {
      router.replace("/login");
      return;
    }
    setAuthChecked(true);
  }, [router]);

  if (!authChecked) {
    // FOUC onleme: token yokken hicbir sey render etme
    return null;
  }

  return <>{children}</>;
}
