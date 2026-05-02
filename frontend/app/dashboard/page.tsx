"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { api, clearAuth } from "@/lib/api";

function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function DashboardPage() {
  const router = useRouter();
  const [tefasTotal, setTefasTotal] = useState<number | null>(null);
  const [tefasFundCount, setTefasFundCount] = useState(0);
  const [cryptoTotal, setCryptoTotal] = useState<number | null>(null);
  const [cryptoLoading, setCryptoLoading] = useState(false);
  const [besTotal, setBesTotal] = useState<number | null>(null);
  const [besPlanCount, setBesPlanCount] = useState(0);
  const [snapshotting, setSnapshotting] = useState(false);
  const [snapshotMsg, setSnapshotMsg] = useState("");

  useEffect(() => {
    api.getTefasHoldings().then((holdings) => {
      if (!holdings.length) return;
      setTefasFundCount(holdings.length);
      api.tefasPreview(holdings).then((positions) => {
        const total = positions.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        setTefasTotal(total);
      }).catch(() => {});
    }).catch(() => {});

    setCryptoLoading(true);
    api.getCryptoPositions().then(({ positions }) => {
      const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
      if (filtered.length === 0) return;
      const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
      setCryptoTotal(total);
    }).catch(() => {}).finally(() => setCryptoLoading(false));

    api.getBesHoldings().then((holdings) => {
      if (!holdings.length) return;
      setBesPlanCount(holdings.length);
      const total = holdings.reduce((s, h) => s + parseFloat(h.total_value_tl.toString()), 0);
      setBesTotal(total);
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <Image src="/images/kfinans-logo.png" alt="KFinans" width={80} height={85} />
        <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">
          Çıkış
        </button>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Portföy</h2>
          <button
            onClick={takeSnapshot}
            disabled={snapshotting}
            className="text-sm border border-gray-200 text-gray-600 hover:text-gray-900 hover:border-gray-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            title="Tüm kaynaklardan veri çek ve haftalık snapshot kaydet"
          >
            {snapshotting ? "Snapshot alınıyor..." : "Snapshot al"}
          </button>
        </div>
        {snapshotMsg && (
          <p className="text-xs text-gray-500 bg-gray-100 px-3 py-2 rounded-lg mb-4">{snapshotMsg}</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <button
            onClick={() => router.push("/dashboard/tefas")}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 text-left hover:shadow-md hover:border-blue-100 transition-all group"
          >
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-blue-100 transition-colors">
              <span className="text-xl">📈</span>
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">TEFAS Fonları</h3>
            {tefasTotal !== null ? (
              <p className="text-sm font-semibold text-blue-600">{fmtTL(tefasTotal)} ₺</p>
            ) : tefasFundCount > 0 ? (
              <p className="text-sm text-gray-400">{tefasFundCount} fon · yükleniyor...</p>
            ) : (
              <p className="text-sm text-gray-400">Yatırım fonu fiyatlarını canlı görüntüle</p>
            )}
          </button>

          <button
            onClick={() => router.push("/dashboard/crypto")}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 text-left hover:shadow-md hover:border-orange-100 transition-all group"
          >
            <div className="w-10 h-10 bg-orange-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-orange-100 transition-colors">
              <span className="text-xl">₿</span>
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Kripto</h3>
            {cryptoTotal !== null ? (
              <p className="text-sm font-semibold text-orange-500">{fmtTL(cryptoTotal)} ₺</p>
            ) : cryptoLoading ? (
              <p className="text-sm text-gray-400">yükleniyor...</p>
            ) : (
              <p className="text-sm text-gray-400">Binance & iCrypex</p>
            )}
          </button>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 opacity-50 cursor-not-allowed">
            <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center mb-4">
              <span className="text-xl">⛓️</span>
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Blockchain</h3>
            <p className="text-sm text-gray-400">Sonic, Avalanche, Ethereum — yakında</p>
          </div>

          <button
            onClick={() => router.push("/dashboard/bes")}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 text-left hover:shadow-md hover:border-green-100 transition-all group"
          >
            <div className="w-10 h-10 bg-green-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-green-100 transition-colors">
              <span className="text-xl">🏦</span>
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">BES</h3>
            {besTotal !== null ? (
              <p className="text-sm font-semibold text-green-600">{fmtTL(besTotal)} ₺</p>
            ) : besPlanCount > 0 ? (
              <p className="text-sm text-gray-400">{besPlanCount} plan</p>
            ) : (
              <p className="text-sm text-gray-400">Bireysel emeklilik — manuel giriş</p>
            )}
          </button>
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
