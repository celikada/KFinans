"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, GoalDTO, GoalCurrency, GOAL_CURRENCY_SYMBOLS } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";

const MULTIPLIER = 300;
const CURRENCIES: GoalCurrency[] = ["TRY", "USD", "EUR", "GBP"];

function fmtForeign(val: number, currency: GoalCurrency) {
  const sym = GOAL_CURRENCY_SYMBOLS[currency];
  const n = val.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return currency === "TRY" ? `${n} ₺` : `${sym}${n}`;
}

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.min(pct, 100);
  const color =
    clamped >= 100 ? "bg-green-500" :
    clamped >= 70  ? "bg-blue-500"  :
    clamped >= 40  ? "bg-indigo-500" : "bg-violet-400";
  return (
    <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${clamped}%` }} />
    </div>
  );
}

export default function GoalPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [goal, setGoal] = useState<GoalDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [currency, setCurrency] = useState<GoalCurrency>("USD");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getGoal();
      setGoal(data);
      if (data.goal_amount) setInputVal(data.goal_amount);
      if (data.goal_currency) setCurrency(data.goal_currency as GoalCurrency);
    } catch {
      setError(t("content.goal.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave() {
    const val = parseFloat(inputVal);
    if (!val || val <= 0) { setError(t("content.goal.amountInvalid")); return; }
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const data = await api.setGoal(val, currency);
      setGoal(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.goal.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  const amount     = goal?.goal_amount        ? parseFloat(goal.goal_amount)        : null;
  const cur        = currency as GoalCurrency;
  const rate       = goal?.rate_to_tl         ? parseFloat(goal.rate_to_tl)         : null;
  const monthlyTL  = goal?.monthly_tl         ? parseFloat(goal.monthly_tl)         : null;
  const targetTL   = goal?.freedom_target_tl  ? parseFloat(goal.freedom_target_tl)  : null;
  const portfolio  = goal?.portfolio_value    ? parseFloat(goal.portfolio_value)    : null;
  const passiveTL  = goal?.passive_income_tl  ? parseFloat(goal.passive_income_tl)  : null;
  const passiveFgn = goal?.passive_income_foreign ? parseFloat(goal.passive_income_foreign) : null;
  const pct        = goal?.progress_pct ?? null;
  const months     = goal?.months_covered ?? null;
  const isForeign  = cur !== "TRY";

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.goal")} />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {loading && <p className="text-sm text-gray-400 text-center py-8">{t("common.loading")}</p>}

        {!loading && (
          <>
            {/* Hedef formu — her zaman görünür */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
              <h2 className="text-sm font-semibold text-gray-700">{t("content.goal.monthlyNeedTitle")}</h2>
              <p className="text-xs text-gray-400">
                {t("content.goal.multiplierHint").replace("{multiplier}", String(MULTIPLIER))}
              </p>

              {/* Para birimi seçici */}
              <div>
                <label className="block text-xs text-gray-500 mb-2">{t("content.goal.currency")}</label>
                <div className="flex rounded-lg border border-gray-200 overflow-hidden w-fit">
                  {CURRENCIES.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setCurrency(c)}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        currency === c
                          ? "bg-violet-600 text-white"
                          : "bg-white text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {GOAL_CURRENCY_SYMBOLS[c]} {c}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tutar girişi */}
              <div>
                <label className="block text-xs text-gray-500 mb-2">
                  {t("content.goal.monthlyNeed").replace("{currency}", currency)}
                </label>
                <div className="flex gap-3">
                  <div className="relative flex-1">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                      {GOAL_CURRENCY_SYMBOLS[currency]}
                    </span>
                    <input
                      type="number"
                      min="1"
                      step={currency === "TRY" ? "1000" : "100"}
                      className={`${INPUT_CLS} pl-7`}
                      placeholder={currency === "TRY" ? "50000" : "3000"}
                      value={inputVal}
                      onChange={(e) => setInputVal(e.target.value)}
                    />
                  </div>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="text-sm bg-violet-600 text-white px-5 py-2 rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors shrink-0"
                  >
                    {saving ? t("form.saving") : saved ? t("content.goal.saved") : t("common.save")}
                  </button>
                </div>
              </div>

              {error && <p className="text-xs text-red-500">{error}</p>}

              {/* Anlık özet: girilen değere göre hesap */}
              {inputVal && parseFloat(inputVal) > 0 && (
                <div className="bg-violet-50 rounded-xl p-4 text-xs space-y-1 text-violet-700">
                  {isForeign && rate && (
                    <p>
                      {GOAL_CURRENCY_SYMBOLS[currency]}{parseFloat(inputVal).toLocaleString("tr-TR")} × {fmtTL(rate)} ₺ =
                      <span className="font-semibold"> {fmtTL(parseFloat(inputVal) * rate)} ₺/ay</span>
                    </p>
                  )}
                  <p>
                    {t("content.goal.freedomTarget")}:
                    <span className="font-semibold ml-1">
                      {isForeign && rate
                        ? `${fmtTL(parseFloat(inputVal) * rate * MULTIPLIER)} ₺`
                        : `${fmtTL(parseFloat(inputVal) * MULTIPLIER)} ₺`}
                    </span>
                  </p>
                </div>
              )}
            </div>

            {/* İlerleme */}
            {amount && targetTL && monthlyTL && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
                <div className="flex justify-between items-start">
                  <h2 className="text-sm font-semibold text-gray-700">{t("content.goal.progressStatus")}</h2>
                  <div className="text-right">
                    <p className="text-xs text-gray-400">{t("content.goal.savedTarget")}</p>
                    <p className="text-sm font-semibold text-gray-700">
                      {fmtForeign(amount, goal!.goal_currency as GoalCurrency)}{t("content.goal.perMonthSuffix")}
                    </p>
                    {isForeign && (
                      <p className="text-xs text-gray-400">= {fmtTL(monthlyTL)} ₺{t("content.goal.perMonthSuffix")}</p>
                    )}
                  </div>
                </div>

                {portfolio ? (
                  <>
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs text-gray-500">
                        <span>{t("content.goal.currentPortfolio")}</span>
                        <span className="font-semibold text-gray-800">{fmtTL(portfolio)} ₺</span>
                      </div>
                      <ProgressBar pct={pct ?? 0} />
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-400">{t("content.goal.percentComplete").replace("{pct}", (pct ?? 0).toFixed(1))}</span>
                        <span className="text-gray-400">{t("content.goal.targetLabel")}: {fmtTL(targetTL)} ₺</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <Stat
                        label={t("content.goal.passiveIncomeTl")}
                        value={`${fmtTL(passiveTL!)} ₺`}
                        sub={t("content.goal.portfolioDivided").replace("{multiplier}", String(MULTIPLIER))}
                        color="text-violet-600"
                      />
                      {isForeign && passiveFgn !== null && rate && (
                        <Stat
                          label={t("content.goal.passiveIncomeCurrency").replace("{currency}", goal!.goal_currency)}
                          value={fmtForeign(passiveFgn, goal!.goal_currency as GoalCurrency)}
                          sub={`1 ${goal!.goal_currency} = ${fmtTL(rate)} ₺`}
                          color="text-blue-600"
                        />
                      )}
                      <Stat
                        label={t("content.goal.remainingToTarget")}
                        value={`${fmtTL(Math.max(0, targetTL - portfolio))} ₺`}
                        sub={pct! >= 100 ? t("content.goal.targetReached") : t("content.goal.percentShort").replace("{pct}", (100 - pct!).toFixed(1))}
                        color={pct! >= 100 ? "text-green-600" : "text-gray-700"}
                      />
                      <Stat
                        label={t("content.goal.monthsCovered")}
                        value={t("content.goal.monthsValue").replace("{months}", months?.toFixed(0) ?? "0")}
                        sub={t("content.goal.yearsValue").replace("{years}", ((months ?? 0) / 12).toFixed(1))}
                        color="text-indigo-600"
                      />
                      <Stat
                        label={t("content.goal.passiveVsNeed")}
                        value={
                          isForeign && passiveFgn !== null
                            ? (passiveFgn >= amount ? t("content.goal.financiallyFree") : t("content.goal.shortBy").replace("{amount}", fmtForeign(amount - passiveFgn, goal!.goal_currency as GoalCurrency)))
                            : (passiveTL! >= monthlyTL ? t("content.goal.financiallyFree") : t("content.goal.shortBy").replace("{amount}", `${fmtTL(monthlyTL - passiveTL!)} ₺`))
                        }
                        sub={
                          (isForeign ? passiveFgn! >= amount : passiveTL! >= monthlyTL)
                            ? t("content.goal.passiveSufficient")
                            : t("content.goal.passiveInsufficient")
                        }
                        color={
                          (isForeign ? passiveFgn! >= amount : passiveTL! >= monthlyTL)
                            ? "text-green-600" : "text-orange-500"
                        }
                      />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-400 py-2">
                    {t("content.goal.noPortfolioData")}
                  </p>
                )}
              </div>
            )}

            {/* Formül */}
            <div className="bg-violet-50 rounded-2xl border border-violet-100 p-5 text-xs text-violet-700 space-y-1">
              <p className="font-semibold mb-2">{t("content.goal.formulaTitle")}</p>
              <p>{t("content.goal.formulaTarget").replace("{multiplier}", String(MULTIPLIER))}</p>
              <p>{t("content.goal.formulaPassive").replace("{multiplier}", String(MULTIPLIER))}</p>
              {goal?.rate_to_tl && goal.goal_currency !== "TRY" && (
                <p>{t("content.goal.formulaRate").replace("{currency}", goal.goal_currency).replace("{rate}", fmtTL(parseFloat(goal.rate_to_tl)))}</p>
              )}
              <p className="pt-1 text-violet-500">
                {t("content.goal.formulaFootnote").replace("{multiplier}", String(MULTIPLIER))}
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-sm font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
