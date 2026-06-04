"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { useTranslation } from "@/app/_i18n/I18nProvider";

type Status = "loading" | "success" | "error";

function UnsubscribeInner() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }
    api.unsubscribe(token)
      .then((ok) => setStatus(ok ? "success" : "error"))
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
        <div className="flex justify-center mb-6">
          <KFinansLogo size="xl" />
        </div>

        {status === "loading" && (
          <p className="text-sm text-gray-500">{t("content.unsubscribe.processing")}</p>
        )}

        {status === "success" && (
          <>
            <h2 className="text-base font-semibold text-gray-900 mb-2">{t("content.unsubscribe.successTitle")}</h2>
            <p className="text-sm text-gray-500 mb-6">{t("content.unsubscribe.successBody")}</p>
            <Link
              href="/dashboard/settings"
              className="inline-block px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              {t("content.unsubscribe.goSettings")}
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <h2 className="text-base font-semibold text-gray-900 mb-2">{t("content.unsubscribe.errorTitle")}</h2>
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mb-4">{t("content.unsubscribe.errorBody")}</p>
            <Link href="/login" className="block text-sm text-blue-600 hover:text-blue-700 font-medium">
              {t("content.unsubscribe.goLogin")}
            </Link>
          </>
        )}
      </div>

      <div className="mt-8 flex flex-col items-center gap-2">
        <p className="text-xs text-gray-400">{t("footer.by")}</p>
        <MayotekLogo />
        <p className="text-xs text-gray-400">{t("footer.productOf")}</p>
      </div>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-50 text-sm text-gray-400">…</div>}>
      <UnsubscribeInner />
    </Suspense>
  );
}
