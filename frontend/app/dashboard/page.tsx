"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, clearAuth, EXPENSE_CATEGORY_LABELS, INCOME_CATEGORY_LABELS, MONTH_NAMES } from "@/lib/api";
import type { BudgetComparisonDTO } from "@/lib/api";
import { getHiddenCards, type DashboardCardId } from "@/lib/format";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { TLValue, useUsdRate } from "@/app/_components/TLValue";
import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";
import { useTranslation } from "@/app/_i18n/I18nProvider";

// FE-003 (FAZ H): page.tsx 970+ satirdi; dashboard kart bilesenleri ve
// snapshot uyari modal'i ayri _components/ modullerine tasindi.
import { Card, GoalCard, BudgetCard, type TopItem } from "./_components/DashboardCard";
import { SnapshotIssuesModal, type PendingIssues } from "./_components/SnapshotIssuesModal";


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function top3<T>(items: T[], valueFn: (i: T) => number, labelFn: (i: T) => string): TopItem[] {
  return [...items]
    .sort((a, b) => valueFn(b) - valueFn(a))
    .slice(0, 3)
    .map((i) => ({ label: labelFn(i), value: valueFn(i) }));
}

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useTranslation();

  // TEFAS
  const [tefasTotal, setTefasTotal] = useState<number | null>(null);
  const [tefasFundCount, setTefasFundCount] = useState(0);
  const [tefasTop, setTefasTop] = useState<TopItem[]>([]);

  // Kripto
  const [cryptoTotal, setCryptoTotal] = useState<number | null>(null);
  const [cryptoLoading, setCryptoLoading] = useState(false);
  const [cryptoTop, setCryptoTop] = useState<TopItem[]>([]);

  // Hisse senedi
  const [stockTotal, setStockTotal] = useState<number | null>(null);
  const [stockHoldingCount, setStockHoldingCount] = useState(0);
  const [stockTop, setStockTop] = useState<TopItem[]>([]);

  // Blockchain (cüzdan)
  const [walletTotal, setWalletTotal] = useState<number | null>(null);
  const [walletLoading, setWalletLoading] = useState(false);
  const [walletTop, setWalletTop] = useState<TopItem[]>([]);

  // BES
  const [besTotal, setBesTotal] = useState<number | null>(null);
  const [besPlanCount, setBesPlanCount] = useState(0);
  const [besTop, setBesTop] = useState<TopItem[]>([]);

  // Harcama (bu ay)
  const [expenseTotal, setExpenseTotal] = useState<number | null>(null);
  const [expenseCount, setExpenseCount] = useState(0);
  const [expenseTop, setExpenseTop] = useState<TopItem[]>([]);

  // Planlı ödemeler (bu yıl)
  const [plannedTotal, setPlannedTotal] = useState<number | null>(null);

  // Gelir (bu ay)
  const [incomeTotal, setIncomeTotal] = useState<number | null>(null);
  const [incomeYearEstimate, setIncomeYearEstimate] = useState<number | null>(null);

  // Kredi kartları (toplam borç + dönem içi borç)
  const [creditCardTotal, setCreditCardTotal] = useState<number | null>(null);
  const [creditCardPeriod, setCreditCardPeriod] = useState<number | null>(null);
  const [creditCardCount, setCreditCardCount] = useState(0);
  const [incomeCount, setIncomeCount] = useState(0);
  const [incomeTop, setIncomeTop] = useState<TopItem[]>([]);

  // Kıymetli madenler
  const [commodityTotal, setCommodityTotal] = useState<number | null>(null);
  const [cashTotal, setCashTotal] = useState<number | null>(null);
  const [cashCount, setCashCount] = useState(0);
  const [commodityCount, setCommodityCount] = useState(0);

  // Manuel kripto (API'siz borsalar)
  const [manualCryptoTotal, setManualCryptoTotal] = useState<number | null>(null);
  const [manualCryptoCount, setManualCryptoCount] = useState(0);
  const [manualCryptoTop, setManualCryptoTop] = useState<TopItem[]>([]);

  // Bütçe
  const [budgetOverCount, setBudgetOverCount] = useState<number | null>(null);

  // Finans ozeti — bu ay ve gelecek ay net (gelir - gider)
  const [currentMonthNet, setCurrentMonthNet] = useState<number | null>(null);
  const [nextMonthNet, setNextMonthNet] = useState<number | null>(null);

  // Finansal hedef
  const [goalPct, setGoalPct] = useState<number | null>(null);
  const [goalPassive, setGoalPassive] = useState<number | null>(null);

  // Dashboard kart görünürlüğü
  const [hiddenCards, setHiddenCards] = useState<DashboardCardId[]>([]);

  const usdRate = useUsdRate();
  const [prevSnapshot, setPrevSnapshot] = useState<number | null>(null);
  // Snapshot uyarı popup state
  const [pendingIssues, setPendingIssues] = useState<PendingIssues | null>(null);

  // Snapshot tetikleyici
  const [snapshotting, setSnapshotting] = useState(false);
  const [snapshotMsg, setSnapshotMsg] = useState("");

  useEffect(() => {
    setHiddenCards(getHiddenCards());
  }, []);

  useEffect(() => {
    // FE-004 (FAZ H): Dashboard fetch orchestration.
    // Once 14 ayri api.X().then().catch(() => {}) silent error + race condition
    // (component unmount sonrasi setState uyarisi). Yeni yapi:
    //   - cancelled flag: cleanup'ta true; her .then() oncesi kontrol -> race-safe
    //   - safe(): try/catch wrapper, hata console.warn'a (silent degil)
    //   - Promise.allSettled: tum fetch'ler paralel; biri fail digerlerini
    //     bloke etmez; toplu sonuc tek log satirinda
    let cancelled = false;
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = now.getMonth() + 1;
    const isDecember = mm === 12;

    function safeSet<T>(setter: (v: T) => void): (v: T) => void {
      return (v) => { if (!cancelled) setter(v); };
    }

    async function safe<T>(label: string, fn: () => Promise<T>): Promise<T | null> {
      try {
        return await fn();
      } catch (err) {
        if (!cancelled) console.warn(`[dashboard:${label}]`, err);
        return null;
      }
    }

    setCryptoLoading(true);
    setWalletLoading(true);

    const tasks: Promise<unknown>[] = [
      // TEFAS: holdings -> preview chain
      safe("tefas", async () => {
        const holdings = await api.getTefasHoldings();
        if (!holdings.length) return;
        safeSet(setTefasFundCount)(holdings.length);
        const positions = await api.tefasPreview(holdings);
        const total = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        safeSet(setTefasTotal)(total);
        safeSet(setTefasTop)(top3(positions, (p) => parseFloat(p.total_value_tl), (p) => p.code));
      }),

      // Kripto (Binance/iCrypex)
      safe("crypto", async () => {
        const { positions } = await api.getCryptoPositions();
        const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
        if (filtered.length === 0) return;
        const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        safeSet(setCryptoTotal)(total);
        safeSet(setCryptoTop)(top3(filtered, (p) => parseFloat(p.total_value_tl), (p) => p.symbol));
      }).finally(() => { if (!cancelled) setCryptoLoading(false); }),

      // Hisse senedi: holdings -> preview chain
      safe("stocks", async () => {
        const holdings = await api.getStockHoldings();
        if (!holdings.length) return;
        safeSet(setStockHoldingCount)(holdings.length);
        const positions = await api.stockPreview(holdings);
        const total = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        safeSet(setStockTotal)(total);
        safeSet(setStockTop)(top3(positions, (p) => parseFloat(p.total_value_tl), (p) => p.ticker));
      }),

      // Blockchain cüzdanlar
      safe("wallets", async () => {
        const { positions } = await api.getWalletPositions();
        const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
        if (filtered.length === 0) return;
        const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        safeSet(setWalletTotal)(total);
        safeSet(setWalletTop)(top3(filtered, (p) => parseFloat(p.total_value_tl), (p) => p.symbol));
      }).finally(() => { if (!cancelled) setWalletLoading(false); }),

      // BES
      safe("bes", async () => {
        const holdings = await api.getBesHoldings();
        if (!holdings.length) return;
        safeSet(setBesPlanCount)(holdings.length);
        const items = holdings.map((h) => ({
          plan_name: h.plan_name,
          total:
            (parseFloat(h.paid_principal.toString()) || 0) +
            (parseFloat(h.paid_returns.toString()) || 0) +
            (parseFloat(h.govt_contribution.toString()) || 0) +
            (parseFloat(h.govt_returns.toString()) || 0),
        }));
        const total = items.reduce((s, i) => s + i.total, 0);
        safeSet(setBesTotal)(total);
        safeSet(setBesTop)(top3(items, (i) => i.total, (i) => i.plan_name));
      }),

      // Gelir özeti (bu ay)
      safe("income-summary", async () => {
        const sum = await api.getIncomeSummary(yyyy, mm);
        if (sum.count === 0) return;
        safeSet(setIncomeTotal)(parseFloat(sum.total));
        safeSet(setIncomeCount)(sum.count);
        safeSet(setIncomeTop)(top3(
          sum.by_category,
          (b) => parseFloat(b.total),
          (b) => INCOME_CATEGORY_LABELS[b.category as keyof typeof INCOME_CATEGORY_LABELS] ?? b.category,
        ));
      }),

      // Gelir dashboard (yıl sonu beklentisi)
      safe("income-dashboard", async () => {
        const d = await api.getIncomeDashboard(yyyy, mm);
        const est = parseFloat(d.year_total_estimate);
        if (est > 0) safeSet(setIncomeYearEstimate)(est);
      }),

      // Cash flow (bu ay + gelecek ay net)
      safe("cash-flow", async () => {
        const fetches = [api.getCashFlow(yyyy)];
        if (isDecember) fetches.push(api.getCashFlow(yyyy + 1));
        const [thisYear, nextYear] = await Promise.all(fetches);
        const thisMonth = thisYear.months.find((m) => m.month === mm);
        if (thisMonth) safeSet(setCurrentMonthNet)(parseFloat(thisMonth.net));
        const nextMonthData = isDecember
          ? nextYear?.months.find((m) => m.month === 1)
          : thisYear.months.find((m) => m.month === mm + 1);
        if (nextMonthData) safeSet(setNextMonthNet)(parseFloat(nextMonthData.net));
      }),

      // Kredi kartları
      safe("credit-cards", async () => {
        const s = await api.listCreditCards();
        safeSet(setCreditCardTotal)(parseFloat(s.total_debt));
        safeSet(setCreditCardPeriod)(parseFloat(s.total_period_debt));
        safeSet(setCreditCardCount)(s.cards.length);
      }),

      // Kıymetli madenler
      safe("commodities", async () => {
        const s = await api.getCommodities();
        const total = parseFloat(s.total_value_tl);
        if (s.positions.length > 0) {
          safeSet(setCommodityTotal)(total);
          safeSet(setCommodityCount)(s.positions.length);
        }
      }),

      // Nakit / Banka
      safe("cash", async () => {
        const s = await api.listCash();
        const total = parseFloat(s.total_tl);
        if (s.holdings.length > 0) {
          safeSet(setCashTotal)(total);
          safeSet(setCashCount)(s.holdings.length);
        }
      }),

      // Manuel kripto
      safe("manual-crypto", async () => {
        const s = await api.listManualCrypto();
        const total = parseFloat(s.total_value_tl);
        if (s.positions.length > 0) {
          safeSet(setManualCryptoTotal)(total);
          safeSet(setManualCryptoCount)(s.positions.length);
          safeSet(setManualCryptoTop)(top3(
            s.positions,
            (p) => parseFloat(p.total_value_tl),
            (p) => p.symbol,
          ));
        }
      }),

      // Bütçe karşılaştırma
      safe("budget", async () => {
        const rows = await api.getBudgetComparison(yyyy, mm);
        const overCount = rows.filter((r: BudgetComparisonDTO) => r.over_budget).length;
        safeSet(setBudgetOverCount)(overCount);
      }),

      // Finansal hedef
      safe("goal", async () => {
        const g = await api.getGoal();
        if (g.progress_pct !== null) safeSet(setGoalPct)(g.progress_pct);
        if (g.passive_income_tl) safeSet(setGoalPassive)(parseFloat(g.passive_income_tl));
      }),

      // Planlı ödemeler (yıllık tahmin)
      safe("planned", async () => {
        const fc = await api.getForecast(yyyy);
        const total = parseFloat(fc.year_total);
        if (total > 0) safeSet(setPlannedTotal)(total);
      }),

      // Harcama özeti (bu ay)
      safe("expenses", async () => {
        const sum = await api.getExpenseSummary(yyyy, mm);
        if (sum.count === 0) return;
        safeSet(setExpenseTotal)(parseFloat(sum.total));
        safeSet(setExpenseCount)(sum.count);
        safeSet(setExpenseTop)(top3(
          sum.by_category,
          (b) => parseFloat(b.total),
          (b) => EXPENSE_CATEGORY_LABELS[b.category] ?? b.category,
        ));
      }),
    ];

    // Tum fetch'lerin tamamlanmasini bekle (orchestration sonu telemetri)
    Promise.allSettled(tasks).then((results) => {
      if (cancelled) return;
      const failed = results.filter((r) => r.status === "rejected").length;
      if (failed > 0) {
        console.warn(`[dashboard] ${failed}/${tasks.length} fetch fail`);
      }
    });

    return () => { cancelled = true; };
  }, [router]);

  async function logout() {
    try {
      await api.logout();
    } catch {
      // Backend ulasilamasa bile lokal session temizlenmeli
    }
    clearAuth();
    router.push("/login");
  }

  function buildSnapshotMsg(total: number, count: number, issuesLen: number): string {
    const usdPart = usdRate && usdRate > 0
      ? ` ≈ $${(total / usdRate).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
      : "";
    let diffPart = "";
    if (prevSnapshot !== null && prevSnapshot > 0) {
      const diffTL = total - prevSnapshot;
      const sign = diffTL >= 0 ? "+" : "";
      const diffUsd = usdRate && usdRate > 0
        ? ` (${sign}$${(diffTL / usdRate).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })})`
        : "";
      diffPart = `, değişim: ${sign}${fmtTL(diffTL)} ₺${diffUsd}`;
    }
    const warnPart = issuesLen > 0
      ? ` ⚠ ${issuesLen} sorun kaydedildi`
      : "";
    return `✓ Snapshot: ${fmtTL(total)} ₺${usdPart} (${count} pozisyon)${diffPart}${warnPart}`;
  }

  async function saveConfirmedSnapshot() {
    setSnapshotting(true);
    setSnapshotMsg("");
    try {
      const snap = await api.createSnapshot(true);
      const total = parseFloat(snap.total_value_tl);
      setPrevSnapshot(total);
      const issues = snap.health_issues ?? [];
      setSnapshotMsg(buildSnapshotMsg(total, snap.asset_positions.length, issues.length));
      setPendingIssues(null);
    } catch (err) {
      setSnapshotMsg(err instanceof Error ? `Hata: ${err.message}` : "Snapshot başarısız");
    } finally {
      setSnapshotting(false);
    }
  }

  async function takeSnapshot() {
    setSnapshotting(true);
    setSnapshotMsg("");
    try {
      // 1) Preview — issues var mı? (preview ASLA DB'ye yazmaz)
      const preview = await api.previewSnapshot();
      if (preview.issues.length > 0) {
        // Onay popup'ı — kullanıcı 'Yine de kaydet' derse saveConfirmedSnapshot çağırır
        const total = parseFloat(preview.total_value_tl);
        setPendingIssues({ issues: preview.issues, total });
        setSnapshotting(false);
        return;
      }
      // Sorunsuz → doğrudan kaydet (force gerekmez)
      const snap = await api.createSnapshot(false);
      const total = parseFloat(snap.total_value_tl);
      setPrevSnapshot(total);
      setSnapshotMsg(buildSnapshotMsg(total, snap.asset_positions.length, 0));
    } catch (err) {
      setSnapshotMsg(err instanceof Error ? `Hata: ${err.message}` : "Snapshot başarısız");
    } finally {
      setSnapshotting(false);
    }
  }

  // Toplam portföy değeri (kartlar yüklendikçe artar)
  const grandTotal =
    (tefasTotal ?? 0) +
    (cryptoTotal ?? 0) +
    (stockTotal ?? 0) +
    (walletTotal ?? 0) +
    (besTotal ?? 0) +
    (commodityTotal ?? 0) +
    (cashTotal ?? 0) +
    (manualCryptoTotal ?? 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <KFinansLogo />
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <button
            onClick={() => router.push("/dashboard/settings")}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            {t("common.settings")}
          </button>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">
            {t("auth.logout")}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="grid gap-6 sm:grid-cols-2 mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1 flex items-center gap-2">
              {t("dashboard.totalPortfolio")}
              {(cryptoLoading || walletLoading) && (
                <span className="inline-flex items-center gap-1 text-[10px] font-normal text-gray-400 normal-case tracking-normal">
                  <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                  {t("common.loading")}
                </span>
              )}
            </p>
            {grandTotal > 0 ? (
              <TLValue tl={grandTotal} className="text-3xl font-bold text-gray-900 tabular-nums" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
            ) : (
              <p className="text-3xl font-bold text-gray-300">—</p>
            )}
          </div>

          {/* Finans ozeti: bu ay + gelecek ay net (gelir - gider) */}
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1">{t("dashboard.financeNetBalance")}</p>
            <div className="flex items-baseline gap-6">
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{t(`months.${new Date().getMonth() + 1}`)}</p>
                {currentMonthNet !== null ? (
                  <p className={`text-2xl font-bold tabular-nums ${currentMonthNet >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {currentMonthNet >= 0 ? "+" : ""}{fmtTL(currentMonthNet)} ₺
                  </p>
                ) : (
                  <p className="text-2xl font-bold text-gray-300">—</p>
                )}
              </div>
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{t(`months.${((new Date().getMonth() + 1) % 12) + 1}`)}</p>
                {nextMonthNet !== null ? (
                  <p className={`text-2xl font-bold tabular-nums ${nextMonthNet >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {nextMonthNet >= 0 ? "+" : ""}{fmtTL(nextMonthNet)} ₺
                  </p>
                ) : (
                  <p className="text-2xl font-bold text-gray-300">—</p>
                )}
              </div>
            </div>
          </div>
        </div>
        {snapshotMsg && (
          <p className="text-xs text-gray-500 bg-gray-50 border border-gray-100 px-3 py-2 rounded-lg mb-4">{snapshotMsg}</p>
        )}

        {/* FINANS GRUBU (yukarida) */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">{t("dashboard.finance")}</h2>
            <button
              onClick={() => router.push("/dashboard/cash-flow")}
              className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
            >
              {t("dashboard.cashFlow")}
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {!hiddenCards.includes("creditCards") && (
              <Card
                href="/dashboard/credit-cards"
                icon="creditCard"
                color="red"
                title={t("dashboard.cards.creditCards")}
                total={creditCardTotal}
                count={creditCardCount}
                countLabel={t("dashboard.card")}
                top={[]}
                placeholder={t("dashboard.cards.creditCardsHint")}
                footer={creditCardPeriod !== null && (
                  <span>{t("dashboard.currentPeriodDebt")}: <span className="font-semibold text-gray-700">{fmtTL(creditCardPeriod)} ₺</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("income") && (
              <Card
                href="/dashboard/income"
                icon="income"
                color="emerald"
                title={t("dashboard.cards.income")}
                total={incomeTotal}
                count={incomeCount}
                countLabel={t("dashboard.record")}
                top={incomeTop}
                placeholder={t("dashboard.cards.incomeHint")}
                footer={incomeYearEstimate !== null && (
                  <span>{t("dashboard.yearEndExpectation")}: <span className="font-semibold text-gray-700">{fmtTL(incomeYearEstimate)} ₺</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("expenses") && (
              <Card
                href="/dashboard/expenses"
                icon="expenses"
                color="red"
                title={t("dashboard.cards.expenses")}
                total={expenseTotal}
                count={expenseCount}
                countLabel={t("dashboard.record")}
                top={expenseTop}
                placeholder={t("dashboard.cards.expensesHint")}
              />
            )}

            {!hiddenCards.includes("planned") && (
              <Card
                href="/dashboard/planned"
                icon="planned"
                color="violet"
                title={t("dashboard.cards.planned")}
                total={plannedTotal}
                top={[]}
                placeholder={t("dashboard.cards.plannedHint")}
              />
            )}

            {!hiddenCards.includes("budget") && (
              <BudgetCard href="/dashboard/budget" overCount={budgetOverCount} />
            )}

            {!hiddenCards.includes("goal") && (
              <GoalCard href="/dashboard/goal" pct={goalPct} passive={goalPassive} />
            )}
          </div>
        </section>

        {/* PORTFÖY GRUBU (asagida) */}
        <section className="space-y-3 mt-8">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">{t("dashboard.portfolio")}</h2>
            <div className="flex gap-2">
              <button
                onClick={() => router.push("/dashboard/history")}
                className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
              >
                {t("dashboard.history")}
              </button>
              <button
                onClick={takeSnapshot}
                disabled={snapshotting}
                className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                {snapshotting ? t("dashboard.snapshotting") : t("dashboard.snapshot")}
              </button>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {!hiddenCards.includes("bes") && (
              <Card
                href="/dashboard/bes"
                icon="bes"
                color="green"
                title={t("dashboard.cards.bes")}
                total={besTotal}
                count={besPlanCount}
                countLabel={t("dashboard.plan")}
                top={besTop}
                placeholder={t("dashboard.cards.besHint")}
              />
            )}

            {!hiddenCards.includes("tefas") && (
              <Card
                href="/dashboard/tefas"
                icon="tefas"
                color="blue"
                title={t("dashboard.cards.tefas")}
                total={tefasTotal}
                count={tefasFundCount}
                countLabel={t("dashboard.fund")}
                top={tefasTop}
                placeholder={t("dashboard.cards.tefasHint")}
              />
            )}

            {!hiddenCards.includes("stocks") && (
              <Card
                href="/dashboard/stocks"
                icon="stocks"
                color="indigo"
                title={t("dashboard.cards.stocks")}
                total={stockTotal}
                count={stockHoldingCount}
                countLabel={t("dashboard.stock")}
                top={stockTop}
                placeholder={t("dashboard.cards.stocksHint")}
              />
            )}

            {!hiddenCards.includes("wallets") && (
              <Card
                href="/dashboard/wallets"
                icon="wallets"
                color="purple"
                title={t("dashboard.cards.wallets")}
                total={walletTotal}
                loading={walletLoading}
                top={walletTop}
                placeholder={t("dashboard.cards.walletsHint")}
              />
            )}

            {!hiddenCards.includes("crypto") && (
              <Card
                href="/dashboard/crypto"
                icon="crypto"
                color="orange"
                title={t("dashboard.cards.crypto")}
                total={cryptoTotal}
                loading={cryptoLoading}
                top={cryptoTop}
                placeholder={t("dashboard.cards.cryptoHint")}
              />
            )}

            {!hiddenCards.includes("manualCrypto") && (
              <Card
                href="/dashboard/manual-crypto"
                icon="crypto"
                color="orange"
                title={t("dashboard.cards.manualCrypto")}
                total={manualCryptoTotal}
                count={manualCryptoCount}
                countLabel={t("dashboard.position")}
                top={manualCryptoTop}
                placeholder={t("dashboard.cards.manualCryptoHint")}
              />
            )}

            {!hiddenCards.includes("commodities") && (
              <Card
                href="/dashboard/commodities"
                icon="commodities"
                color="amber"
                title={t("dashboard.cards.commodities")}
                total={commodityTotal}
                count={commodityCount}
                countLabel={t("dashboard.position")}
                top={[]}
                placeholder={t("dashboard.cards.commoditiesHint")}
              />
            )}

            {!hiddenCards.includes("cash") && (
              <Card
                href="/dashboard/cash"
                icon="cash"
                color="green"
                title={t("dashboard.cards.cash")}
                total={cashTotal}
                count={cashCount}
                countLabel={t("dashboard.record")}
                top={[]}
                placeholder={t("dashboard.cards.cashHint")}
              />
            )}
          </div>
        </section>
      </main>

      {/* FE-003: Snapshot uyari modal'i — extract edildi */}
      {pendingIssues && (
        <SnapshotIssuesModal
          pending={pendingIssues}
          onCancel={() => setPendingIssues(null)}
          onConfirm={saveConfirmedSnapshot}
          saving={snapshotting}
        />
      )}

      <footer className="mt-auto py-4 flex flex-col items-center gap-2">
        <div className="flex justify-center items-center gap-2">
          <span className="text-xs text-gray-300">Bir</span>
          <MayotekLogo />
          <span className="text-xs text-gray-300">ürünüdür</span>
        </div>
        <div className="flex gap-3 text-xs text-gray-300">
          <Link href="/legal/kvkk" className="hover:text-gray-500">KVKK</Link>
          <Link href="/legal/privacy" className="hover:text-gray-500">Gizlilik</Link>
          <Link href="/legal/terms" className="hover:text-gray-500">Şartlar</Link>
          <Link href="/legal/cookies" className="hover:text-gray-500">Çerezler</Link>
        </div>
      </footer>
    </div>
  );
}

