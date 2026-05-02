"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, GoalDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL } from "@/lib/format";
import { INPUT_CLS } from "@/lib/format";

const MULTIPLIER = 300;

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.min(pct, 100);
  const color =
    clamped >= 100 ? "bg-green-500" :
    clamped >= 70  ? "bg-blue-500"  :
    clamped >= 40  ? "bg-indigo-500" :
                     "bg-violet-400";
  return (
    <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${color}`}
        style={{ width: `${clamped}%` }}
      />
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
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getGoal();
      setGoal(data);
      if (data.monthly_expense_goal) setInputVal(data.monthly_expense_goal);
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
      const data = await api.setGoal(val);
      setGoal(data);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  const monthly   = goal?.monthly_expense_goal ? parseFloat(goal.monthly_expense_goal) : null;
  const target    = goal?.freedom_target        ? parseFloat(goal.freedom_target)        : null;
  const portfolio = goal?.portfolio_value       ? parseFloat(goal.portfolio_value)       : null;
  const passive   = goal?.passive_income_potential ? parseFloat(goal.passive_income_potential) : null;
  const pct       = goal?.progress_pct ?? null;
  const months    = goal?.months_covered ?? null;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Finansal Hedef" />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {loading && <p className="text-sm text-gray-400 text-center py-8">Yükleniyor...</p>}

        {!loading && (
          <>
            {/* Hedef girişi */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Aylık finansal özgürlük ihtiyacı
              </h2>

              {!editing && monthly ? (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-bold text-gray-900">{fmtTL(monthly)} ₺<span className="text-base font-normal text-gray-400"> / ay</span></p>
                    <p className="text-xs text-gray-400 mt-1">Hedef: {fmtTL(target!)} ₺ ({MULTIPLIER}× aylık ihtiyaç)</p>
                  </div>
                  <button
                    onClick={() => setEditing(true)}
                    className="text-sm text-indigo-600 hover:text-indigo-800"
                  >
                    Düzenle
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">
                    Bu değerin {MULTIPLIER} katı finansal özgürlük hedefinizi oluşturur.
                  </p>
                  <div className="flex gap-3">
                    <input
                      type="number"
                      min="1"
                      step="1000"
                      className={`${INPUT_CLS} flex-1`}
                      placeholder="örn. 50000"
                      value={inputVal}
                      onChange={(e) => setInputVal(e.target.value)}
                    />
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="text-sm bg-violet-600 text-white px-4 py-2 rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
                    >
                      {saving ? "Kaydediliyor..." : "Kaydet"}
                    </button>
                  </div>
                  {error && <p className="text-xs text-red-500">{error}</p>}
                </div>
              )}
            </div>

            {/* İlerleme */}
            {monthly && target && (
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
                        <span className="text-gray-400">Hedef: {fmtTL(target)} ₺</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 pt-2">
                      <Stat
                        label="Aylık pasif gelir potansiyeli"
                        value={`${fmtTL(passive!)} ₺`}
                        sub="portföy ÷ 300"
                        color="text-violet-600"
                      />
                      <Stat
                        label="Hedefe kalan"
                        value={`${fmtTL(target - portfolio)} ₺`}
                        sub={pct! >= 100 ? "Hedefe ulaşıldı 🎉" : `%${(100 - pct!).toFixed(1)} eksik`}
                        color={pct! >= 100 ? "text-green-600" : "text-gray-700"}
                      />
                      <Stat
                        label="Kaç ay karşılıyor"
                        value={`${months?.toFixed(0)} ay`}
                        sub={`${(months! / 12).toFixed(1)} yıl`}
                        color="text-blue-600"
                      />
                      <Stat
                        label="Aylık ihtiyaç / pasif gelir"
                        value={passive! >= monthly
                          ? "Finansal özgür 🎉"
                          : `${fmtTL(monthly - passive!)} ₺ eksik`}
                        sub={passive! >= monthly
                          ? "Pasif geliriniz ihtiyacı karşılıyor"
                          : "Pasif gelir henüz yeterli değil"}
                        color={passive! >= monthly ? "text-green-600" : "text-orange-500"}
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

            {/* Formül açıklaması */}
            <div className="bg-violet-50 rounded-2xl border border-violet-100 p-5 text-xs text-violet-700 space-y-1">
              <p className="font-semibold mb-2">Finansal özgürlük formülü</p>
              <p>Hedef = Aylık ihtiyaç × {MULTIPLIER}</p>
              <p>Aylık pasif gelir potansiyeli = Portföy ÷ {MULTIPLIER}</p>
              <p className="pt-1 text-violet-500">
                Bu formül, portföyün yılda ~%4 reel getiri sağlayacağı varsayımına dayanır
                ({MULTIPLIER} ay = 25 yıllık sürdürülebilir çekim oranı).
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
