"use client";
import { useState, FormEvent } from "react";
import Link from "next/link";
import { api, CurrencyType, CURRENCIES } from "@/lib/api";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";
import { useTranslation } from "@/app/_i18n/I18nProvider";

type RiskProfile = "conservative" | "balanced" | "aggressive";

export default function RegisterPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("balanced");
  const [defaultCurrency, setDefaultCurrency] = useState<CurrencyType>("TRY");
  const [showPassword, setShowPassword] = useState(false);
  const [kvkkRead, setKvkkRead] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [overseasConsent, setOverseasConsent] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);  // COMP-010
  // Sürüm bildirimleri — KVKK açık rıza, opsiyonel, varsayılan KAPALI.
  const [releaseNotesOptIn, setReleaseNotesOptIn] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendNotice, setResendNotice] = useState("");

  const riskOptions: { key: RiskProfile; labelKey: string }[] = [
    { key: "conservative", labelKey: "auth.riskConservative" },
    { key: "balanced", labelKey: "auth.riskBalanced" },
    { key: "aggressive", labelKey: "auth.riskAggressive" },
  ];

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError(t("auth.passwordMinError"));
      return;
    }
    if (password !== passwordConfirm) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    if (!kvkkRead) {
      setError(t("auth.kvkkRequired"));
      return;
    }
    if (!termsAccepted) {
      setError(t("auth.termsRequired"));
      return;
    }
    if (!overseasConsent) {
      setError(t("auth.overseasRequired"));
      return;
    }
    if (!ageConfirmed) {
      setError(t("auth.ageRequiredLong"));
      return;
    }

    setLoading(true);
    try {
      const data = await api.register(email, password, riskProfile, ageConfirmed, releaseNotesOptIn, defaultCurrency);
      setSuccess(true);
      setEmailSent(data.verification_email_sent);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.registerFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResending(true);
    setResendNotice("");
    try {
      await api.resendVerification(email);
      setResendNotice(t("auth.resendSuccess"));
    } catch (err) {
      setResendNotice(err instanceof Error ? err.message : t("auth.resendFailed"));
    } finally {
      setResending(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 relative">
        <div className="absolute top-3 right-3">
          <LanguageSwitcher />
        </div>
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
          <div className="flex justify-center mb-6">
            <KFinansLogo size="xl" />
          </div>
          <h2 className="text-base font-semibold text-gray-900 mb-2">
            {emailSent ? t("auth.checkEmail") : t("auth.registrationComplete")}
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            {emailSent
              ? t("auth.verificationSent").replace("{email}", email)
              : t("auth.verificationFailed")}
          </p>

          {resendNotice && (
            <output aria-live="polite" className="block text-xs text-gray-600 bg-gray-50 px-3 py-2 rounded-lg mb-4">{resendNotice}</output>
          )}

          <button
            onClick={handleResend}
            disabled={resending}
            className="w-full py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors mb-3"
          >
            {resending ? t("auth.resending") : t("auth.resendVerification")}
          </button>

          <Link
            href="/login"
            className="block text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            {t("auth.backToLogin")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 py-8 relative">
      <div className="absolute top-3 right-3">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex justify-center mb-6">
          <KFinansLogo size="xl" />
        </div>
        <p className="text-sm text-gray-600 mb-8 text-center">{t("auth.registerTitle")}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="register-email" className="block text-sm font-medium text-gray-700 mb-1">{t("auth.email")}</label>
            <input
              id="register-email"
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
              <label htmlFor="register-password" className="block text-sm font-medium text-gray-700">{t("auth.password")}</label>
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                {showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
              </button>
            </div>
            <input
              id="register-password"
              name="new-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={t("auth.passwordMin")}
            />
          </div>

          <div>
            <label htmlFor="register-password-confirm" className="block text-sm font-medium text-gray-700 mb-1">{t("auth.passwordRepeat")}</label>
            <input
              id="register-password-confirm"
              name="new-password-confirm"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={t("auth.passwordPlaceholder")}
            />
          </div>

          <div>
            <label htmlFor="register-risk" className="block text-sm font-medium text-gray-700 mb-1">{t("auth.riskProfile")}</label>
            <select
              id="register-risk"
              value={riskProfile}
              onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {riskOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>{t(opt.labelKey)}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="register-currency" className="block text-sm font-medium text-gray-700 mb-1">{t("auth.defaultCurrency")}</label>
            <select
              id="register-currency"
              value={defaultCurrency}
              onChange={(e) => setDefaultCurrency(e.target.value as CurrencyType)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="space-y-2 pt-1">
            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={kvkkRead}
                onChange={(e) => setKvkkRead(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>{t("auth.kvkkConsentLabel")}</span>
            </label>

            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>{t("auth.termsConsentLabel")}</span>
            </label>

            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={overseasConsent}
                onChange={(e) => setOverseasConsent(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>{t("auth.overseasConsentLong")}</span>
            </label>

            {/* COMP-010 (FAZ H): 18+ yas dogrulama (KVKK 2018/482, TMK m.16) */}
            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={ageConfirmed}
                onChange={(e) => setAgeConfirmed(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>{t("auth.ageConfirmLong")}</span>
            </label>

            {/* Sürüm bildirimleri — opsiyonel KVKK açık rıza (varsayılan KAPALI) */}
            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={releaseNotesOptIn}
                onChange={(e) => setReleaseNotesOptIn(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>{t("auth.releaseNotesOptIn")}</span>
            </label>
          </div>

          {error && (
            <p role="alert" aria-live="assertive" className="text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? t("auth.registering") : t("auth.register")}
          </button>
        </form>

        <p className="mt-4 text-xs text-gray-600 text-center">
          {t("auth.loginHint")}{" "}
          <Link href="/login" className="text-blue-600 hover:text-blue-700 font-medium">
            {t("auth.login")}
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
