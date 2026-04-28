"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
    api.getIntegrations().then((integrations) => {
      const hasCrypto = integrations.some((i) => i.provider === "binance" || i.provider === "icrypex");
      if (!hasCrypto) { setCryptoLoading(false); return; }
      api.getCryptoPositions().then(({ positions }) => {
        const filtered = positions.filter((p) => parseFloat(p.total_value_tl) > 0.01);
        const total = filtered.reduce((s, p) => s + parseFloat(p.total_value_tl), 0);
        setCryptoTotal(total);
      }).catch(() => {}).finally(() => setCryptoLoading(false));
    }).catch(() => setCryptoLoading(false));
  }, [router]);

  function logout() {
    clearAuth();
    router.push("/login");
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
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Portföy</h2>

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

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 opacity-50 cursor-not-allowed">
            <div className="w-10 h-10 bg-green-50 rounded-xl flex items-center justify-center mb-4">
              <span className="text-xl">🏦</span>
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">BES</h3>
            <p className="text-sm text-gray-400">Bireysel emeklilik — yakında</p>
          </div>
        </div>
      </main>

      <footer className="mt-auto py-4 flex justify-center items-center gap-2">
        <span className="text-xs text-gray-300">Bir</span>
        <Image src="/images/mayotek-logo.png" alt="Mayotek" width={64} height={22} />
        <span className="text-xs text-gray-300">ürünüdür</span>
      </footer>
    </div>
  );
}
