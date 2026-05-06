"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, clearAuth, EXPENSE_CATEGORY_LABELS, INCOME_CATEGORY_LABELS } from "@/lib/api";
import type { BudgetComparisonDTO } from "@/lib/api";
import { getHiddenCards, type DashboardCardId } from "@/lib/format";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { TLValue, useUsdRate } from "@/app/_components/TLValue";
import type { SnapshotHealthIssue } from "@/lib/api";


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

interface TopItem {
  label: string;
  value: number;
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

  // Finansal hedef
  const [goalPct, setGoalPct] = useState<number | null>(null);
  const [goalPassive, setGoalPassive] = useState<number | null>(null);

  // Dashboard kart görünürlüğü
  const [hiddenCards, setHiddenCards] = useState<DashboardCardId[]>([]);

  const usdRate = useUsdRate();
  const [prevSnapshot, setPrevSnapshot] = useState<number | null>(null);
  // Snapshot uyarı popup state
  const [pendingIssues, setPendingIssues] = useState<{
    issues: SnapshotHealthIssue[];
    total: number;
  } | null>(null);

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
        <div className="flex items-end justify-between mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1">Toplam Portföy</p>
            {grandTotal > 0 ? (
              <TLValue tl={grandTotal} className="text-3xl font-bold text-gray-900 tabular-nums" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
            ) : (
              <p className="text-3xl font-bold text-gray-300">—</p>
            )}
          </div>
          <div className="flex gap-2 pb-1">
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
        {snapshotMsg && (
          <p className="text-xs text-gray-500 bg-gray-50 border border-gray-100 px-3 py-2 rounded-lg mb-4">{snapshotMsg}</p>
        )}

        {/* PORTFÖY GRUBU */}
        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">Portföy</h2>
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

        {/* FİNANS GRUBU */}
        <section className="space-y-3 mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">Finans</h2>
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
      </main>

      {/* Snapshot uyarı popup'ı */}
      {pendingIssues && (
        <div
          role="presentation"
          onClick={() => setPendingIssues(null)}
          onKeyDown={(e) => { if (e.key === "Escape") setPendingIssues(null); }}
          className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-lg w-full text-left cursor-default"
          >
            {(() => {
              const warns = pendingIssues.issues.filter((i) => (i.level ?? "warn") === "warn");
              const infos = pendingIssues.issues.filter((i) => i.level === "info");
              return (
                <>
                  <h3 className="text-base font-semibold text-gray-900 mb-1">
                    Snapshot uyarıları
                    {warns.length > 0 && <span className="text-amber-600"> · {warns.length} sorun</span>}
                    {infos.length > 0 && <span className="text-blue-600"> · {infos.length} bilgi</span>}
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">
                    Toplam: <span className="font-semibold text-gray-700">{fmtTL(pendingIssues.total)} ₺</span>.
                    {warns.length > 0 && " Sorunlu kayıtlar var; yine de kaydetmek ister misiniz? "}
                    {warns.length === 0 && infos.length > 0 && " Bilgi notları var (manuel/bağlı fiyatlar). "}
                    Sorunlar/notlar geçmişte de görünür kalır.
                  </p>
                  <ul className="space-y-2 max-h-72 overflow-y-auto mb-4">
                    {pendingIssues.issues.map((iss, i) => {
                      const isInfo = iss.level === "info";
                      return (
                        <li
                          key={i}
                          className={`rounded-lg px-3 py-2 text-xs border ${
                            isInfo
                              ? "bg-blue-50 border-blue-100"
                              : "bg-amber-50 border-amber-100"
                          }`}
                        >
                          <p className={`font-semibold ${isInfo ? "text-blue-800" : "text-amber-800"}`}>
                            {isInfo ? "ⓘ" : "⚠"} {iss.source}
                            {iss.exchange && ` · ${iss.exchange}`}
                            {iss.symbol && ` · ${iss.symbol}`}
                            {iss.chain && ` · ${iss.chain}`}
                            {iss.provider && ` · ${iss.provider}`}
                            {iss.label && ` · ${iss.label}`}
                          </p>
                          <p className="text-gray-700 mt-0.5">{iss.msg}</p>
                        </li>
                      );
                    })}
                  </ul>
                </>
              );
            })()}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setPendingIssues(null)}
                className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50"
              >
                İptal
              </button>
              <button
                type="button"
                onClick={saveConfirmedSnapshot}
                disabled={snapshotting}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {snapshotting ? "Kaydediliyor..." : "Yine de kaydet"}
              </button>
            </div>
          </div>
        </div>
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

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; accent: string }> = {
  blue:    { bg: "bg-blue-50",    border: "hover:border-blue-200",    text: "text-blue-600",    accent: "bg-blue-500" },
  orange:  { bg: "bg-orange-50",  border: "hover:border-orange-200",  text: "text-orange-500",  accent: "bg-orange-500" },
  indigo:  { bg: "bg-indigo-50",  border: "hover:border-indigo-200",  text: "text-indigo-600",  accent: "bg-indigo-500" },
  purple:  { bg: "bg-purple-50",  border: "hover:border-purple-200",  text: "text-purple-600",  accent: "bg-purple-500" },
  green:   { bg: "bg-green-50",   border: "hover:border-green-200",   text: "text-green-600",   accent: "bg-green-500" },
  red:     { bg: "bg-red-50",     border: "hover:border-red-200",     text: "text-red-500",     accent: "bg-red-500" },
  violet:  { bg: "bg-violet-50",  border: "hover:border-violet-200",  text: "text-violet-600",  accent: "bg-violet-500" },
  emerald: { bg: "bg-emerald-50", border: "hover:border-emerald-200", text: "text-emerald-600", accent: "bg-emerald-500" },
  amber:   { bg: "bg-amber-50",   border: "hover:border-amber-200",   text: "text-amber-600",   accent: "bg-amber-500" },
};

type IconName = "tefas" | "crypto" | "stocks" | "wallets" | "bes" | "expenses" | "planned" | "income" | "goal" | "commodities" | "budget" | "cash" | "creditCard";

const ICONS: Record<IconName, React.ReactNode> = {
  tefas: (
    // Pie chart — yatırım fonu portföy dağılımını çağrıştırır
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2v10h10" />
      <path d="M12 12L4.93 19.07" />
    </svg>
  ),
  crypto: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M11.767 19.089c4.924.868 6.14-6.025 1.216-6.894m-1.216 6.894L5.86 18.047m5.908 1.042-.347 1.97m1.563-8.864c4.924.869 6.14-6.025 1.215-6.893m-1.215 6.893-3.94-.694m5.155-6.2L8.29 4.26m5.908 1.042.348-1.97M7.48 20.364l3.126-17.727" />
    </svg>
  ),
  stocks: (
    // Candlestick chart — hisse senedi göstergesi (wick + body)
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <line x1="6"  y1="3"  x2="6"  y2="21" />
      <rect x="4"  y="7"  width="4" height="7" fill="currentColor" stroke="none" />
      <line x1="12" y1="5"  x2="12" y2="19" />
      <rect x="10" y="13" width="4" height="4" fill="currentColor" stroke="none" />
      <line x1="18" y1="2"  x2="18" y2="22" />
      <rect x="16" y="6"  width="4" height="9" fill="currentColor" stroke="none" />
    </svg>
  ),
  wallets: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  bes: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  ),
  expenses: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="1" y="4" width="22" height="16" rx="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  ),
  planned: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8"  y1="2" x2="8"  y2="6" />
      <line x1="3"  y1="10" x2="21" y2="10" />
    </svg>
  ),
  income: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  goal: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  ),
  commodities: (
    // Coin stack — üst üste 3 madeni para (altın/gümüş)
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <ellipse cx="12" cy="5"  rx="8" ry="2.5" />
      <path d="M4 5v3.5c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5V5" />
      <path d="M4 11v3.5c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5V11" />
      <path d="M4 17v2c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-2" />
    </svg>
  ),
  budget: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </svg>
  ),
  cash: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <circle cx="12" cy="12" r="2" />
      <path d="M6 12h.01M18 12h.01" />
    </svg>
  ),
  creditCard: (
    // Kredi kartı — chip ile birlikte
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <line x1="2" y1="10" x2="22" y2="10" />
      <rect x="5" y="13" width="4" height="3" rx="0.5" fill="currentColor" stroke="none" />
    </svg>
  ),
};

interface CardProps {
  href: string;
  icon: IconName;
  color: keyof typeof COLOR_MAP;
  title: string;
  total: number | null;
  count?: number;
  countLabel?: string;
  loading?: boolean;
  top: TopItem[];
  placeholder: string;
  footer?: React.ReactNode;
}

function GoalCard({ href, pct, passive }: { href: string; pct: number | null; passive: number | null }) {
  const router = useRouter();
  const hasData = pct !== null;

  return (
    <button
      onClick={() => router.push(href)}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md hover:border-violet-200 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 bg-violet-50 rounded-xl flex items-center justify-center text-violet-600 group-hover:bg-violet-100 transition-colors">
          {ICONS.goal}
        </div>
        {hasData && (
          <span className="text-xs font-semibold text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">
            %{pct!.toFixed(0)}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">Finansal Hedef</h3>

      {hasData ? (
        <>
          <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden mb-2">
            <div
              className="h-full bg-violet-500 rounded-full transition-all"
              style={{ width: `${Math.min(pct!, 100)}%` }}
            />
          </div>
          {passive !== null && (
            <p className="text-xs text-gray-400">
              Pasif gelir: <span className="font-medium text-gray-600">{fmtTL(passive)} ₺/ay</span>
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-400">Aylık ihtiyacını gir, hedefini hesapla</p>
      )}
    </button>
  );
}

function BudgetCard({ href, overCount }: { href: string; overCount: number | null }) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push(href)}
      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md hover:border-amber-200 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600 group-hover:bg-amber-100 transition-colors">
          {ICONS.budget}
        </div>
        {overCount !== null && overCount > 0 && (
          <span className="text-xs font-semibold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">
            {overCount} aşım
          </span>
        )}
        {overCount !== null && overCount === 0 && (
          <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
            Dahilinde
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">Bütçe Takibi</h3>
      {overCount === null
        ? <p className="text-xs text-gray-400">Kategori bazında limit belirle</p>
        : overCount === 0
          ? <p className="text-xs text-emerald-600">Tüm kategoriler bütçe dahilinde</p>
          : <p className="text-xs text-red-500">{overCount} kategori bütçeyi aştı</p>
      }
    </button>
  );
}

function Card({ href, icon, color, title, total, count, countLabel, loading, top, placeholder, footer }: CardProps) {
  const router = useRouter();
  const c = COLOR_MAP[color];
  // total === 0 da geçerli yüklenmiş değer (örn. kredi kartı borç yoksa).
  // Sadece null = henüz fetch gelmedi.
  const hasTotal = total !== null;

  return (
    <button
      onClick={() => router.push(href)}
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-5 text-left hover:shadow-md ${c.border} transition-all group`}
    >
      <div className={`w-9 h-9 ${c.bg} rounded-xl flex items-center justify-center ${c.text} mb-3 group-hover:opacity-80 transition-opacity`}>
        {ICONS[icon]}
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>

      {hasTotal ? (
        <TLValue tl={total} className={`text-base font-bold tabular-nums ${c.text}`} />
      ) : (count ?? 0) > 0 ? (
        <p className="text-xs text-gray-400">{count} {countLabel} · yükleniyor...</p>
      ) : loading ? (
        <p className="text-xs text-gray-400">Yükleniyor...</p>
      ) : (
        <p className="text-xs text-gray-400">{placeholder}</p>
      )}

      {top.length > 0 && (
        <ul className="mt-3 pt-3 border-t border-gray-50 space-y-1.5">
          {top.map((it) => (
            <li key={it.label} className="flex justify-between items-center text-xs">
              <span className="truncate text-gray-500 font-mono max-w-[60%]">{it.label}</span>
              <span className="font-semibold tabular-nums text-gray-700 ml-2 shrink-0">{fmtTL(it.value)} ₺</span>
            </li>
          ))}
        </ul>
      )}
      {footer && (
        <div className="mt-3 pt-3 border-t border-gray-50 text-xs text-gray-500">
          {footer}
        </div>
      )}
    </button>
  );
}
