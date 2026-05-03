"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, GoalDTO, GoalCurrency, GOAL_CURRENCY_SYMBOLS } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { INPUT_CLS } from "@/lib/format";

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
      setError("Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    load();
  }, [load, router]);

  async function handleSave() {
    const val = parseFloat(inputVal);
    if (!val || val <= 0) { setError("Geçerli bir tutar girin"); return; }
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const data = await api.setGoal(val, currency);
      setGoal(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
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
      <PageHeader title="Finansal Hedef" />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {loading && <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>}

        {!loading && (
          <>
            {/* Hedef formu — her zaman görünür */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
              <h2 className="text-sm font-semibold text-gray-700">Aylık finansal özgürlük ihtiyacı</h2>
              <p className="text-xs text-gray-400">
                Bu değerin {MULTIPLIER} katı finansal özgürlük hedefinizi oluşturur.
              </p>

              {/* Para birimi seçici */}
              <div>
                <label className="block text-xs text-gray-500 mb-2">Para birimi</label>
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
                  Aylık ihtiyaç ({currency})
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
                    {saving ? "Kaydediliyor..." : saved ? "✓ Kaydedildi" : "Kaydet"}
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
                    Finansal özgürlük hedefi:
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
                  <h2 className="text-sm font-semibold text-gray-700">İlerleme durumu</h2>
                  <div className="text-right">
                    <p className="text-xs text-gray-400">Kaydedilen hedef</p>
                    <p className="text-sm font-semibold text-gray-700">
                      {fmtForeign(amount, goal!.goal_currency as GoalCurrency)}/ay
                    </p>
                    {isForeign && (
                      <p className="text-xs text-gray-400">= {fmtTL(monthlyTL)} ₺/ay</p>
                    )}
                  </div>
                </div>

                {portfolio ? (
                  <>
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs text-gray-500">
                        <span>Mevcut portföy</span>
                        <span className="font-semibold text-gray-800">{fmtTL(portfolio)} ₺</span>
                      </div>
                      <ProgressBar pct={pct ?? 0} />
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-400">%{(pct ?? 0).toFixed(1)} tamamlandı</span>
                        <span className="text-gray-400">Hedef: {fmtTL(targetTL)} ₺</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <Stat
                        label="Aylık pasif gelir (TL)"
                        value={`${fmtTL(passiveTL!)} ₺`}
                        sub="portföy ÷ 300"
                        color="text-violet-600"
                      />
                      {isForeign && passiveFgn !== null && rate && (
                        <Stat
                          label={`Aylık pasif gelir (${goal!.goal_currency})`}
                          value={fmtForeign(passiveFgn, goal!.goal_currency as GoalCurrency)}
                          sub={`1 ${goal!.goal_currency} = ${fmtTL(rate)} ₺`}
                          color="text-blue-600"
                        />
                      )}
                      <Stat
                        label="Hedefe kalan"
                        value={`${fmtTL(Math.max(0, targetTL - portfolio))} ₺`}
                        sub={pct! >= 100 ? "Hedefe ulaşıldı 🎉" : `%${(100 - pct!).toFixed(1)} eksik`}
                        color={pct! >= 100 ? "text-green-600" : "text-gray-700"}
                      />
                      <Stat
                        label="Portföy kaç ay karşılıyor"
                        value={`${months?.toFixed(0)} ay`}
                        sub={`${((months ?? 0) / 12).toFixed(1)} yıl`}
                        color="text-indigo-600"
                      />
                      <Stat
                        label="Pasif gelir vs ihtiyaç"
                        value={
                          isForeign && passiveFgn !== null
                            ? (passiveFgn >= amount ? "Finansal özgür 🎉" : `${fmtForeign(amount - passiveFgn, goal!.goal_currency as GoalCurrency)} eksik`)
                            : (passiveTL! >= monthlyTL ? "Finansal özgür 🎉" : `${fmtTL(monthlyTL - passiveTL!)} ₺ eksik`)
                        }
                        sub={
                          (isForeign ? passiveFgn! >= amount : passiveTL! >= monthlyTL)
                            ? "Pasif geliriniz ihtiyacı karşılıyor"
                            : "Pasif gelir henüz yeterli değil"
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
                    Portföy verisi yok — dashboard&apos;dan bir snapshot al, ardından ilerleme hesaplanır.
                  </p>
                )}
              </div>
            )}

            {/* Formül */}
            <div className="bg-violet-50 rounded-2xl border border-violet-100 p-5 text-xs text-violet-700 space-y-1">
              <p className="font-semibold mb-2">Finansal özgürlük formülü</p>
              <p>Hedef = Aylık ihtiyaç × {MULTIPLIER}</p>
              <p>Aylık pasif gelir = Portföy ÷ {MULTIPLIER}</p>
              {goal?.rate_to_tl && goal.goal_currency !== "TRY" && (
                <p>Güncel kur (TCMB): 1 {goal.goal_currency} = {fmtTL(parseFloat(goal.rate_to_tl))} ₺</p>
              )}
              <p className="pt-1 text-violet-500">
                {MULTIPLIER} ay = 25 yıllık sürdürülebilir çekim oranı (%4 kuralı).
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
