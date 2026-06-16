"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  clearAuth,
  EXPENSE_CATEGORY_LABELS,
  INCOME_CATEGORY_LABELS,
  type BudgetComparisonDTO,
  type PendingItemDTO,
  type CreditCardRemindersDTO,
  type SubscriptionRemindersDTO,
  type LivePortfolioOut,
} from "@/lib/api";
import { getAccessToken } from "@/lib/api/_client";
import { getHiddenCards, type DashboardCardId } from "@/lib/format";
import { deriveScope, loadCache, saveCache, type DashboardSnapshot } from "@/lib/dashboardCache";
import { useLivePortfolio } from "@/app/_hooks/useLivePortfolio";
import { LivePortfolioBar } from "@/app/_components/LivePortfolioBar";
import { KFinansLogo, MayotekLogo } from "@/app/_components/Logos";
import { useUsdRate } from "@/app/_components/TLValue";
import { Money, fmtCurrency, useDisplayCurrency } from "@/app/_components/Money";
import { LanguageSwitcher } from "@/app/_i18n/LanguageSwitcher";
import { useTranslation } from "@/app/_i18n/I18nProvider";

// FE-003 (FAZ H): page.tsx 970+ satirdi; dashboard kart bilesenleri ve
// snapshot uyari modal'i ayri _components/ modullerine tasindi.
import { Card, GoalCard, BudgetCard, type TopItem } from "./_components/DashboardCard";
import { SnapshotIssuesModal, type PendingIssues } from "./_components/SnapshotIssuesModal";
import { CHAIN_LABELS } from "./wallets/_components/constants";
import { PendingRealizeModal } from "./_components/PendingRealizeModal";
import { CreditCardRemindersModal } from "./_components/CreditCardRemindersModal";
import { SubscriptionRemindersModal } from "./_components/SubscriptionRemindersModal";


function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function top3<T>(items: T[], valueFn: (i: T) => number, labelFn: (i: T) => string): TopItem[] {
  return [...items]
    .sort((a, b) => valueFn(b) - valueFn(a))
    .slice(0, 3)
    .map((i) => ({ label: labelFn(i), value: valueFn(i) }));
}

// Cache hit sonrasi yeniden cekilen (kendi fetch task'i olan) HAFIF kart id'leri.
// Ağır portföy kartları (tefas/crypto/stocks/wallets/manualCrypto/commodities)
// artık tek `/portfolio/live` çağrısından (useLivePortfolio) beslenir; onların
// "güncelleniyor" durumu live hook'un `refreshing` bayrağıyla yönetilir.
const REFRESHABLE_CARDS: DashboardCardId[] = [
  "bes", "cash", "creditCards", "income", "expenses", "budget", "goal",
];

// `/portfolio/live` section'larından ağır kartların (total + count + top3)
// türetilmiş değerleri. Tüm okumalar defensive (cache yoksa section eksik olabilir).
interface HeavyCardValues {
  tefasTotal: number | null; tefasFundCount: number; tefasTop: TopItem[];
  cryptoTotal: number | null; cryptoTop: TopItem[];
  stockTotal: number | null; stockHoldingCount: number; stockTop: TopItem[];
  walletTotal: number | null; walletTop: TopItem[];
  manualCryptoTotal: number | null; manualCryptoCount: number; manualCryptoTop: TopItem[];
  commodityTotal: number | null; commodityCount: number;
}

function deriveHeavyCards(live: LivePortfolioOut | null): HeavyCardValues | null {
  if (!live) return null;
  const s = live.sections ?? {};
  const parse = (v: string) => Number.parseFloat(v);
  const sum = <T extends { total_value_tl: string }>(arr: T[]) => arr.reduce((a, p) => a + parse(p.total_value_tl), 0);
  const big = <T extends { total_value_tl: string }>(arr: T[]) => arr.filter((p) => parse(p.total_value_tl) > 0.01);

  const tefasPos = s.tefas?.positions ?? [];
  const cryptoPos = big(s.crypto?.positions ?? []);
  const stockPos = s.stocks?.positions ?? [];
  const walletPos = big(s.wallets?.positions ?? []);
  const manualPos = s.manual_crypto?.positions ?? [];
  const commodityPos = s.commodities?.positions ?? [];

  return {
    tefasTotal: tefasPos.length ? sum(tefasPos) : null,
    tefasFundCount: tefasPos.length,
    tefasTop: top3(tefasPos, (p) => parse(p.total_value_tl), (p) => p.code),

    cryptoTotal: cryptoPos.length ? sum(cryptoPos) : null,
    cryptoTop: top3(cryptoPos, (p) => parse(p.total_value_tl), (p) => p.symbol),

    stockTotal: stockPos.length ? sum(stockPos) : null,
    stockHoldingCount: stockPos.length,
    stockTop: top3(stockPos, (p) => parse(p.total_value_tl), (p) => p.ticker),

    walletTotal: walletPos.length ? sum(walletPos) : null,
    walletTop: top3(walletPos, (p) => parse(p.total_value_tl), (p) => p.symbol),

    manualCryptoTotal: manualPos.length ? parse(s.manual_crypto?.total_value_tl ?? "0") : null,
    manualCryptoCount: manualPos.length,
    manualCryptoTop: top3(manualPos, (p) => parse(p.total_value_tl), (p) => p.symbol),

    commodityTotal: commodityPos.length ? parse(s.commodities?.total_value_tl ?? "0") : null,
    commodityCount: commodityPos.length,
  };
}

// Canlı portföy verisinde çekilemeyen kaynakları kullanıcıya gösterilecek okunur
// etiketlere çevirir: tamamen çekilemeyen bölümler (health_issues section_failed) +
// çekilemeyen cüzdan zincirleri (sections.wallets.errors) + borsa hataları
// (sections.crypto.errors). Boş liste → uyarı gösterilmez. Görünen toplamın neden
// eksik olabileceğini kullanıcıya bildirir.
function collectLiveWarnings(
  data: LivePortfolioOut | null,
  cardLabel: (key: string) => string,
): string[] {
  if (!data) return [];
  const labels = new Set<string>();
  // section key → dashboard.cards.* anahtarı (manual_crypto → manualCrypto)
  const sectionKey: Record<string, string> = {
    crypto: "crypto", tefas: "tefas", stocks: "stocks",
    commodities: "commodities", manual_crypto: "manualCrypto", wallets: "wallets",
  };
  for (const issue of data.health_issues ?? []) {
    if (issue.code === "section_failed") {
      labels.add(cardLabel(sectionKey[issue.source] ?? issue.source));
    }
  }
  for (const key of Object.keys(data.sections?.wallets?.errors ?? {})) {
    if (key === "_timeout") continue;
    const chain = key.split(":")[0];
    labels.add(CHAIN_LABELS[chain] ?? chain);
  }
  for (const key of Object.keys(data.sections?.crypto?.errors ?? {})) {
    labels.add(key);
  }
  return [...labels];
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
  const [cryptoTop, setCryptoTop] = useState<TopItem[]>([]);

  // Hisse senedi
  const [stockTotal, setStockTotal] = useState<number | null>(null);
  const [stockHoldingCount, setStockHoldingCount] = useState(0);
  const [stockTop, setStockTop] = useState<TopItem[]>([]);

  // Blockchain (cüzdan)
  const [walletTotal, setWalletTotal] = useState<number | null>(null);
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
  // Abonelik (utility) yıllık kalan tahmini — Giderler footer'ında planlı ile toplanır.
  const [subscriptionYearTotal, setSubscriptionYearTotal] = useState<number | null>(null);

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

  // Dashboard ilk yukleme — tum task'lar tamamlanana kadar "Yukleniyor" spinner
  // (kullanici 2026-05-11: TEFAS yuklenirken Toplam Portfoy yaninda spinner gozukmuyor)
  const [dashboardLoading, setDashboardLoading] = useState(true);

  // Cache'ten hidrasyon olduysa (cache hit), kartlar bos degil — "yukleniyor"
  // yerine ust banner'da "Degerler guncelleniyor" gosterilir.
  const [refreshing, setRefreshing] = useState(false);
  // Hangi kartlarin verisi su an yeniden cekiliyor (cache hit sonrasi). Her kart
  // kendi verisi gelince setten dusulur → kart ustundeki "guncelleniyor" rozeti kalkar.
  const [updatingCards, setUpdatingCards] = useState<Set<DashboardCardId>>(() => new Set());

  // Dashboard kart görünürlüğü
  const [hiddenCards, setHiddenCards] = useState<DashboardCardId[]>([]);

  const usdRate = useUsdRate();
  // Görüntüleme para birimi: finans toplamları backend *_display'inden (BÖLME YOK).
  const displayCurrency = useDisplayCurrency();

  // Ağır portföy kartları: tek `/portfolio/live` çağrısı (sunucu-cache) + poll.
  // Mount'ta otomatik dış-refetch YOK; sadece cache okunur (hızlı).
  const live = useLivePortfolio();
  const heavy = useMemo(() => deriveHeavyCards(live.data), [live.data]);

  const [prevSnapshot, setPrevSnapshot] = useState<number | null>(null);
  // Snapshot uyarı popup state
  const [pendingIssues, setPendingIssues] = useState<PendingIssues | null>(null);
  // Periyodik gelir/gider bekleyen dönem popup state
  const [pendingRealize, setPendingRealize] = useState<PendingItemDTO[]>([]);
  // Kredi kartı hatırlatma popup (ekstre yükleme + ödeme yaklaşan) state
  const [ccReminders, setCcReminders] = useState<CreditCardRemindersDTO | null>(null);
  // Abonelik hatırlatma popup (fatura gir + ödeme yaklaşan) state
  const [subReminders, setSubReminders] = useState<SubscriptionRemindersDTO | null>(null);

  // Snapshot tetikleyici
  const [snapshotting, setSnapshotting] = useState(false);
  const [snapshotMsg, setSnapshotMsg] = useState("");

  useEffect(() => {
    setHiddenCards(getHiddenCards());
  }, []);

  // Ağır kartlar: `/portfolio/live` cache verisi geldikçe (veya poll güncelledikçe)
  // state'i + dashboard cache'ini tazele. Cache hidrasyonu (aşağıdaki hafif-kart
  // effect'i) anında gösterir; bu effect canlı kaynak geldiğinde üzerine yazar.
  useEffect(() => {
    if (!heavy) return;
    setTefasTotal(heavy.tefasTotal);
    setTefasFundCount(heavy.tefasFundCount);
    setTefasTop(heavy.tefasTop);
    setCryptoTotal(heavy.cryptoTotal);
    setCryptoTop(heavy.cryptoTop);
    setStockTotal(heavy.stockTotal);
    setStockHoldingCount(heavy.stockHoldingCount);
    setStockTop(heavy.stockTop);
    setWalletTotal(heavy.walletTotal);
    setWalletTop(heavy.walletTop);
    setManualCryptoTotal(heavy.manualCryptoTotal);
    setManualCryptoCount(heavy.manualCryptoCount);
    setManualCryptoTop(heavy.manualCryptoTop);
    setCommodityTotal(heavy.commodityTotal);
    setCommodityCount(heavy.commodityCount);

    // Ağır kart değerlerini kullanıcıya özel dashboard cache'ine yaz (sonraki
    // açılışta anında gösterim). Top listeleri kompakt (label+value) saklanır.
    const scope = deriveScope(getAccessToken());
    saveCache(scope, {
      tefasTotal: heavy.tefasTotal, tefasFundCount: heavy.tefasFundCount, tefasTop: heavy.tefasTop,
      cryptoTotal: heavy.cryptoTotal, cryptoTop: heavy.cryptoTop,
      stockTotal: heavy.stockTotal, stockHoldingCount: heavy.stockHoldingCount, stockTop: heavy.stockTop,
      walletTotal: heavy.walletTotal, walletTop: heavy.walletTop,
      manualCryptoTotal: heavy.manualCryptoTotal, manualCryptoCount: heavy.manualCryptoCount, manualCryptoTop: heavy.manualCryptoTop,
      commodityTotal: heavy.commodityTotal, commodityCount: heavy.commodityCount,
    });
  }, [heavy]);

  // Girişte: tarihi geçmiş + işaretlenmemiş periyodik gelir/gider varsa popup aç
  useEffect(() => {
    let cancelled = false;
    api
      .getPendingRealizations()
      .then((res) => {
        if (!cancelled && res.items.length > 0) setPendingRealize(res.items);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Kredi kartı hatırlatması: her dashboard açılışında DEĞİL, günde en fazla 1 kez.
  // localStorage'da o gün gösterildiyse atla; gösterilecek bir şey varsa (ekstre
  // eksik veya ödemesi ≤5 gün kala) bir kez aç ve günü işaretle.
  useEffect(() => {
    const STORAGE_KEY = "kfinans-cc-reminders-shown";
    const todayStr = new Date().toISOString().slice(0, 10);
    if (localStorage.getItem(STORAGE_KEY) === todayStr) return; // bugün zaten gösterildi

    let cancelled = false;
    api
      .getCreditCardReminders()
      .then((res) => {
        if (cancelled) return;
        if (res.pending_statements.length > 0 || res.due_payments.length > 0) {
          setCcReminders(res);
          localStorage.setItem(STORAGE_KEY, todayStr);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Abonelik hatırlatması: kredi kartıyla aynı mantık (günde 1 kez, ayrı throttle key).
  // Fatura girilecek dönem veya ödemesi yaklaşan/geçmiş fatura varsa popup aç.
  useEffect(() => {
    const STORAGE_KEY = "kfinans-sub-reminders-shown";
    const todayStr = new Date().toISOString().slice(0, 10);
    if (localStorage.getItem(STORAGE_KEY) === todayStr) return; // bugün zaten gösterildi

    let cancelled = false;
    api
      .getSubscriptionReminders()
      .then((res) => {
        if (cancelled) return;
        if (res.pending_bills.length > 0 || res.due_payments.length > 0) {
          setSubReminders(res);
          localStorage.setItem(STORAGE_KEY, todayStr);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
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

    // Cache scope (kullaniciya ozel) — access token'dan turetilir.
    const scope = deriveScope(getAccessToken());

    // Bir fetch grubu tamamlaninca: cache'i kismi (merge) guncelle.
    function cachePatch(patch: Partial<DashboardSnapshot>): void {
      if (cancelled) return;
      saveCache(scope, patch);
    }

    // Bir kartin verisi geldi → "guncelleniyor" rozetini kaldir (set'ten dus).
    function markFresh(id: DashboardCardId): void {
      if (cancelled) return;
      setUpdatingCards((prev) => {
        if (!prev.has(id)) return prev;
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }

    // Hidrasyon + ilk setState'ler senkron effect govdesinde DEGIL, microtask'ta
    // calisir (react-hooks/set-state-in-effect uyarisi sadece SENKRON cagrilari
    // isaretler; fetch .then() callback'leri gibi async cagrilar guvenli).
    Promise.resolve().then(() => {
      if (cancelled) return;

      // Cache hit → kartlari ANINDA cache degerleriyle doldur + "guncelleniyor".
      const cached = loadCache(scope);
      if (!cached) return;
      const c = cached;
      const set = <T,>(setter: (v: T) => void, v: T | null | undefined) => {
        if (v !== null && v !== undefined) setter(v);
      };
      set(setTefasTotal, c.tefasTotal);
      set(setTefasFundCount, c.tefasFundCount);
      set(setTefasTop, c.tefasTop);
      set(setCryptoTotal, c.cryptoTotal);
      set(setCryptoTop, c.cryptoTop);
      set(setStockTotal, c.stockTotal);
      set(setStockHoldingCount, c.stockHoldingCount);
      set(setStockTop, c.stockTop);
      set(setWalletTotal, c.walletTotal);
      set(setWalletTop, c.walletTop);
      set(setBesTotal, c.besTotal);
      set(setBesPlanCount, c.besPlanCount);
      set(setBesTop, c.besTop);
      set(setExpenseTotal, c.expenseTotal);
      set(setExpenseCount, c.expenseCount);
      set(setExpenseTop, c.expenseTop);
      set(setPlannedTotal, c.plannedTotal);
      set(setSubscriptionYearTotal, c.subscriptionYearTotal);
      set(setIncomeTotal, c.incomeTotal);
      set(setIncomeCount, c.incomeCount);
      set(setIncomeTop, c.incomeTop);
      set(setIncomeYearEstimate, c.incomeYearEstimate);
      set(setCreditCardTotal, c.creditCardTotal);
      set(setCreditCardPeriod, c.creditCardPeriod);
      set(setCreditCardCount, c.creditCardCount);
      set(setCommodityTotal, c.commodityTotal);
      set(setCommodityCount, c.commodityCount);
      set(setCashTotal, c.cashTotal);
      set(setCashCount, c.cashCount);
      set(setManualCryptoTotal, c.manualCryptoTotal);
      set(setManualCryptoCount, c.manualCryptoCount);
      set(setManualCryptoTop, c.manualCryptoTop);
      set(setBudgetOverCount, c.budgetOverCount);
      set(setCurrentMonthNet, c.currentMonthNet);
      set(setNextMonthNet, c.nextMonthNet);
      set(setGoalPct, c.goalPct);
      set(setGoalPassive, c.goalPassive);
      // Cache degerleri ekranda — spinner yerine ust banner + kart-bazli rozet.
      // Tum (fetch task'i olan) kartlari "guncelleniyor" isaretle; her task
      // bitince markFresh ile tek tek dusulur.
      setDashboardLoading(false);
      setRefreshing(true);
      setUpdatingCards(new Set(REFRESHABLE_CARDS));
    });

    // NOT: Ağır portföy kartları (tefas/crypto/stocks/wallets/commodities/
    // manual-crypto) artık bu listede DEĞİL — tek `/portfolio/live` çağrısıyla
    // (useLivePortfolio) sunucu-cache'ten okunur. Burada yalnız HAFİF kartlar var.
    const tasks: Promise<unknown>[] = [
      // BES
      safe("bes", async () => {
        const holdings = await api.getBesHoldings();
        if (!holdings.length) return;
        safeSet(setBesPlanCount)(holdings.length);
        const items = holdings.map((h) => ({
          plan_name: h.plan_name,
          total:
            (Number.parseFloat(h.paid_principal.toString()) || 0) +
            (Number.parseFloat(h.paid_returns.toString()) || 0) +
            (Number.parseFloat(h.govt_contribution.toString()) || 0) +
            (Number.parseFloat(h.govt_returns.toString()) || 0),
        }));
        const total = items.reduce((s, i) => s + i.total, 0);
        const besTop = top3(items, (i) => i.total, (i) => i.plan_name);
        safeSet(setBesTotal)(total);
        safeSet(setBesTop)(besTop);
        cachePatch({ besTotal: total, besPlanCount: holdings.length, besTop });
      }).finally(() => markFresh("bes")),

      // Gelir özeti (bu ay)
      safe("income-summary", async () => {
        const sum = await api.getIncomeSummary(yyyy, mm);
        if (sum.count === 0) return;
        // Faz C: *_display ZATEN görüntüleme biriminde (tarihsel kur, BÖLME YOK).
        const incomeTotal = Number.parseFloat(sum.total_display);
        const incomeTop = top3(
          sum.by_category,
          (b) => Number.parseFloat(b.total_display),
          (b) => INCOME_CATEGORY_LABELS[b.category] ?? b.category,
        );
        safeSet(setIncomeTotal)(incomeTotal);
        safeSet(setIncomeCount)(sum.count);
        safeSet(setIncomeTop)(incomeTop);
        cachePatch({ incomeTotal, incomeCount: sum.count, incomeTop });
      }).finally(() => markFresh("income")),

      // Gelir dashboard (yıl sonu beklentisi)
      safe("income-dashboard", async () => {
        const d = await api.getIncomeDashboard(yyyy, mm);
        // Faz C: year_total_estimate_display görüntüleme biriminde (BÖLME YOK).
        const est = Number.parseFloat(d.year_total_estimate_display);
        if (est > 0) {
          safeSet(setIncomeYearEstimate)(est);
          cachePatch({ incomeYearEstimate: est });
        }
      }),

      // Cash flow (bu ay + gelecek ay net)
      safe("cash-flow", async () => {
        const fetches = [api.getCashFlow(yyyy)];
        if (isDecember) fetches.push(api.getCashFlow(yyyy + 1));
        const [thisYear, nextYear] = await Promise.all(fetches);
        const thisMonth = thisYear.months.find((m) => m.month === mm);
        const nextMonthData = isDecember
          ? nextYear?.months.find((m) => m.month === 1)
          : thisYear.months.find((m) => m.month === mm + 1);
        const patch: Partial<DashboardSnapshot> = {};
        // Faz C: net_display ZATEN görüntüleme biriminde (BÖLME YOK).
        if (thisMonth) {
          const v = Number.parseFloat(thisMonth.net_display);
          safeSet(setCurrentMonthNet)(v);
          patch.currentMonthNet = v;
        }
        if (nextMonthData) {
          const v = Number.parseFloat(nextMonthData.net_display);
          safeSet(setNextMonthNet)(v);
          patch.nextMonthNet = v;
        }
        cachePatch(patch);
      }),

      // Kredi kartları
      safe("credit-cards", async () => {
        const s = await api.listCreditCards();
        // Faz C: *_display ZATEN görüntüleme biriminde (borç → güncel kur, BÖLME YOK).
        const creditCardTotal = Number.parseFloat(s.total_debt_display);
        const creditCardPeriod = Number.parseFloat(s.total_period_debt_display);
        safeSet(setCreditCardTotal)(creditCardTotal);
        safeSet(setCreditCardPeriod)(creditCardPeriod);
        safeSet(setCreditCardCount)(s.cards.length);
        cachePatch({ creditCardTotal, creditCardPeriod, creditCardCount: s.cards.length });
      }).finally(() => markFresh("creditCards")),

      // Nakit / Banka
      safe("cash", async () => {
        const s = await api.listCash();
        const total = Number.parseFloat(s.total_tl);
        if (s.holdings.length > 0) {
          safeSet(setCashTotal)(total);
          safeSet(setCashCount)(s.holdings.length);
          cachePatch({ cashTotal: total, cashCount: s.holdings.length });
        }
      }).finally(() => markFresh("cash")),

      // Bütçe karşılaştırma
      safe("budget", async () => {
        const rows = await api.getBudgetComparison(yyyy, mm);
        const overCount = rows.filter((r: BudgetComparisonDTO) => r.over_budget).length;
        safeSet(setBudgetOverCount)(overCount);
        cachePatch({ budgetOverCount: overCount });
      }).finally(() => markFresh("budget")),

      // Finansal hedef
      safe("goal", async () => {
        const g = await api.getGoal();
        const patch: Partial<DashboardSnapshot> = {};
        if (g.progress_pct !== null) {
          safeSet(setGoalPct)(g.progress_pct);
          patch.goalPct = g.progress_pct;
        }
        if (g.passive_income_tl) {
          const v = Number.parseFloat(g.passive_income_tl);
          safeSet(setGoalPassive)(v);
          patch.goalPassive = v;
        }
        cachePatch(patch);
      }).finally(() => markFresh("goal")),

      // Planlı ödemeler (yıllık tahmin) — Giderler kartının "yıl sonu beklentisi"
      // footer'ını besler (ayrı kart kaldırıldı → markFresh expenses).
      safe("planned", async () => {
        const fc = await api.getForecast(yyyy);
        const total = Number.parseFloat(fc.year_total);
        if (total > 0) {
          safeSet(setPlannedTotal)(total);
          cachePatch({ plannedTotal: total });
        }
      }).finally(() => markFresh("expenses")),

      // Abonelikler (utility) yıllık kalan tahmini — Giderler footer'ında
      // planlı ile toplanır (yıl sonu beklentisi = planlı + abonelik).
      safe("subscriptions", async () => {
        const sum = await api.getSubscriptionSummary(displayCurrency);
        const total = Number.parseFloat(sum.remaining_year_estimate);
        if (Number.isFinite(total) && total > 0) {
          safeSet(setSubscriptionYearTotal)(total);
          cachePatch({ subscriptionYearTotal: total });
        }
      }).finally(() => markFresh("expenses")),

      // Harcama özeti (bu ay)
      safe("expenses", async () => {
        const sum = await api.getExpenseSummary(yyyy, mm);
        if (sum.count === 0) return;
        // Faz C: *_display ZATEN görüntüleme biriminde (tarihsel kur, BÖLME YOK).
        const expenseTotal = Number.parseFloat(sum.total_display);
        const expenseTop = top3(
          sum.by_category,
          (b) => Number.parseFloat(b.total_display),
          (b) => EXPENSE_CATEGORY_LABELS[b.category] ?? b.category,
        );
        safeSet(setExpenseTotal)(expenseTotal);
        safeSet(setExpenseCount)(sum.count);
        safeSet(setExpenseTop)(expenseTop);
        cachePatch({ expenseTotal, expenseCount: sum.count, expenseTop });
      }).finally(() => markFresh("expenses")),
    ];

    // Tum fetch'lerin tamamlanmasini bekle (orchestration sonu telemetri + spinner kapat)
    Promise.allSettled(tasks).then((results) => {
      if (cancelled) return;
      const failed = results.filter((r) => r.status === "rejected").length;
      if (failed > 0) {
        console.warn(`[dashboard] ${failed}/${tasks.length} fetch fail`);
      }
      setDashboardLoading(false);
      setRefreshing(false);
    });

    return () => { cancelled = true; };
    // displayCurrency dep: görüntüleme para birimi değişince finans fetch'leri yeni
    // display param ile yeniden çalışır (backend güncel *_display döner).
  }, [router, displayCurrency]);

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
      const total = Number.parseFloat(snap.total_value_tl);
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
        const total = Number.parseFloat(preview.total_value_tl);
        setPendingIssues({ issues: preview.issues, total });
        setSnapshotting(false);
        return;
      }
      // Sorunsuz → doğrudan kaydet (force gerekmez)
      const snap = await api.createSnapshot(false);
      const total = Number.parseFloat(snap.total_value_tl);
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

  // Giderler kartı "yıl sonu beklentisi" footer'ı = planlı ödemeler + abonelikler.
  const expenseYearEnd = (plannedTotal ?? 0) + (subscriptionYearTotal ?? 0);

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
        {(refreshing || live.refreshing) && (
          <output
            aria-live="polite"
            className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 border border-blue-100 px-3 py-2 rounded-lg mb-4"
          >
            <span className="inline-block w-3 h-3 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            {t("dashboard.refreshing")}
          </output>
        )}
        {live.error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-100 px-3 py-2 rounded-lg mb-4" role="alert">
            {live.error}
          </p>
        )}
        {(() => {
          // Kısmi hata: bazı cüzdan zincirleri / bölümler çekilemedi → toplam eksik
          // olabilir. Kullanıcıya hangi kaynakların eksik olduğunu bildir (sessiz
          // düşük-toplam yerine). Yenilenirken gösterme (geçici olabilir).
          if (live.refreshing) return null;
          const warnings = collectLiveWarnings(live.data, (k) => t(`dashboard.cards.${k}`));
          if (warnings.length === 0) return null;
          return (
            <div
              className="text-xs text-amber-800 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg mb-4 flex items-start gap-2"
              role="alert"
            >
              <span aria-hidden="true">⚠</span>
              <span>
                {t("dashboard.live.partialFailure")}:{" "}
                <span className="font-medium">{warnings.join(", ")}</span>. {t("dashboard.live.partialHint")}
              </span>
            </div>
          );
        })()}
        <div className="grid gap-6 sm:grid-cols-2 mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-1 flex items-center gap-2">
              {t("dashboard.totalPortfolio")}
              {dashboardLoading && (
                <span className="inline-flex items-center gap-1 text-[10px] font-normal text-gray-400 normal-case tracking-normal">
                  <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                  {t("common.loading")}
                </span>
              )}
            </p>
            {grandTotal > 0 ? (
              <Money tl={grandTotal} className="text-3xl font-bold text-gray-900 tabular-nums" />
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
                {currentMonthNet === null ? (
                  <p className="text-2xl font-bold text-gray-300">—</p>
                ) : (
                  <p className={`text-2xl font-bold tabular-nums ${currentMonthNet >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {currentMonthNet >= 0 ? "+" : ""}{fmtCurrency(currentMonthNet, displayCurrency)}
                  </p>
                )}
              </div>
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider">{t(`months.${((new Date().getMonth() + 1) % 12) + 1}`)}</p>
                {nextMonthNet === null ? (
                  <p className="text-2xl font-bold text-gray-300">—</p>
                ) : (
                  <p className={`text-2xl font-bold tabular-nums ${nextMonthNet >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {nextMonthNet >= 0 ? "+" : ""}{fmtCurrency(nextMonthNet, displayCurrency)}
                  </p>
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
                updating={updatingCards.has("creditCards")}
                icon="creditCard"
                color="red"
                title={t("dashboard.cards.creditCards")}
                total={creditCardTotal}
                displayValue
                count={creditCardCount}
                countLabel={t("dashboard.card")}
                top={[]}
                placeholder={t("dashboard.cards.creditCardsHint")}
                footer={creditCardPeriod !== null && (
                  <span>{t("dashboard.currentPeriodDebt")}: <span className="font-semibold text-gray-700">{fmtCurrency(creditCardPeriod, displayCurrency)}</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("income") && (
              <Card
                href="/dashboard/income"
                updating={updatingCards.has("income")}
                icon="income"
                color="emerald"
                title={t("dashboard.cards.income")}
                total={incomeTotal}
                displayValue
                count={incomeCount}
                countLabel={t("dashboard.record")}
                top={incomeTop}
                placeholder={t("dashboard.cards.incomeHint")}
                footer={incomeYearEstimate !== null && (
                  <span>{t("dashboard.yearEndExpectation")}: <span className="font-semibold text-gray-700">{fmtCurrency(incomeYearEstimate, displayCurrency)}</span></span>
                )}
              />
            )}

            {/* Giderler: anlık (bu ay) gerçekleşen + footer'da yıl sonu planlı beklenti
                (gelir kartı simetrisi). Eski ayrı "Planlı Ödemeler" kartı buraya birleşti;
                tek "Giderler" kartı → tıklayınca /dashboard/expenses (2 sekme). */}
            {!hiddenCards.includes("expenses") && (
              <Card
                href="/dashboard/expenses"
                updating={updatingCards.has("expenses")}
                icon="expenses"
                color="red"
                title={t("dashboard.cards.expenses")}
                total={expenseTotal}
                displayValue
                count={expenseCount}
                countLabel={t("dashboard.record")}
                top={expenseTop}
                placeholder={t("dashboard.cards.expensesHint")}
                footer={expenseYearEnd > 0 && (
                  <span>{t("dashboard.yearEndExpectation")}: <span className="font-semibold text-gray-700">{fmtCurrency(expenseYearEnd, displayCurrency)}</span></span>
                )}
              />
            )}

            {!hiddenCards.includes("budget") && (
              <BudgetCard href="/dashboard/budget" overCount={budgetOverCount} updating={updatingCards.has("budget")} />
            )}

            {!hiddenCards.includes("goal") && (
              <GoalCard href="/dashboard/goal" pct={goalPct} passive={goalPassive} updating={updatingCards.has("goal")} />
            )}
          </div>
        </section>

        {/* PORTFÖY GRUBU (asagida) */}
        <section className="space-y-3 mt-8">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">{t("dashboard.portfolio")}</h2>
            <div className="flex gap-2 items-center flex-wrap">
              <LivePortfolioBar
                refreshedAt={live.data?.refreshed_at ?? null}
                stale={live.data?.stale ?? false}
                refreshing={live.refreshing}
                onRefresh={live.refresh}
              />
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
                updating={updatingCards.has("bes")}
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
                updating={live.refreshing}
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
                updating={live.refreshing}
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
                updating={live.refreshing}
                icon="wallets"
                color="purple"
                title={t("dashboard.cards.wallets")}
                total={walletTotal}
                loading={live.loading && walletTotal === null}
                top={walletTop}
                placeholder={t("dashboard.cards.walletsHint")}
              />
            )}

            {!hiddenCards.includes("crypto") && (
              <Card
                href="/dashboard/crypto"
                updating={live.refreshing}
                icon="crypto"
                color="orange"
                title={t("dashboard.cards.crypto")}
                total={cryptoTotal}
                loading={live.loading && cryptoTotal === null}
                top={cryptoTop}
                placeholder={t("dashboard.cards.cryptoHint")}
              />
            )}

            {!hiddenCards.includes("manualCrypto") && (
              <Card
                href="/dashboard/manual-crypto"
                updating={live.refreshing}
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
                updating={live.refreshing}
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
                updating={updatingCards.has("cash")}
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

      {/* Periyodik gelir/gider bekleyen dönem popup'ı */}
      {pendingRealize.length > 0 && (
        <PendingRealizeModal items={pendingRealize} onClose={() => setPendingRealize([])} />
      )}

      {/* Kredi kartı ekstre/ödeme hatırlatma popup'ı */}
      {ccReminders && (
        <CreditCardRemindersModal data={ccReminders} onClose={() => setCcReminders(null)} />
      )}

      {/* Abonelik fatura/ödeme hatırlatma popup'ı */}
      {subReminders && (
        <SubscriptionRemindersModal data={subReminders} onClose={() => setSubReminders(null)} />
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

