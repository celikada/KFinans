"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { api, clearAuth, EXPENSE_CATEGORY_LABELS } from "@/lib/api";

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

  // Snapshot tetikleyici
  const [snapshotting, setSnapshotting] = useState(false);
  const [snapshotMsg, setSnapshotMsg] = useState("");

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

  async function takeSnapshot() {
    setSnapshotting(true);
    setSnapshotMsg("");
    try {
      const snap = await api.createSnapshot();
      const total = parseFloat(snap.total_value_tl);
      setSnapshotMsg(`✓ Snapshot alındı: ${fmtTL(total)} ₺ (${snap.asset_positions.length} pozisyon)`);
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
    (besTotal ?? 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <Image src="/images/kfinans-logo.png" alt="KFinans" width={80} height={85} />
        <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">
          Çıkış
        </button>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Portföy</h2>
            {grandTotal > 0 && (
              <p className="text-sm text-gray-500 mt-1">
                Toplam: <span className="font-semibold text-gray-900">{fmtTL(grandTotal)} ₺</span>
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => router.push("/dashboard/history")}
              className="text-sm border border-gray-200 text-gray-600 hover:text-gray-900 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
              title="Snapshot geçmişi grafikleri"
            >
              Geçmiş
            </button>
            <button
              onClick={takeSnapshot}
              disabled={snapshotting}
              className="text-sm border border-gray-200 text-gray-600 hover:text-gray-900 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              title="Tüm kaynaklardan veri çek ve haftalık snapshot kaydet"
            >
              {snapshotting ? "Snapshot alınıyor..." : "Snapshot al"}
            </button>
          </div>
        </div>
        {snapshotMsg && (
          <p className="text-xs text-gray-500 bg-gray-100 px-3 py-2 rounded-lg mb-4">{snapshotMsg}</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            href="/dashboard/tefas"
            icon="📈"
            color="blue"
            title="TEFAS Fonları"
            total={tefasTotal}
            count={tefasFundCount}
            countLabel="fon"
            top={tefasTop}
            placeholder="Yatırım fonu fiyatlarını canlı görüntüle"
          />

          <Card
            href="/dashboard/crypto"
            icon="₿"
            color="orange"
            title="Kripto"
            total={cryptoTotal}
            loading={cryptoLoading}
            top={cryptoTop}
            placeholder="Binance & iCrypex"
          />

          <Card
            href="/dashboard/stocks"
            icon="📊"
            color="indigo"
            title="Hisse Senedi"
            total={stockTotal}
            count={stockHoldingCount}
            countLabel="hisse"
            top={stockTop}
            placeholder="BIST + ABD + UK — Yahoo Finance"
          />

          <Card
            href="/dashboard/wallets"
            icon="⛓️"
            color="purple"
            title="Blockchain Cüzdanlar"
            total={walletTotal}
            loading={walletLoading}
            top={walletTop}
            placeholder="Sonic, Avalanche, Ethereum"
          />

          <Card
            href="/dashboard/bes"
            icon="🏦"
            color="green"
            title="BES"
            total={besTotal}
            count={besPlanCount}
            countLabel="plan"
            top={besTop}
            placeholder="Bireysel emeklilik — manuel giriş"
          />

          <Card
            href="/dashboard/expenses"
            icon="💸"
            color="red"
            title="Harcamalar (bu ay)"
            total={expenseTotal}
            count={expenseCount}
            countLabel="kayıt"
            top={expenseTop}
            placeholder="Aylık gider takibi"
          />
        </div>
      </main>

      <footer className="mt-auto py-4 flex flex-col items-center gap-2">
        <div className="flex justify-center items-center gap-2">
          <span className="text-xs text-gray-300">Bir</span>
          <Image src="/images/mayotek-logo.png" alt="Mayotek" width={64} height={22} />
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

const COLOR_MAP: Record<string, { bg: string; bgHover: string; ring: string; text: string }> = {
  blue:   { bg: "bg-blue-50",   bgHover: "group-hover:bg-blue-100",   ring: "hover:border-blue-100",   text: "text-blue-600" },
  orange: { bg: "bg-orange-50", bgHover: "group-hover:bg-orange-100", ring: "hover:border-orange-100", text: "text-orange-500" },
  indigo: { bg: "bg-indigo-50", bgHover: "group-hover:bg-indigo-100", ring: "hover:border-indigo-100", text: "text-indigo-600" },
  purple: { bg: "bg-purple-50", bgHover: "group-hover:bg-purple-100", ring: "hover:border-purple-100", text: "text-purple-600" },
  green:  { bg: "bg-green-50",  bgHover: "group-hover:bg-green-100",  ring: "hover:border-green-100",  text: "text-green-600" },
  red:    { bg: "bg-red-50",    bgHover: "group-hover:bg-red-100",    ring: "hover:border-red-100",    text: "text-red-600" },
};

interface CardProps {
  href: string;
  icon: string;
  color: keyof typeof COLOR_MAP;
  title: string;
  total: number | null;
  count?: number;
  countLabel?: string;
  loading?: boolean;
  top: TopItem[];
  placeholder: string;
}

function Card({ href, icon, color, title, total, count, countLabel, loading, top, placeholder }: CardProps) {
  const router = useRouter();
  const c = COLOR_MAP[color];
  const hasTotal = total !== null && total > 0;

  return (
    <button
      onClick={() => router.push(href)}
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-6 text-left hover:shadow-md ${c.ring} transition-all group`}
    >
      <div className={`w-10 h-10 ${c.bg} rounded-xl flex items-center justify-center mb-4 ${c.bgHover} transition-colors`}>
        <span className="text-xl">{icon}</span>
      </div>
      <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>

      {hasTotal && (
        <p className={`text-sm font-semibold ${c.text}`}>{fmtTL(total)} ₺</p>
      )}
      {!hasTotal && (count ?? 0) > 0 && (
        <p className="text-sm text-gray-400">{count} {countLabel} · yükleniyor...</p>
      )}
      {!hasTotal && (count ?? 0) === 0 && loading && (
        <p className="text-sm text-gray-400">yükleniyor...</p>
      )}
      {!hasTotal && (count ?? 0) === 0 && !loading && (
        <p className="text-sm text-gray-400">{placeholder}</p>
      )}

      {top.length > 0 && (
        <ul className="mt-4 pt-3 border-t border-gray-50 space-y-1">
          {top.map((it) => (
            <li key={it.label} className="flex justify-between text-xs text-gray-500">
              <span className="truncate font-mono">{it.label}</span>
              <span className="font-medium tabular-nums ml-2 shrink-0">{fmtTL(it.value)} ₺</span>
            </li>
          ))}
        </ul>
      )}
    </button>
  );
}
