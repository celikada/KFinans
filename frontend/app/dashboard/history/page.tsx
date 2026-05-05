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
import { api, SnapshotHealthIssue, SnapshotHistoryDTO } from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";

type Currency = "TRY" | "USD";

interface ChartPoint {
  date: string;          // "2026-04-26" formatında
  total: number;
  crypto: number;
  fund: number;
  pension: number;
  stock: number;
  cash: number;
  commodity: number;
  rate: number | null;   // Snapshot anındaki USD/TRY (geçmiş USD eğimi için)
  issues: SnapshotHealthIssue[];
}

function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtUSD(val: number) {
  return val.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function snapshotToPoint(s: SnapshotHistoryDTO): ChartPoint {
  const totals = { crypto: 0, fund: 0, pension: 0, stock: 0, cash: 0, commodity: 0 };
  for (const pos of s.asset_positions) {
    const v = parseFloat(pos.total_value_tl);
    if (pos.asset_type in totals) {
      (totals as Record<string, number>)[pos.asset_type] += v;
    }
  }
  return {
    date: s.snapshot_date,
    total: parseFloat(s.total_value_tl),
    rate: s.usd_try_rate ? parseFloat(s.usd_try_rate) : null,
    issues: s.health_issues ?? [],
    ...totals,
  };
}

/** TL veya USD'ye dönüştür. Snapshot'ın kendi rate'i yoksa 0 dönülür (görselde gizlenir). */
function valueIn(point: ChartPoint, key: keyof Pick<ChartPoint, "total"|"crypto"|"fund"|"pension"|"stock"|"cash"|"commodity">, currency: Currency): number {
  const tl = point[key];
  if (currency === "TRY") return tl;
  if (point.rate && point.rate > 0) return tl / point.rate;
  return 0;
}

export default function HistoryPage() {
  const router = useRouter();
  const [points, setPoints] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currency, setCurrency] = useState<Currency>("TRY");
  const [openIssues, setOpenIssues] = useState<{ date: string; issues: SnapshotHealthIssue[] } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
      return;
    }
    api.getPortfolioHistory(12)
      .then((snapshots) => {
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

  async function handleDelete(snapshotDate: string) {
    setDeleting(true);
    try {
      await api.deleteSnapshot(snapshotDate);
      setPoints((prev) => prev.filter((p) => p.date !== snapshotDate));
      setConfirmDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Snapshot silinemedi");
    } finally {
      setDeleting(false);
    }
  }

  // Currency dönüşümlü grafik veri seti
  const chartData = points.map((p) => ({
    ...p,
    total: valueIn(p, "total", currency),
    crypto: valueIn(p, "crypto", currency),
    fund: valueIn(p, "fund", currency),
    pension: valueIn(p, "pension", currency),
    stock: valueIn(p, "stock", currency),
    cash: valueIn(p, "cash", currency),
    commodity: valueIn(p, "commodity", currency),
  }));

  const sym = currency === "TRY" ? "₺" : "$";
  const fmtVal = (v: number) => currency === "TRY" ? `${fmtTL(v)} ${sym}` : `${sym}${fmtUSD(v)}`;
  const yAxisFmt = (v: number) => currency === "TRY" ? `${(v / 1000).toFixed(0)}K` : `${sym}${(v / 1000).toFixed(0)}K`;

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
        {/* TL/USD toggle */}
        <div className="ml-auto inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">
          {(["TRY", "USD"] as Currency[]).map((c) => (
            <button
              key={c}
              onClick={() => setCurrency(c)}
              className={`px-3 py-1.5 font-medium transition-colors ${
                currency === c
                  ? "bg-blue-600 text-white"
                  : "bg-white text-gray-500 hover:text-gray-800"
              }`}
            >
              {c === "TRY" ? "₺ TL" : "$ USD"}
            </button>
          ))}
        </div>
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
                {currency === "TRY" ? (
                  <TLValue tl={latest.total} className="text-3xl font-bold text-gray-900" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
                ) : (
                  <p className="text-3xl font-bold text-gray-900 tabular-nums">
                    {latest.rate && latest.rate > 0
                      ? `$${fmtUSD(latest.total / latest.rate)}`
                      : "—"}
                  </p>
                )}
              </div>
            )}

            {/* Sağlık uyarıları rozet listesi */}
            {points.some((p) => p.issues.length > 0) && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <p className="text-xs text-gray-500 mb-2">Sorunlu snapshotlar (üzerine tıklayın):</p>
                <div className="flex flex-wrap gap-2">
                  {points.filter((p) => p.issues.length > 0).map((p) => (
                    <button
                      key={p.date}
                      onClick={() => setOpenIssues({ date: p.date, issues: p.issues })}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs hover:bg-amber-100"
                    >
                      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-500 text-white text-[10px] font-bold">!</span>
                      {fmtDate(p.date)} · {p.issues.length}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Toplam değer eğrisi */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Toplam Portföy Değeri ({currency === "TRY" ? "₺ TL" : "$ USD"})
              </h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} stroke="#9ca3af" />
                    <YAxis tickFormatter={yAxisFmt} fontSize={11} stroke="#9ca3af" />
                    <Tooltip
                      formatter={(v) => fmtVal(v as number)}
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
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} stroke="#9ca3af" />
                    <YAxis tickFormatter={yAxisFmt} fontSize={11} stroke="#9ca3af" />
                    <Tooltip
                      formatter={(v) => fmtVal(v as number)}
                      labelFormatter={(label) => fmtDate(label as string)}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="crypto" stroke="#f97316" strokeWidth={1.5} dot={{ r: 2 }} name="Kripto" />
                    <Line type="monotone" dataKey="fund" stroke="#2563eb" strokeWidth={1.5} dot={{ r: 2 }} name="TEFAS" />
                    <Line type="monotone" dataKey="stock" stroke="#6366f1" strokeWidth={1.5} dot={{ r: 2 }} name="Hisse" />
                    <Line type="monotone" dataKey="pension" stroke="#16a34a" strokeWidth={1.5} dot={{ r: 2 }} name="BES" />
                    <Line type="monotone" dataKey="cash" stroke="#6b7280" strokeWidth={1.5} dot={{ r: 2 }} name="Nakit" />
                    <Line type="monotone" dataKey="commodity" stroke="#d97706" strokeWidth={1.5} dot={{ r: 2 }} name="Altın/Gümüş" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Snapshot listesi (tarih + tutar + sil) */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700">Snapshotlar</h2>
              </div>
              <ul className="divide-y divide-gray-50">
                {[...points].reverse().map((p) => (
                  <li key={p.date} className="px-6 py-3 flex items-center gap-3 text-sm">
                    <span className="font-medium text-gray-700 tabular-nums w-24">{fmtDate(p.date)}</span>
                    <span className="text-gray-500 tabular-nums flex-1">
                      {fmtTL(p.total)} ₺
                      {p.rate && p.rate > 0 && (
                        <span className="text-gray-400 ml-2">≈ ${fmtUSD(p.total / p.rate)}</span>
                      )}
                    </span>
                    {p.issues.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setOpenIssues({ date: p.date, issues: p.issues })}
                        className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] font-bold"
                        title={`${p.issues.length} uyarı`}
                      >
                        !
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(p.date)}
                      className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50"
                    >
                      Sil
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-xs text-gray-400 text-center">
              Son {points.length} snapshot. {currency === "USD" && (
                <>
                  USD değerleri her snapshot&apos;ın <em>kendi</em> kayıt anındaki USD/TRY kuruyla
                  hesaplanır — TL enflasyonundan etkilenmez.
                </>
              )}
            </p>
          </>
        )}
      </main>

      {/* Silme onayı */}
      {confirmDelete && (
        <div
          role="presentation"
          onClick={() => setConfirmDelete(null)}
          onKeyDown={(e) => { if (e.key === "Escape") setConfirmDelete(null); }}
          className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-sm w-full text-left cursor-default"
          >
            <h3 className="text-base font-semibold text-gray-900 mb-2">Snapshot silinsin mi?</h3>
            <p className="text-sm text-gray-600 mb-4">
              <strong>{fmtDate(confirmDelete)}</strong> tarihli snapshot ve içindeki tüm pozisyonlar
              kalıcı olarak silinecek. Bu işlem geri alınamaz.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                İptal
              </button>
              <button
                type="button"
                onClick={() => handleDelete(confirmDelete)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Siliniyor…" : "Evet, sil"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Health issues popup */}
      {openIssues && (
        <div
          role="presentation"
          onClick={() => setOpenIssues(null)}
          onKeyDown={(e) => { if (e.key === "Escape") setOpenIssues(null); }}
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
              const warns = openIssues.issues.filter((i) => (i.level ?? "warn") === "warn");
              const infos = openIssues.issues.filter((i) => i.level === "info");
              return (
                <>
                  <h3 className="text-base font-semibold text-gray-900 mb-1">
                    {fmtDate(openIssues.date)} snapshot notları
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">
                    {warns.length > 0 && <span className="text-amber-700">{warns.length} sorun</span>}
                    {warns.length > 0 && infos.length > 0 && " · "}
                    {infos.length > 0 && <span className="text-blue-700">{infos.length} bilgi (manuel/bağlı)</span>}
                  </p>
                  <ul className="space-y-2 max-h-80 overflow-y-auto">
                    {openIssues.issues.map((iss, i) => {
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
                          <p className="text-[10px] text-gray-400 mt-0.5">code: {iss.code}</p>
                        </li>
                      );
                    })}
                  </ul>
                </>
              );
            })()}
            <button
              type="button"
              onClick={() => setOpenIssues(null)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
            >
              Kapat
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
