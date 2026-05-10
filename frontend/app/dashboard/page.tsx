"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, clearAuth, EXPENSE_CATEGORY_LABELS, INCOME_CATEGORY_LABELS, MONTH_NAMES } from "@/lib/api";
import type { BudgetComparisonDTO } from "@/lib/api";
import { getHiddenCards, type DashboardCardId } from "@/lib/format";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { TLValue, useUsdRate } from "@/app/_components/TLValue";

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
    api.getTefasHoldings().then((holdings) => {
      if (!holdings.length) return;
      setTefasFundCount(holdings.length);
      api.tefasPreview(holdings).then((positions) => {
        const total = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        setTefasTotal(total);
        setTefasTop(top3(positions, (p) => parseFloat(p.total_value_tl), (p) => p.code));
      }).catch(() => {});
    }).catch(() => {});

    setCryptoLoading(true);
    api.getCryptoPositions().then(({ positions }) => {
      const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
      if (filtered.length === 0) return;
      const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
      setCryptoTotal(total);
      setCryptoTop(top3(filtered, (p) => parseFloat(p.total_value_tl), (p) => p.symbol));
    }).catch(() => {}).finally(() => setCryptoLoading(false));

    api.getStockHoldings().then((holdings) => {
      if (!holdings.length) return;
      setStockHoldingCount(holdings.length);
      api.stockPreview(holdings).then((positions) => {
        const total = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        setStockTotal(total);
        setStockTop(top3(positions, (p) => parseFloat(p.total_value_tl), (p) => p.ticker));
      }).catch(() => {});
    }).catch(() => {});

    setWalletLoading(true);
    api.getWalletPositions().then(({ positions }) => {
      const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
      if (filtered.length === 0) return;
      const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
      setWalletTotal(total);
      setWalletTop(top3(filtered, (p) => parseFloat(p.total_value_tl), (p) => p.symbol));
    }).catch(() => {}).finally(() => setWalletLoading(false));

    api.getBesHoldings().then((holdings) => {
      if (!holdings.length) return;
      setBesPlanCount(holdings.length);
      const items = holdings.map((h) => ({
        plan_name: h.plan_name,
        total:
          (parseFloat(h.paid_principal.toString()) || 0) +
          (parseFloat(h.paid_returns.toString()) || 0) +
          (parseFloat(h.govt_contribution.toString()) || 0) +
          (parseFloat(h.govt_returns.toString()) || 0),
      }));
      const total = items.reduce((s, i) => s + i.total, 0);
      setBesTotal(total);
      setBesTop(top3(items, (i) => i.total, (i) => i.plan_name));
    }).catch(() => {});

    const now = new Date();
    api.getIncomeSummary(now.getFullYear(), now.getMonth() + 1).then((sum) => {
      if (sum.count === 0) return;
      setIncomeTotal(parseFloat(sum.total));
      setIncomeCount(sum.count);
      setIncomeTop(top3(
        sum.by_category,
        (b) => parseFloat(b.total),
        (b) => INCOME_CATEGORY_LABELS[b.category as keyof typeof INCOME_CATEGORY_LABELS] ?? b.category,
      ));
    }).catch(() => {});

    api.getIncomeDashboard(now.getFullYear(), now.getMonth() + 1).then((d) => {
      const est = parseFloat(d.year_total_estimate);
      if (est > 0) setIncomeYearEstimate(est);
    }).catch(() => {});

    // Finans ozeti: bu ay ve gelecek ay net (gelir - gider)
    // Aralik ise gelecek ay sonraki yilin Ocak'idir; iki yil paralel cek.
    const currentMonthIdx = now.getMonth() + 1;  // 1-12
    const isDecember = currentMonthIdx === 12;
    const fetches = [api.getCashFlow(now.getFullYear())];
    if (isDecember) fetches.push(api.getCashFlow(now.getFullYear() + 1));
    Promise.all(fetches).then(([thisYear, nextYear]) => {
      const thisMonth = thisYear.months.find((m) => m.month === currentMonthIdx);
      if (thisMonth) setCurrentMonthNet(parseFloat(thisMonth.net));
      const nextMonthData = isDecember
        ? nextYear?.months.find((m) => m.month === 1)
        : thisYear.months.find((m) => m.month === currentMonthIdx + 1);
      if (nextMonthData) setNextMonthNet(parseFloat(nextMonthData.net));
    }).catch(() => {});

    api.listCreditCards().then((s) => {
      setCreditCardTotal(parseFloat(s.total_debt));
      setCreditCardPeriod(parseFloat(s.total_period_debt));
      setCreditCardCount(s.cards.length);
    }).catch(() => {});

    api.getCommodities().then((s) => {
      const total = parseFloat(s.total_value_tl);
      if (s.positions.length > 0) {
        setCommodityTotal(total);
        setCommodityCount(s.positions.length);
      }
    }).catch(() => {});

    api.listCash().then((s) => {
      const total = parseFloat(s.total_tl);
      if (s.holdings.length > 0) {
        setCashTotal(total);
        setCashCount(s.holdings.length);
      }
    }).catch(() => {});

    api.listManualCrypto().then((s) => {
      const total = parseFloat(s.total_value_tl);
      if (s.positions.length > 0) {
        setManualCryptoTotal(total);
        setManualCryptoCount(s.positions.length);
        setManualCryptoTop(top3(
          s.positions,
          (p) => parseFloat(p.total_value_tl),
          (p) => p.symbol,
        ));
      }
    }).catch(() => {});

    api.getBudgetComparison(now.getFullYear(), now.getMonth() + 1).then((rows) => {
      const overCount = rows.filter((r: BudgetComparisonDTO) => r.over_budget).length;
      setBudgetOverCount(overCount);
    }).catch(() => {});

    api.getGoal().then((g) => {
      if (g.progress_pct !== null) setGoalPct(g.progress_pct);
      if (g.passive_income_tl) setGoalPassive(parseFloat(g.passive_income_tl));
    }).catch(() => {});

    api.getForecast(now.getFullYear()).then((fc) => {
      const total = parseFloat(fc.year_total);
      if (total > 0) setPlannedTotal(total);
    }).catch(() => {});

    api.getExpenseSummary(now.getFullYear(), now.getMonth() + 1).then((sum) => {
      const total = parseFloat(sum.total);
      if (sum.count === 0) return;
      setExpenseTotal(total);
      setExpenseCount(sum.count);
      setExpenseTop(top3(
        sum.by_category,
        (b) => parseFloat(b.total),
        (b) => EXPENSE_CATEGORY_LABELS[b.category] ?? b.category,
      ));
    }).catch(() => {});
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
          <button
            onClick={() => router.push("/dashboard/settings")}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Ayarlar
          </button>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">
            Çıkış
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="grid gap-6 sm:grid-cols-2 mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1 flex items-center gap-2">
              Toplam Portföy
              {(cryptoLoading || walletLoading) && (
                <span className="inline-flex items-center gap-1 text-[10px] font-normal text-gray-400 normal-case tracking-normal">
                  <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                  Yükleniyor...
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
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1">Finans (Net Bakiye)</p>
            <div className="flex items-baseline gap-6">
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{MONTH_NAMES[new Date().getMonth()]}</p>
                {currentMonthNet !== null ? (
                  <p className={`text-2xl font-bold tabular-nums ${currentMonthNet >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {currentMonthNet >= 0 ? "+" : ""}{fmtTL(currentMonthNet)} ₺
                  </p>
                ) : (
                  <p className="text-2xl font-bold text-gray-300">—</p>
                )}
              </div>
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{MONTH_NAMES[(new Date().getMonth() + 1) % 12]}</p>
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
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">Finans</h2>
            <button
              onClick={() => router.push("/dashboard/cash-flow")}
              className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
            >
              Nakit Akışı
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {!hiddenCards.includes("creditCards") && (
              <Card
                href="/dashboard/credit-cards"
                icon="creditCard"
                color="red"
                title="Kredi Kartları (toplam borç)"
                total={creditCardTotal}
                count={creditCardCount}
                countLabel="kart"
                top={[]}
                placeholder="Kart tanımı + ekstre + taksit"
                footer={creditCardPeriod !== null && (
                  <span>Dönem içi borç: <span className="font-semibold text-gray-700">{fmtTL(creditCardPeriod)} ₺</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("income") && (
              <Card
                href="/dashboard/income"
                icon="income"
                color="emerald"
                title="Gelirler (bu ay)"
                total={incomeTotal}
                count={incomeCount}
                countLabel="kayıt"
                top={incomeTop}
                placeholder="Maaş, kira, temettü..."
                footer={incomeYearEstimate !== null && (
                  <span>Yıl sonu beklentisi: <span className="font-semibold text-gray-700">{fmtTL(incomeYearEstimate)} ₺</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("expenses") && (
              <Card
                href="/dashboard/expenses"
                icon="expenses"
                color="red"
                title="Harcamalar (bu ay)"
                total={expenseTotal}
                count={expenseCount}
                countLabel="kayıt"
                top={expenseTop}
                placeholder="Aylık gider takibi"
              />
            )}

            {!hiddenCards.includes("planned") && (
              <Card
                href="/dashboard/planned"
                icon="planned"
                color="violet"
                title="Planlı Harcamalar (bu yıl)"
                total={plannedTotal}
                top={[]}
                placeholder="Kredi, vergi, fatura planı"
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
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">Portföy</h2>
            <div className="flex gap-2">
              <button
                onClick={() => router.push("/dashboard/history")}
                className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
              >
                Geçmiş
              </button>
              <button
                onClick={takeSnapshot}
                disabled={snapshotting}
                className="text-sm border border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                {snapshotting ? "Alınıyor..." : "Snapshot al"}
              </button>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {!hiddenCards.includes("bes") && (
              <Card
                href="/dashboard/bes"
                icon="bes"
                color="green"
                title="BES"
                total={besTotal}
                count={besPlanCount}
                countLabel="plan"
                top={besTop}
                placeholder="Bireysel emeklilik — manuel giriş"
              />
            )}

            {!hiddenCards.includes("tefas") && (
              <Card
                href="/dashboard/tefas"
                icon="tefas"
                color="blue"
                title="TEFAS Fonları"
                total={tefasTotal}
                count={tefasFundCount}
                countLabel="fon"
                top={tefasTop}
                placeholder="Yatırım fonu fiyatlarını canlı görüntüle"
              />
            )}

            {!hiddenCards.includes("stocks") && (
              <Card
                href="/dashboard/stocks"
                icon="stocks"
                color="indigo"
                title="Hisse Senedi"
                total={stockTotal}
                count={stockHoldingCount}
                countLabel="hisse"
                top={stockTop}
                placeholder="BIST + ABD + UK — Yahoo Finance"
              />
            )}

            {!hiddenCards.includes("wallets") && (
              <Card
                href="/dashboard/wallets"
                icon="wallets"
                color="purple"
                title="Blockchain Cüzdanlar"
                total={walletTotal}
                loading={walletLoading}
                top={walletTop}
                placeholder="Sonic, Avalanche, Ethereum"
              />
            )}

            {!hiddenCards.includes("crypto") && (
              <Card
                href="/dashboard/crypto"
                icon="crypto"
                color="orange"
                title="Kripto"
                total={cryptoTotal}
                loading={cryptoLoading}
                top={cryptoTop}
                placeholder="Binance & iCrypex"
              />
            )}

            {!hiddenCards.includes("manualCrypto") && (
              <Card
                href="/dashboard/manual-crypto"
                icon="crypto"
                color="orange"
                title="Manuel Kripto"
                total={manualCryptoTotal}
                count={manualCryptoCount}
                countLabel="pozisyon"
                top={manualCryptoTop}
                placeholder="API'siz borsalar (BinanceTR, iCrypex...)"
              />
            )}

            {!hiddenCards.includes("commodities") && (
              <Card
                href="/dashboard/commodities"
                icon="commodities"
                color="amber"
                title="Altın & Gümüş"
                total={commodityTotal}
                count={commodityCount}
                countLabel="pozisyon"
                top={[]}
                placeholder="Gram, BiGA, sikke (çeyrek, tam...)"
              />
            )}

            {!hiddenCards.includes("cash") && (
              <Card
                href="/dashboard/cash"
                icon="cash"
                color="green"
                title="Nakit / Banka"
                total={cashTotal}
                count={cashCount}
                countLabel="hesap"
                top={[]}
                placeholder="Banka hesabı + nakit (manuel)"
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

