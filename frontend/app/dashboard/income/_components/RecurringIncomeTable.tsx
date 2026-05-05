"use client";
import { useState } from "react";
import {
  api,
  RecurringIncomeDTO,
  RECURRING_INCOME_CATEGORY_LABELS,
  RECURRING_RECURRENCE_LABELS,
} from "@/lib/api";
import { fmtTL } from "@/lib/format";

interface Props {
  items: RecurringIncomeDTO[];
  onDeleted: (id: number) => void;
  onEdit: (item: RecurringIncomeDTO) => void;
  onRefresh: () => void;
}

const MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export function RecurringIncomeTable({ items, onDeleted, onEdit, onRefresh }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  async function handleDelete(id: number, title: string) {
    if (!confirm(`"${title}" periyodik gelir kaydı silinsin mi?\nNot: bu kayıttan oluşmuş gerçekleşmiş gelirler korunur (sadece bağlantı kopar).`)) return;
    setBusy(`del-${id}`);
    setMsg("");
    try {
      await api.deleteRecurringIncome(id);
      onDeleted(id);
    } catch {
      setMsg("Silinemedi");
    } finally {
      setBusy(null);
    }
  }

  async function handleRealizeThisMonth(it: RecurringIncomeDTO) {
    const now = new Date();
    setBusy(`r-${it.id}`);
    setMsg("");
    try {
      const r = await api.realizeRecurringPeriod(it.id, now.getFullYear(), now.getMonth() + 1);
      if (r.realized > 0) setMsg(`✓ "${it.title}" bu ay gerçekleşti olarak işaretlendi`);
      else setMsg(`"${it.title}" zaten bu ay için gerçekleştirilmiş — atlandı`);
      onRefresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "İşlem başarısız");
    } finally {
      setBusy(null);
    }
  }

  async function handleRealizePast(it: RecurringIncomeDTO) {
    if (!confirm(`"${it.title}" için ${it.start_date} tarihinden bugüne kadar olan TÜM geçmiş dönemler gelir kaydı olarak oluşturulacak. Devam edilsin mi?`)) return;
    setBusy(`rp-${it.id}`);
    setMsg("");
    try {
      const r = await api.realizeRecurringPast(it.id);
      setMsg(`✓ "${it.title}": ${r.realized} dönem gerçekleştirildi, ${r.skipped} atlandı (zaten vardı)`);
      onRefresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "İşlem başarısız");
    } finally {
      setBusy(null);
    }
  }

  async function handleRealizeAllPast() {
    if (!items.length) return;
    if (!confirm(`TÜM ${items.length} periyodik kayıt için bugüne kadar olan tüm geçmiş dönemler gelir olarak oluşturulacak. Devam edilsin mi?`)) return;
    setBusy("all-past");
    setMsg("");
    try {
      const r = await api.realizeAllRecurringPast();
      setMsg(`✓ Toplu işlem: ${r.realized} dönem gerçekleştirildi, ${r.skipped} atlandı`);
      onRefresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "İşlem başarısız");
    } finally {
      setBusy(null);
    }
  }

  if (!items.length) {
    return <p className="text-center text-sm text-gray-400 py-8">Henüz periyodik gelir kaydı yok.</p>;
  }

  return (
    <div className="space-y-3">
      {/* Toplu işlem toolbar */}
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <p className="text-xs text-gray-500">
          {items.length} periyodik kayıt. Geçmiş dönemleri toplu olarak gerçekleşmiş gelir kaydına çevir:
        </p>
        <button
          type="button"
          onClick={handleRealizeAllPast}
          disabled={busy === "all-past"}
          className="text-xs font-medium px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy === "all-past" ? "İşleniyor..." : "Tümünün Geçmişini Gerçekleştir"}
        </button>
      </div>

      {msg && (
        <p className={`text-xs px-3 py-2 rounded-lg border ${
          msg.startsWith("✓") ? "bg-emerald-50 border-emerald-100 text-emerald-700" : "bg-red-50 border-red-100 text-red-700"
        }`}>{msg}</p>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
              <th className="px-4 py-3 text-left">Başlık</th>
              <th className="px-4 py-3 text-left">Kategori</th>
              <th className="px-4 py-3 text-left">Periyot</th>
              <th className="px-4 py-3 text-left">Tarih aralığı</th>
              <th className="px-4 py-3 text-right">Tutar</th>
              <th className="px-4 py-3 text-right">İşlemler</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map((it) => {
              const monthsLabel = it.recurrence === "custom" && it.months?.length
                ? it.months.map((m) => MONTH_NAMES[m - 1]).join(", ")
                : null;
              return (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{it.title}</p>
                    {it.notes && <p className="text-xs text-gray-400 mt-0.5">{it.notes}</p>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{RECURRING_INCOME_CATEGORY_LABELS[it.category]}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {RECURRING_RECURRENCE_LABELS[it.recurrence]}
                    {monthsLabel && <span className="block text-xs text-gray-400">{monthsLabel}</span>}
                    <span className="block text-xs text-gray-400">{it.day_of_month}. gün</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">
                    {it.start_date}
                    <br />
                    {it.end_date ? `→ ${it.end_date}` : "→ süresiz"}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-emerald-600 tabular-nums">
                    {fmtTL(parseFloat(it.amount))} ₺
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => handleRealizeThisMonth(it)}
                        disabled={busy === `r-${it.id}`}
                        className="text-xs px-2 py-1 rounded text-emerald-700 border border-emerald-200 hover:bg-emerald-50 disabled:opacity-50"
                        title="Bu ay'ı gerçekleşti olarak işaretle"
                      >
                        Bu ay ✓
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRealizePast(it)}
                        disabled={busy === `rp-${it.id}`}
                        className="text-xs px-2 py-1 rounded text-blue-700 border border-blue-200 hover:bg-blue-50 disabled:opacity-50"
                        title="Geçmiş tüm dönemleri gerçekleştir"
                      >
                        Geçmişi ✓
                      </button>
                      <button
                        type="button"
                        onClick={() => onEdit(it)}
                        className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                        title="Düzenle"
                      >
                        Düzenle
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(it.id, it.title)}
                        disabled={busy === `del-${it.id}`}
                        className="text-gray-400 hover:text-red-500 text-sm disabled:opacity-50"
                        title="Sil"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
