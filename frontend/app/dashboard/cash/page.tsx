"use client";
import { useEffect, useState, useCallback, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, CashCurrency, CashSummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { TLValue } from "@/app/_components/TLValue";
import { fmtNum, INPUT_CLS } from "@/lib/format";

const CURRENCIES: CashCurrency[] = ["TRY", "USD", "EUR", "GBP"];

export default function CashPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<CashSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Form state
  const [label, setLabel] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<CashCurrency>("TRY");
  const [notes, setNotes] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.listCash());
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!label.trim() || !amount.trim()) { setError("Etiket ve tutar zorunlu"); return; }
    setSaving(true);
    setError("");
    try {
      await api.createCash({
        label: label.trim(),
        amount: parseFloat(amount),
        currency,
        notes: notes.trim() || null,
      });
      setLabel(""); setAmount(""); setNotes(""); setCurrency("TRY");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, lbl: string) {
    if (!confirm(`"${lbl}" silinsin mi?`)) return;
    try {
      await api.deleteCash(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silme başarısız");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Nakit / Banka Hesapları" />

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {/* Özet panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <p className="text-xs text-gray-400 mb-1">Toplam nakit</p>
          {summary && (
            <TLValue tl={summary.total_tl} className="text-3xl font-bold text-gray-900" usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums" />
          )}
          {summary && (
            <p className="text-xs text-gray-400 mt-1">{summary.holdings.length} hesap</p>
          )}
        </div>

        {/* Yeni hesap formu */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Yeni Nakit Kaydı</h2>
          <div className="flex gap-2 flex-wrap">
            <input
              placeholder="Etiket (Akbank Vadesiz, Cüzdan...)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={`flex-1 min-w-[200px] ${INPUT_CLS}`}
              maxLength={100}
            />
            <input
              type="number"
              placeholder="Tutar"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="0"
              step="0.01"
              className={`w-36 ${INPUT_CLS}`}
            />
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value as CashCurrency)}
              className={`w-24 ${INPUT_CLS}`}
            >
              {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <input
            placeholder="Not (opsiyonel)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={`w-full ${INPUT_CLS}`}
            maxLength={500}
          />
          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Kaydediliyor..." : "Ekle"}
          </button>
        </form>

        {/* Liste */}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && summary && summary.holdings.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">Henüz nakit kaydı yok.</p>
        )}
        {!loading && summary && summary.holdings.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-6 py-3 text-left">Etiket</th>
                  <th className="px-6 py-3 text-right">Tutar</th>
                  <th className="px-6 py-3 text-right">TL Karşılığı</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {summary.holdings.map((h) => (
                  <tr key={h.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <p className="font-medium text-gray-900">{h.label}</p>
                      {h.notes && <p className="text-xs text-gray-400 mt-0.5">{h.notes}</p>}
                    </td>
                    <td className="px-6 py-4 text-right text-gray-700 tabular-nums">
                      {fmtNum(h.amount, 2)} {h.currency}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <TLValue tl={h.amount_tl} className="font-semibold text-gray-900" />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(h.id, h.label)}
                        className="text-gray-400 hover:text-red-500 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                        title="Sil"
                        aria-label={`${h.label} kaydını sil`}
                      >
                        <span aria-hidden="true">✕</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
