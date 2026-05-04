"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, SnapshotHistoryDTO } from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";

interface ChartPoint {
  date: string;          // "2026-04-26" formatında
  total: number;
  crypto: number;
  fund: number;
  pension: number;
  stock: number;
  cash: number;
}

function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function snapshotToPoint(s: SnapshotHistoryDTO): ChartPoint {
  const totals = { crypto: 0, fund: 0, pension: 0, stock: 0, cash: 0 };
  for (const pos of s.asset_positions) {
    const v = parseFloat(pos.total_value_tl);
    if (pos.asset_type in totals) {
      (totals as Record<string, number>)[pos.asset_type] += v;
    }
  }
  return {
    date: s.snapshot_date,
    total: parseFloat(s.total_value_tl),
    ...totals,
  };
}

export default function HistoryPage() {
  const router = useRouter();
  const [points, setPoints] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
      return;
    }
    api.getPortfolioHistory(12)
      .then((snapshots) => {
        // Backend desc order ile döndürür; chart için artan tarih sıralaması
        const sorted = [...snapshots].sort((a, b) =>
          a.snapshot_date.localeCompare(b.snapshot_date)
        );
        setPoints(sorted.map(snapshotToPoint));
      })
      .catch((err) => {
        if (err instanceof Error && err.message.includes("401")) {
          handle401();
          return;
        }
        setError(err instanceof Error ? err.message : "Geçmiş yüklenemedi");
      })
      .finally(() => setLoading(false));
  }, [router, handle401]);

  const latest = points.length > 0 ? points[points.length - 1] : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ← Geri
        </button>
        <h1 className="text-lg font-semibold text-gray-900">Portföy Geçmişi</h1>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {loading && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
            <p className="text-sm text-gray-400">Yükleniyor...</p>
          </div>
        )}

        {error && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {!loading && !error && points.length === 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center space-y-2">
            <p className="text-sm font-semibold text-gray-700">Henüz snapshot yok</p>
            <p className="text-xs text-gray-400">
              Dashboard&apos;a dönüp <strong>&quot;Snapshot al&quot;</strong> butonuna basın.
              Otomatik haftalık snapshot Pazar 23:00&apos;da çalışır.
            </p>
          </div>
        )}

        {!loading && points.length > 0 && (
          <>
            {latest && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                <p className="text-xs text-gray-400 mb-1">Son snapshot ({fmtDate(latest.date)})</p>
                <TLValue tl={latest.total} className="text-3xl font-bold text-gray-900" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
              </div>
            )}

            {/* Toplam değer eğrisi */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Toplam Portföy Değeri</h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={points} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} stroke="#9ca3af" />
                    <YAxis
                      tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                      fontSize={11}
                      stroke="#9ca3af"
                    />
                    <Tooltip
                      formatter={(v) => `${fmtTL(v as number)} ₺`}
                      labelFormatter={(label) => fmtDate(label as string)}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke="#2563eb"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                      name="Toplam"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Varlık tipi bazlı kırılım */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Varlık Tipine Göre</h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={points} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} stroke="#9ca3af" />
                    <YAxis
                      tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                      fontSize={11}
                      stroke="#9ca3af"
                    />
                    <Tooltip
                      formatter={(v) => `${fmtTL(v as number)} ₺`}
                      labelFormatter={(label) => fmtDate(label as string)}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="crypto" stroke="#f97316" strokeWidth={1.5} dot={{ r: 2 }} name="Kripto" />
                    <Line type="monotone" dataKey="fund" stroke="#2563eb" strokeWidth={1.5} dot={{ r: 2 }} name="TEFAS" />
                    <Line type="monotone" dataKey="stock" stroke="#6366f1" strokeWidth={1.5} dot={{ r: 2 }} name="Hisse" />
                    <Line type="monotone" dataKey="pension" stroke="#16a34a" strokeWidth={1.5} dot={{ r: 2 }} name="BES" />
                    <Line type="monotone" dataKey="cash" stroke="#6b7280" strokeWidth={1.5} dot={{ r: 2 }} name="Nakit" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <p className="text-xs text-gray-400 text-center">
              Son {points.length} snapshot gösteriliyor. Daha fazla geçmiş için haftalık otomatik
              snapshot&apos;ın (Pazar 23:00) çalışmasını bekleyin.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
