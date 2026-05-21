"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, setAuth } from "@/lib/api";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";
import { useTranslation } from "@/app/_i18n/I18nProvider";

type Stage = "credentials" | "mfa";
type MfaMode = "totp" | "recovery";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // Email dogrulanmadi durumu — login 403 sonrasi "yeniden gonder" akisi
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendNotice, setResendNotice] = useState("");

  // MFA challenge state
  const [stage, setStage] = useState<Stage>("credentials");
  const [mfaMode, setMfaMode] = useState<MfaMode>("totp");
  const [preMfaToken, setPreMfaToken] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNeedsVerification(false);
    setResendNotice("");
    setLoading(true);
    try {
      const data = await api.login(email, password);
      // Backend MFA gerektiriyorsa pre_mfa_token + mfa_required doner.
      if (data.mfa_required && data.pre_mfa_token) {
        setPreMfaToken(data.pre_mfa_token);
        setStage("mfa");
        setMfaMode("totp");
        return;
      }
      if (!data.access_token || !data.refresh_token) {
        throw new Error(t("auth.loginFailed"));
      }
      // FAZ C4: hem access hem refresh sakla — refresh token rotation +
      // 401 sonrası otomatik retry için lib/api.ts::tryRefresh() kullanır.
      setAuth(data.access_token, data.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : t("auth.loginFailed");
      setError(message);
      // Backend 403 + "E-posta adresiniz henüz doğrulanmadı" -> resend akisi
      const lower = message.toLowerCase();
      if (lower.includes("doğrulan") || lower.includes("dogrulan") || lower.includes("verif")) {
        setNeedsVerification(true);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResendVerification() {
    if (!email) return;
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

  async function handleMfaSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!preMfaToken) {
      setError(t("mfa.sessionExpired"));
      setStage("credentials");
      return;
    }
    if (mfaMode === "totp" && !/^\d{6}$/.test(totpCode)) {
      setError(t("mfa.invalidCode"));
      return;
    }
    if (mfaMode === "recovery" && recoveryCode.trim().length < 8) {
      setError(t("mfa.invalidRecovery"));
      return;
    }
    setLoading(true);
    try {
      const payload =
        mfaMode === "totp"
          ? { totp_code: totpCode }
          : { recovery_code: recoveryCode.trim() };
      const data = await api.mfaVerify(preMfaToken, payload);
      setAuth(data.access_token, data.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("mfa.invalidCode"));
    } finally {
      setLoading(false);
    }
  }

  function resetMfa() {
    setStage("credentials");
    setPreMfaToken(null);
    setTotpCode("");
    setRecoveryCode("");
    setMfaMode("totp");
    setError("");
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
        <p className="text-sm text-gray-600 mb-8 text-center">
          {stage === "credentials" ? t("auth.loginTitle") : t("mfa.verifyTitle")}
        </p>

        {stage === "credentials" && (
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

            {needsVerification && (
              <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 px-3 py-3 rounded-lg space-y-2">
                <p>{t("auth.verificationNotReceived")}</p>
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resending || !email}
                  className="text-sm font-medium text-blue-700 hover:text-blue-800 underline disabled:opacity-50 disabled:no-underline"
                >
                  {resending ? t("auth.resending") : t("auth.resendVerification")}
                </button>
                {resendNotice && (
                  <p role="status" aria-live="polite" className="text-xs text-gray-700">{resendNotice}</p>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? t("auth.loggingIn") : t("auth.login")}
            </button>
          </form>
        )}

        {stage === "mfa" && (
          <form
            onSubmit={handleMfaSubmit}
            className="space-y-4"
            data-testid="mfa-challenge-form"
          >
            <p className="text-xs text-gray-500">
              {mfaMode === "totp" ? t("mfa.verifyDesc") : t("mfa.recoveryDesc")}
            </p>

            {mfaMode === "totp" ? (
              <div>
                <label
                  htmlFor="mfa-totp"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  {t("mfa.codeInput")}
                </label>
                <input
                  id="mfa-totp"
                  name="totp_code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="one-time-code"
                  maxLength={6}
                  required
                  autoFocus
                  value={totpCode}
                  onChange={(e) =>
                    setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  placeholder="123456"
                  data-testid="mfa-login-code"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-center tracking-[0.4em] font-mono text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ) : (
              <div>
                <label
                  htmlFor="mfa-recovery"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  {t("mfa.recoveryCode")}
                </label>
                <input
                  id="mfa-recovery"
                  name="recovery_code"
                  type="text"
                  autoComplete="one-time-code"
                  required
                  autoFocus
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value)}
                  placeholder="xxxxxx-xxxx"
                  data-testid="mfa-login-recovery"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg font-mono text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}

            {error && (
              <p
                role="alert"
                aria-live="assertive"
                className="text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              data-testid="mfa-login-submit"
            >
              {loading ? t("auth.loggingIn") : t("mfa.verifyBtn")}
            </button>

            <div className="flex items-center justify-between text-xs">
              <button
                type="button"
                onClick={() => {
                  setMfaMode((m) => (m === "totp" ? "recovery" : "totp"));
                  setError("");
                }}
                className="text-blue-600 hover:text-blue-700"
                data-testid="mfa-login-toggle-mode"
              >
                {mfaMode === "totp"
                  ? t("mfa.useRecovery")
                  : t("mfa.useAuthenticator")}
              </button>
              <button
                type="button"
                onClick={resetMfa}
                className="text-gray-500 hover:text-gray-700"
              >
                {t("common.cancel")}
              </button>
            </div>
          </form>
        )}

        {stage === "credentials" && (
          <p className="mt-4 text-xs text-gray-600 text-center">
            {t("auth.registerHint")}{" "}
            <Link href="/register" className="text-blue-600 hover:text-blue-700 font-medium">
              {t("auth.register")}
            </Link>
          </p>
        )}
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
