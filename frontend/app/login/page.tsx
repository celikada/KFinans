"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, setAuth } from "@/lib/api";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";
import { useTranslation } from "@/app/_i18n/I18nProvider";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api.login(email, password);
      // FAZ C4: hem access hem refresh sakla — refresh token rotation +
      // 401 sonrası otomatik retry için lib/api.ts::tryRefresh() kullanır.
      setAuth(data.access_token, data.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.loginFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 relative">
      <div className="absolute top-3 right-3">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex justify-center mb-6">
          <KFinansLogo size="xl" />
        </div>
        <p className="text-sm text-gray-600 mb-8 text-center">{t("auth.loginTitle")}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-gray-700 mb-1">{t("auth.email")}</label>
            <input
              id="login-email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={t("auth.emailPlaceholder")}
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">{t("auth.password")}</label>
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                {showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
              </button>
            </div>
            <input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={t("auth.passwordPlaceholder")}
            />
          </div>

          {error && (
            <p role="alert" aria-live="assertive" className="text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? t("auth.loggingIn") : t("auth.login")}
          </button>
        </form>

        <p className="mt-4 text-xs text-gray-600 text-center">
          {t("auth.registerHint")}{" "}
          <Link href="/register" className="text-blue-600 hover:text-blue-700 font-medium">
            {t("auth.register")}
          </Link>
        </p>
      </div>

      <div className="mt-8 flex flex-col items-center gap-2">
        <p className="text-xs text-gray-500">{t("footer.by")}</p>
        <MayotekLogo />
        <p className="text-xs text-gray-500">{t("footer.productOf")}</p>
      </div>

      <div className="mt-4 flex gap-3 text-xs text-gray-500">
        <Link href="/legal/kvkk" className="hover:text-gray-800">{t("legal.kvkk")}</Link>
        <Link href="/legal/privacy" className="hover:text-gray-800">{t("legal.privacy")}</Link>
        <Link href="/legal/terms" className="hover:text-gray-800">{t("legal.terms")}</Link>
        <Link href="/legal/cookies" className="hover:text-gray-800">{t("legal.cookies")}</Link>
      </div>
    </div>
  );
}
