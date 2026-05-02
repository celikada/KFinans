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
  return currency === "TRY"
    ? `${val.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ₺`
    : `${sym}${val.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
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
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [currency, setCurrency] = useState<GoalCurrency>("USD");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getGoal();
      setGoal(data);
      if (data.goal_amount) setInputVal(data.goal_amount);
      if (data.goal_currency) setCurrency(data.goal_currency);
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
    try {
      const data = await api.setGoal(val, currency);
      setGoal(data);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  const amount       = goal?.goal_amount       ? parseFloat(goal.goal_amount)       : null;
  const cur          = (goal?.goal_currency ?? currency) as GoalCurrency;
  const rate         = goal?.rate_to_tl        ? parseFloat(goal.rate_to_tl)        : null;
  const monthlyTL    = goal?.monthly_tl        ? parseFloat(goal.monthly_tl)        : null;
  const targetTL     = goal?.freedom_target_tl ? parseFloat(goal.freedom_target_tl) : null;
  const portfolio    = goal?.portfolio_value   ? parseFloat(goal.portfolio_value)   : null;
  const passiveTL    = goal?.passive_income_tl ? parseFloat(goal.passive_income_tl) : null;
  const passiveFgn   = goal?.passive_income_foreign ? parseFloat(goal.passive_income_foreign) : null;
  const pct          = goal?.progress_pct ?? null;
  const months       = goal?.months_covered ?? null;
  const isForeign    = cur !== "TRY";

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Finansal Hedef" />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {loading && <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>}

        {!loading && (
          <>
            {/* Hedef girişi */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Aylık finansal özgürlük ihtiyacı</h2>

              {!editing && amount ? (
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-3xl font-bold text-gray-900">
                      {fmtForeign(amount, cur)}
                      <span className="text-base font-normal text-gray-400"> / ay</span>
                    </p>
                    {isForeign && monthlyTL && rate && (
                      <p className="text-sm text-gray-500 mt-1">
                        = {fmtTL(monthlyTL)} ₺/ay
                        <span className="text-xs text-gray-400 ml-2">(1 {cur} = {fmtTL(rate)} ₺)</span>
                      </p>
                    )}
                    {targetTL && (
                      <p className="text-xs text-gray-400 mt-2">
                        Hedef: <span className="font-medium text-gray-600">{fmtTL(targetTL)} ₺</span>
                        {isForeign && amount && (
                          <span className="ml-1">({fmtForeign(amount * MULTIPLIER, cur)})</span>
                        )}
                        <span className="ml-1 text-gray-300">({MULTIPLIER}× aylık)</span>
                      </p>
                    )}
                  </div>
                  <button onClick={() => setEditing(true)} className="text-sm text-indigo-600 hover:text-indigo-800 shrink-0">
                    Düzenle
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">
                    Bu değerin {MULTIPLIER} katı finansal özgürlük hedefinizi oluşturur.
                  </p>
                  <div className="flex gap-2">
                    {/* Para birimi seçici */}
                    <div className="flex rounded-lg border border-gray-200 overflow-hidden shrink-0">
                      {CURRENCIES.map((c) => (
                        <button
                          key={c}
                          type="button"
                          onClick={() => setCurrency(c)}
                          className={`px-3 py-2 text-xs font-medium transition-colors ${
                            currency === c
                              ? "bg-violet-600 text-white"
                              : "bg-white text-gray-500 hover:bg-gray-50"
                          }`}
                        >
                          {GOAL_CURRENCY_SYMBOLS[c]} {c}
                        </button>
                      ))}
                    </div>
                    <input
                      type="number"
                      min="1"
                      step="100"
                      className={`${INPUT_CLS} flex-1`}
                      placeholder={currency === "TRY" ? "örn. 50000" : "örn. 3000"}
                      value={inputVal}
                      onChange={(e) => setInputVal(e.target.value)}
                    />
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="text-sm bg-violet-600 text-white px-4 py-2 rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors shrink-0"
                    >
                      {saving ? "..." : "Kaydet"}
                    </button>
                  </div>
                  {error && <p className="text-xs text-red-500">{error}</p>}
                </div>
              )}
            </div>

            {/* İlerleme */}
            {amount && targetTL && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
                <h2 className="text-sm font-semibold text-gray-700">İlerleme durumu</h2>

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

                    <div className="grid grid-cols-2 gap-4 pt-2">
                      <Stat
                        label="Aylık pasif gelir (TL)"
                        value={`${fmtTL(passiveTL!)} ₺`}
                        sub="portföy ÷ 300"
                        color="text-violet-600"
                      />
                      {isForeign && passiveFgn !== null && (
                        <Stat
                          label={`Aylık pasif gelir (${cur})`}
                          value={fmtForeign(passiveFgn, cur)}
                          sub={`${fmtTL(passiveTL!)} ₺ ÷ ${fmtTL(rate!)} ₺/${cur}`}
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
                            ? (passiveFgn >= amount! ? "Finansal özgür 🎉" : `${fmtForeign(amount! - passiveFgn, cur)} eksik`)
                            : (passiveTL! >= (monthlyTL ?? 0) ? "Finansal özgür 🎉" : `${fmtTL((monthlyTL ?? 0) - passiveTL!)} ₺ eksik`)
                        }
                        sub={
                          (isForeign ? passiveFgn! >= amount! : passiveTL! >= (monthlyTL ?? 0))
                            ? "Pasif geliriniz ihtiyacı karşılıyor"
                            : "Pasif gelir henüz yeterli değil"
                        }
                        color={
                          (isForeign ? passiveFgn! >= amount! : passiveTL! >= (monthlyTL ?? 0))
                            ? "text-green-600" : "text-orange-500"
                        }
                      />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-400 py-2">
                    Portföy verisi yok — bir snapshot al, ardından ilerleme hesaplanır.
                  </p>
                )}
              </div>
            )}

            {/* Formül */}
            <div className="bg-violet-50 rounded-2xl border border-violet-100 p-5 text-xs text-violet-700 space-y-1">
              <p className="font-semibold mb-2">Finansal özgürlük formülü</p>
              <p>Hedef = Aylık ihtiyaç × {MULTIPLIER}</p>
              <p>Aylık pasif gelir = Portföy ÷ {MULTIPLIER}</p>
              {isForeign && rate && (
                <p>Güncel kur: 1 {cur} = {fmtTL(rate)} ₺ (TCMB)</p>
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
