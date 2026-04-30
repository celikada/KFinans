"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";

type Status = "loading" | "success" | "expired" | "invalid" | "error";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      setMessage("Doğrulama bağlantısı eksik veya geçersiz.");
      return;
    }
    api.verifyEmail(token)
      .then((res) => {
        setStatus("success");
        setMessage(res.detail);
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "Doğrulama başarısız";
        if (msg.toLowerCase().includes("süre") || msg.toLowerCase().includes("dolm")) {
          setStatus("expired");
        } else {
          setStatus("error");
        }
        setMessage(msg);
      });
  }, [token]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
        <div className="flex justify-center mb-6">
          <Image src="/images/kfinans-logo.png" alt="KFinans" width={140} height={148} priority />
        </div>

        {status === "loading" && (
          <p className="text-sm text-gray-500">Doğrulanıyor...</p>
        )}

        {status === "success" && (
          <>
            <h2 className="text-base font-semibold text-gray-900 mb-2">E-posta doğrulandı</h2>
            <p className="text-sm text-gray-500 mb-6">{message}</p>
            <Link
              href="/login"
              className="inline-block px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              Giriş Yap
            </Link>
          </>
        )}

        {(status === "expired" || status === "invalid" || status === "error") && (
          <>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              {status === "expired" ? "Bağlantının süresi dolmuş" : "Doğrulama başarısız"}
            </h2>
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mb-4">{message}</p>
            {status === "expired" && (
              <p className="text-xs text-gray-400 mb-4">
                Kayıt sayfasından yeni bir doğrulama bağlantısı talep edebilirsin.
              </p>
            )}
            <Link
              href="/login"
              className="block text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Giriş sayfasına dön
            </Link>
          </>
        )}
      </div>

      <div className="mt-8 flex flex-col items-center gap-2">
        <p className="text-xs text-gray-400">Bir</p>
        <Image src="/images/mayotek-logo.png" alt="Mayotek" width={90} height={30} />
        <p className="text-xs text-gray-400">ürünüdür</p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-50 text-sm text-gray-400">Yükleniyor...</div>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
