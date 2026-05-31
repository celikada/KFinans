"use client";
import { useEffect, useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { useTranslation } from "@/app/_i18n/I18nProvider";

const CARD_CLS = "bg-white rounded-2xl border border-gray-100 shadow-sm p-6";
const INPUT_CLS =
  "w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500";

type SetupStage = "idle" | "setup" | "recovery";

function qrSrc(qr: string): string {
  // Backend kisaca raw base64 veya data URL gonderebilir; her ikisini de destekle.
  return qr.startsWith("data:") ? qr : `data:image/png;base64,${qr}`;
}

export default function MfaSecurityPage() {
  const router = useRouter();
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // Setup state
  const [stage, setStage] = useState<SetupStage>("idle");
  const [setupData, setSetupData] = useState<{
    secret: string;
    otpauth: string;
    qr: string;
  } | null>(null);
  const [setupCode, setSetupCode] = useState("");
  const [setupSaving, setSetupSaving] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);

  // Disable state
  const [disableOpen, setDisableOpen] = useState(false);
  const [disableCode, setDisableCode] = useState("");
  const [disableSaving, setDisableSaving] = useState(false);

  useEffect(() => {
    api
      .mfaStatus()
      .then((data) => setMfaEnabled(data.mfa_enabled))
      .catch((err: Error) => {
        if (err.message.includes("401")) router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function handleSetup() {
    setError("");
    setInfo("");
    try {
      const data = await api.mfaSetup();
      setSetupData({
        secret: data.secret_base32,
        otpauth: data.otpauth_url,
        qr: data.qr_png_base64,
      });
      setStage("setup");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("mfa.setupFailed"));
    }
  }

  async function handleEnable(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(setupCode)) {
      setError(t("mfa.invalidCode"));
      return;
    }
    setSetupSaving(true);
    try {
      const data = await api.mfaEnable(setupCode);
      setRecoveryCodes(data.recovery_codes);
      setStage("recovery");
      setMfaEnabled(true);
      setSetupCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("mfa.invalidCode"));
    } finally {
      setSetupSaving(false);
    }
  }

  async function handleDisable(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(disableCode)) {
      setError(t("mfa.invalidCode"));
      return;
    }
    setDisableSaving(true);
    try {
      await api.mfaDisable(disableCode);
      setMfaEnabled(false);
      setDisableOpen(false);
      setDisableCode("");
      setInfo(t("mfa.disabledOk"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("mfa.invalidCode"));
    } finally {
      setDisableSaving(false);
    }
  }

  function finishSetup() {
    setStage("idle");
    setSetupData(null);
    setRecoveryCodes([]);
    setInfo(t("mfa.enabledOk"));
  }

  function copyCodes() {
    try {
      void navigator.clipboard.writeText(recoveryCodes.join("\n"));
    } catch {
      // best-effort
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title={t("mfa.title")} back="/dashboard/settings" />
        <p className="text-sm text-gray-400 text-center py-16">
          {t("common.loading")}
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("mfa.title")} back="/dashboard/settings" />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {/* Durum */}
        <section className={CARD_CLS}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900 mb-1">
                {t("mfa.title")}
              </h2>
              <p className="text-sm text-gray-600">
                {mfaEnabled ? t("mfa.activeDesc") : t("mfa.inactiveDesc")}
              </p>
            </div>
            <span
              className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                mfaEnabled
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-gray-100 text-gray-600 border border-gray-200"
              }`}
              data-testid="mfa-status-badge"
            >
              {mfaEnabled ? t("mfa.statusActive") : t("mfa.statusInactive")}
            </span>
          </div>

          {info && (
            <output
              aria-live="polite"
              className="block mt-4 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg"
            >
              {info}
            </output>
          )}
          {error && (
            <p
              role="alert"
              aria-live="assertive"
              className="mt-4 text-sm text-red-700 bg-red-50 px-3 py-2 rounded-lg"
            >
              {error}
            </p>
          )}

          {!mfaEnabled && stage === "idle" && (
            <button
              type="button"
              onClick={handleSetup}
              className="mt-4 w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
              data-testid="mfa-setup-btn"
            >
              {t("mfa.setupBtn")}
            </button>
          )}

          {mfaEnabled && !disableOpen && (
            <button
              type="button"
              onClick={() => setDisableOpen(true)}
              className="mt-4 w-full py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
              data-testid="mfa-disable-btn"
            >
              {t("mfa.disableBtn")}
            </button>
          )}
        </section>

        {/* Setup stage: QR + enable */}
        {stage === "setup" && setupData && (
          <section className={CARD_CLS} data-testid="mfa-setup-panel">
            <h3 className="text-base font-semibold text-gray-900 mb-2">
              {t("mfa.setupTitle")}
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              {t("mfa.qrInstruction")}
            </p>
            <div className="flex flex-col items-center gap-3 mb-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrSrc(setupData.qr)}
                alt={t("mfa.qrAlt")}
                width={192}
                height={192}
                className="border border-gray-100 rounded-lg p-1"
                data-testid="mfa-qr-image"
              />
              <p className="text-xs text-gray-500">{t("mfa.manualSecretHint")}</p>
              <code
                className="text-xs bg-gray-50 px-2 py-1 rounded font-mono break-all"
                data-testid="mfa-secret"
              >
                {setupData.secret}
              </code>
            </div>

            <form onSubmit={handleEnable} className="space-y-3">
              <label
                htmlFor="mfa-setup-code"
                className="block text-xs text-gray-500"
              >
                {t("mfa.codeInput")}
              </label>
              <input
                id="mfa-setup-code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                maxLength={6}
                required
                value={setupCode}
                onChange={(e) =>
                  setSetupCode(e.target.value.replaceAll(/\D/g, "").slice(0, 6))
                }
                placeholder="123456"
                className={INPUT_CLS + " text-center tracking-[0.4em] font-mono"}
                data-testid="mfa-setup-code"
              />
              <button
                type="submit"
                disabled={setupSaving}
                className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                data-testid="mfa-enable-btn"
              >
                {setupSaving ? t("common.saving") : t("mfa.verifyAndActivate")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setStage("idle");
                  setSetupData(null);
                  setSetupCode("");
                }}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-700"
              >
                {t("common.cancel")}
              </button>
            </form>
          </section>
        )}

        {/* Recovery codes stage */}
        {stage === "recovery" && recoveryCodes.length > 0 && (
          <section
            className={`${CARD_CLS} border-amber-200`}
            data-testid="mfa-recovery-panel"
          >
            <h3 className="text-base font-semibold text-amber-700 mb-2">
              {t("mfa.recoveryTitle")}
            </h3>
            <p
              role="alert"
              className="text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-lg mb-3"
            >
              {t("mfa.recoveryWarning")}
            </p>
            <ul
              className="grid grid-cols-2 gap-2 mb-4"
              data-testid="mfa-recovery-list"
            >
              {recoveryCodes.map((code) => (
                <li
                  key={code}
                  className="text-sm font-mono bg-gray-50 px-3 py-2 rounded"
                >
                  {code}
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={copyCodes}
                className="flex-1 py-2 rounded-lg border border-gray-200 text-sm font-medium hover:bg-gray-50"
              >
                {t("mfa.copyCodes")}
              </button>
              <button
                type="button"
                onClick={finishSetup}
                className="flex-1 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
                data-testid="mfa-recovery-saved-btn"
              >
                {t("mfa.codesSaved")}
              </button>
            </div>
          </section>
        )}

        {/* Disable form */}
        {disableOpen && (
          <section className={`${CARD_CLS} border-red-100`}>
            <h3 className="text-base font-semibold text-red-700 mb-2">
              {t("mfa.disableTitle")}
            </h3>
            <p className="text-sm text-gray-600 mb-3">
              {t("mfa.disableInstruction")}
            </p>
            <form onSubmit={handleDisable} className="space-y-3">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                maxLength={6}
                required
                value={disableCode}
                onChange={(e) =>
                  setDisableCode(e.target.value.replaceAll(/\D/g, "").slice(0, 6))
                }
                placeholder="123456"
                className={INPUT_CLS + " text-center tracking-[0.4em] font-mono"}
                data-testid="mfa-disable-code"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setDisableOpen(false);
                    setDisableCode("");
                  }}
                  className="flex-1 py-2 rounded-lg border border-gray-200 text-sm font-medium hover:bg-gray-50"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={disableSaving}
                  className="flex-1 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                  data-testid="mfa-disable-confirm-btn"
                >
                  {disableSaving ? t("common.saving") : t("mfa.disableBtn")}
                </button>
              </div>
            </form>
          </section>
        )}

        <p className="text-xs text-gray-500 text-center">
          <Link
            href="/dashboard/settings"
            className="hover:text-gray-700 underline"
          >
            {t("common.back")} {t("pages.settings")}
          </Link>
        </p>
      </main>
    </div>
  );
}
