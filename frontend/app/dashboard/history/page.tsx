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
import { useTranslation } from "@/app/_i18n/I18nProvider";

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
    const v = Number.parseFloat(pos.total_value_tl);
    if (pos.asset_type in totals) {
      (totals as Record<string, number>)[pos.asset_type] += v;
    }
  }
  return {
    date: s.snapshot_date,
    total: Number.parseFloat(s.total_value_tl),
    rate: s.usd_try_rate ? Number.parseFloat(s.usd_try_rate) : null,
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
  const { t } = useTranslation();
  const [points, setPoints] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currency, setCurrency] = useState<Currency>("TRY");
  const [openIssues, setOpenIssues] = useState<{ date: string; issues: SnapshotHealthIssue[] } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | "all">("all");

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    api.getPortfolioHistoryYears().then(setAvailableYears).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: { limit?: number; year?: number } = { limit: 365 };
    if (selectedYear !== "all") params.year = selectedYear;
    api.getPortfolioHistory(params)
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
        setError(err instanceof Error ? err.message : t("content.history.loadFailed"));
      })
      .finally(() => setLoading(false));
  }, [selectedYear, handle401, t]);

  const latest = points.length > 0 ? points[points.length - 1] : null;

  async function handleDelete(snapshotDate: string) {
    setDeleting(true);
    try {
      await api.deleteSnapshot(snapshotDate);
      setPoints((prev) => prev.filter((p) => p.date !== snapshotDate));
      setConfirmDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.history.deleteFailed"));
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
          {t("common.back")}
        </button>
        <h1 className="text-lg font-semibold text-gray-900">{t("pages.history")}</h1>

        {/* Yıl seçici */}
        {availableYears.length > 0 && (
          <select
            value={selectedYear}
            onChange={(e) => {
              const v = e.target.value;
              setSelectedYear(v === "all" ? "all" : Number.parseInt(v));
            }}
            className="ml-auto text-xs px-3 py-1.5 border border-gray-200 rounded-lg bg-white text-gray-700 hover:border-gray-300"
            aria-label={t("content.history.yearFilterAria")}
          >
            <option value="all">{t("content.history.allYears")}</option>
            {availableYears.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        )}

        {/* TL/USD toggle */}
        <div className={`${availableYears.length > 0 ? "" : "ml-auto"} inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs`}>
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
              {c === "TRY" ? t("content.history.tlToggle") : t("content.history.usdToggle")}
            </button>
          ))}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {loading && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
            <p className="text-sm text-gray-400">{t("content.history.loading")}</p>
          </div>
        )}

        {error && (
          <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {!loading && !error && points.length === 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center space-y-2">
            <p className="text-sm font-semibold text-gray-700">{t("content.history.noSnapshotTitle")}</p>
            <p className="text-xs text-gray-400">
              {t("content.history.noSnapshotHintPre")} <strong>{t("content.history.noSnapshotHintBtn")}</strong> {t("content.history.noSnapshotHintPost")}
            </p>
          </div>
        )}

        {!loading && points.length > 0 && (
          <>
            {latest && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                <p className="text-xs text-gray-400 mb-1">{t("content.history.lastSnapshot")} ({fmtDate(latest.date)})</p>
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
                <p className="text-xs text-gray-500 mb-2">{t("content.history.problematicSnapshots")}</p>
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
                {t("content.history.totalPortfolioValue")} ({currency === "TRY" ? t("content.history.tlToggle") : t("content.history.usdToggle")})
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
                      name={t("content.history.legendTotal")}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Varlık tipi bazlı kırılım */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("content.history.byAssetType")}</h2>
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
                    <Line type="monotone" dataKey="crypto" stroke="#f97316" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendCrypto")} />
                    <Line type="monotone" dataKey="fund" stroke="#2563eb" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendTefas")} />
                    <Line type="monotone" dataKey="stock" stroke="#6366f1" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendStock")} />
                    <Line type="monotone" dataKey="pension" stroke="#16a34a" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendBes")} />
                    <Line type="monotone" dataKey="cash" stroke="#6b7280" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendCash")} />
                    <Line type="monotone" dataKey="commodity" stroke="#d97706" strokeWidth={1.5} dot={{ r: 2 }} name={t("content.history.legendGoldSilver")} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Snapshot listesi (tarih + tutar + sil) */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700">{t("content.history.snapshots")}</h2>
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
                        title={`${p.issues.length} ${t("content.history.warningCountTitle")}`}
                      >
                        !
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => api.downloadReport(`/portfolio/snapshot/${p.date}/report.xlsx`, `portfoy-${p.date}.xlsx`)}
                      className="text-xs text-gray-500 hover:text-gray-800 px-2 py-1 rounded hover:bg-gray-100"
                      title={t("content.history.xlsxTitle")}
                    >
                      📊 xlsx
                    </button>
                    <button
                      type="button"
                      onClick={() => api.downloadReport(`/portfolio/snapshot/${p.date}/report.pdf`, `portfoy-${p.date}.pdf`)}
                      className="text-xs text-gray-500 hover:text-gray-800 px-2 py-1 rounded hover:bg-gray-100"
                      title={t("content.history.pdfTitle")}
                    >
                      📄 pdf
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(p.date)}
                      className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50"
                    >
                      {t("content.history.deleteBtn")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-xs text-gray-400 text-center">
              {t("content.history.lastCountPre")} {points.length} {t("content.history.lastCountSuffix")} {currency === "USD" && (
                <>{t("content.history.usdNote")}</>
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
            <h3 className="text-base font-semibold text-gray-900 mb-2">{t("content.history.deleteConfirmTitle")}</h3>
            <p className="text-sm text-gray-600 mb-4">
              <strong>{fmtDate(confirmDelete)}</strong> {t("content.history.deleteConfirmBodySuffix")}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={() => handleDelete(confirmDelete)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? t("common.deleting") : t("content.history.confirmDeleteBtn")}
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
                    {fmtDate(openIssues.date)} {t("content.history.issuesTitleSuffix")}
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">
                    {warns.length > 0 && <span className="text-amber-700">{warns.length} {t("content.history.problemsLabel")}</span>}
                    {warns.length > 0 && infos.length > 0 && " · "}
                    {infos.length > 0 && <span className="text-blue-700">{infos.length} {t("content.history.infoLabel")}</span>}
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
              {t("content.history.close")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
