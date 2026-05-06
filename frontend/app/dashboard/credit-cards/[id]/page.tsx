"use client";
import { useEffect, useState, useCallback, FormEvent, use } from "react";
import { useRouter } from "next/navigation";
import {
  api, CreditCardDetailDTO, StatementDTO, InstallmentDTO,
  StatementInput, InstallmentInput,
} from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { fmtTL, INPUT_CLS } from "@/lib/format";

const MONTH_NAMES = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const TODAY = new Date().toISOString().slice(0, 10);

export default function CreditCardDetailPage({ params }: Readonly<{ params: Promise<{ id: string }> }>) {
  const router = useRouter();
  const { id } = use(params);
  const cardId = parseInt(id);

  const [detail, setDetail] = useState<CreditCardDetailDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDetail(await api.getCreditCardDetail(cardId));
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) { router.replace("/login"); return; }
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [cardId, router]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    refresh();
  }, [refresh, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title="Kart Detayı" back="/dashboard/credit-cards" />
        <p className="text-sm text-gray-400 text-center py-12">Yükleniyor...</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title="Kart Detayı" back="/dashboard/credit-cards" />
        <p className="text-sm text-red-500 bg-red-50 px-4 py-3 rounded-xl mx-6 my-6">{error}</p>
      </div>
    );
  }
  if (!detail) return null;

  const c = detail.card;
  const limit = c.credit_limit ? parseFloat(c.credit_limit) : null;
  const debt = parseFloat(c.current_period_debt);
  const utilization = limit ? (debt / limit) * 100 : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={c.name} back="/dashboard/credit-cards" />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Üst panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div>
            <p className="text-xs text-gray-400 mb-1">Banka / Kart</p>
            <p className="text-base font-semibold text-gray-900">{c.bank_name ?? "—"}</p>
            {c.last_4 && <p className="text-xs text-gray-500 font-mono">**** {c.last_4}</p>}
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Kesim / Son ödeme</p>
            <p className="text-sm text-gray-700">{c.statement_day}. gün → {c.payment_due_day}.</p>
            {limit !== null && (
              <p className="text-xs text-gray-400 mt-1">Limit: {fmtTL(limit)} ₺</p>
            )}
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Dönem içi borç</p>
            <p className={`text-2xl font-bold tabular-nums ${debt > 0 ? "text-rose-600" : "text-gray-400"}`}>
              {fmtTL(debt)} ₺
            </p>
            {utilization !== null && limit !== null && limit > 0 && (
              <p className="text-xs text-gray-400 mt-1">%{utilization.toFixed(0)} kullanım</p>
            )}
          </div>
        </div>

        {/* Ekstreler */}
        <StatementsSection
          cardId={cardId}
          items={detail.statements}
          onChange={refresh}
        />

        {/* Taksitler */}
        <InstallmentsSection
          cardId={cardId}
          items={detail.installments}
          onChange={refresh}
        />
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ekstreler bölümü
// ---------------------------------------------------------------------------
function StatementsSection({ cardId, items, onChange }: Readonly<{
  cardId: number;
  items: StatementDTO[];
  onChange: () => void;
}>) {
  const now = new Date();
  const [editing, setEditing] = useState<StatementDTO | null>(null);
  const [year, setYear] = useState(now.getFullYear().toString());
  const [month, setMonth] = useState((now.getMonth() + 1).toString());
  const [amount, setAmount] = useState("");
  const [stmtDate, setStmtDate] = useState(TODAY);
  const [dueDate, setDueDate] = useState(TODAY);
  const [paid, setPaid] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  function reset() {
    setEditing(null);
    setYear(now.getFullYear().toString());
    setMonth((now.getMonth() + 1).toString());
    setAmount(""); setStmtDate(TODAY); setDueDate(TODAY); setPaid(false); setNotes("");
    setErr("");
  }

  function startEdit(s: StatementDTO) {
    setEditing(s);
    setYear(s.period_year.toString());
    setMonth(s.period_month.toString());
    setAmount(s.statement_amount);
    setStmtDate(s.statement_date);
    setDueDate(s.due_date);
    setPaid(!!s.paid_at);
    setNotes(s.notes ?? "");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!amount.trim()) { setErr("Tutar zorunlu"); return; }
    setSaving(true); setErr("");
    try {
      const payload: StatementInput = {
        period_year: parseInt(year),
        period_month: parseInt(month),
        statement_amount: parseFloat(amount),
        statement_date: stmtDate,
        due_date: dueDate,
        paid_at: paid ? new Date().toISOString() : null,
        notes: notes.trim() || null,
      };
      if (editing) {
        await api.updateStatement(cardId, editing.id, payload);
      } else {
        await api.createStatement(cardId, payload);
      }
      reset();
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(s: StatementDTO) {
    if (!confirm(`${s.period_year}-${MONTH_NAMES[s.period_month - 1]} ekstresi silinsin mi?`)) return;
    try {
      await api.deleteStatement(cardId, s.id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Silme başarısız");
    }
  }

  let submitLabel: string;
  if (saving) submitLabel = "Kaydediliyor...";
  else if (editing) submitLabel = "Güncelle";
  else submitLabel = "Ekle";

  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">Aylık Ekstreler</h2>
        <span className="text-xs text-gray-400">{items.length} kayıt</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 pb-4 border-b border-gray-50">
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
          <input type="number" placeholder="Yıl" value={year} onChange={(e) => setYear(e.target.value)} min="2020" max="2100" className={INPUT_CLS} />
          <select value={month} onChange={(e) => setMonth(e.target.value)} className={INPUT_CLS}>
            {MONTH_NAMES.map((n, i) => <option key={i + 1} value={i + 1}>{n}</option>)}
          </select>
          <input type="number" placeholder="Tutar (TL)" value={amount} onChange={(e) => setAmount(e.target.value)} step="0.01" min="0" className={`sm:col-span-2 ${INPUT_CLS}`} />
          <input type="date" value={stmtDate} onChange={(e) => setStmtDate(e.target.value)} className={INPUT_CLS} title="Kesim tarihi" />
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={INPUT_CLS} title="Son ödeme" />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-gray-600 inline-flex items-center gap-2">
            <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} className="rounded" />
            Ödendi
          </label>
          <input placeholder="Notlar (ops.)" value={notes} onChange={(e) => setNotes(e.target.value)} className={`flex-1 ${INPUT_CLS}`} maxLength={500} />
        </div>
        {err && <p className="text-xs text-red-500">{err}</p>}
        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="text-sm bg-rose-600 text-white px-4 py-2 rounded-lg hover:bg-rose-700 disabled:opacity-50">{submitLabel}</button>
          {editing && <button type="button" onClick={reset} className="text-sm border border-gray-200 text-gray-600 px-4 py-2 rounded-lg">İptal</button>}
        </div>
      </form>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">Henüz ekstre kaydı yok.</p>
      ) : (
        <ul className="divide-y divide-gray-50">
          {items.map((s) => (
            <li key={s.id} className="py-3 flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {s.period_year} · {MONTH_NAMES[s.period_month - 1]}
                  {s.paid_at && <span className="ml-2 text-[10px] font-medium text-green-700 bg-green-50 px-1.5 py-0.5 rounded border border-green-200">ÖDENDİ</span>}
                </p>
                <p className="text-xs text-gray-500">Kesim: {s.statement_date} · Son ödeme: {s.due_date}</p>
                {s.notes && <p className="text-xs text-gray-400 mt-0.5">{s.notes}</p>}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-rose-600 tabular-nums">{fmtTL(parseFloat(s.statement_amount))} ₺</span>
                <button onClick={() => startEdit(s)} className="text-xs text-gray-500 hover:text-gray-800">Düzenle</button>
                <button onClick={() => handleDelete(s)} className="text-xs text-red-400 hover:text-red-600">✕</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Taksitler bölümü
// ---------------------------------------------------------------------------
function InstallmentsSection({ cardId, items, onChange }: Readonly<{
  cardId: number;
  items: InstallmentDTO[];
  onChange: () => void;
}>) {
  const [editing, setEditing] = useState<InstallmentDTO | null>(null);
  const [description, setDescription] = useState("");
  const [totalAmount, setTotalAmount] = useState("");
  const [total, setTotal] = useState("12");
  const [firstDue, setFirstDue] = useState(TODAY);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  function reset() {
    setEditing(null);
    setDescription(""); setTotalAmount(""); setTotal("12");
    setFirstDue(TODAY); setNotes(""); setErr("");
  }

  function startEdit(i: InstallmentDTO) {
    setEditing(i);
    setDescription(i.description);
    setTotalAmount(i.total_amount);
    setTotal(i.installments_total.toString());
    setFirstDue(i.first_due_date);
    setNotes(i.notes ?? "");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) { setErr("Açıklama zorunlu"); return; }
    setSaving(true); setErr("");
    try {
      const payload: InstallmentInput = {
        description: description.trim(),
        total_amount: parseFloat(totalAmount),
        installments_total: parseInt(total),
        first_due_date: firstDue,
        notes: notes.trim() || null,
      };
      if (editing) {
        await api.updateInstallment(cardId, editing.id, payload);
      } else {
        await api.createInstallment(cardId, payload);
      }
      reset();
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  }

  // Aylık tutar canlı hesaplama (form preview)
  const totalNum = parseFloat(totalAmount);
  const totalCount = parseInt(total) || 0;
  const monthlyPreview = totalNum > 0 && totalCount > 0
    ? (totalNum / totalCount).toFixed(2)
    : null;

  async function handleDelete(i: InstallmentDTO) {
    if (!confirm(`"${i.description}" taksiti silinsin mi?`)) return;
    try {
      await api.deleteInstallment(cardId, i.id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Silme başarısız");
    }
  }

  let submitLabel: string;
  if (saving) submitLabel = "Kaydediliyor...";
  else if (editing) submitLabel = "Güncelle";
  else submitLabel = "Ekle";

  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">Taksitler</h2>
        <span className="text-xs text-gray-400">{items.length} kayıt</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 pb-4 border-b border-gray-50">
        <input
          required placeholder="Açıklama (TV — MediaMarkt)" value={description}
          onChange={(e) => setDescription(e.target.value)} maxLength={200}
          className={INPUT_CLS}
        />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <input type="number" placeholder="Toplam tutar (TL)" value={totalAmount} onChange={(e) => setTotalAmount(e.target.value)} step="0.01" min="0.01" className={INPUT_CLS} />
          <input type="number" placeholder="Taksit sayısı" value={total} onChange={(e) => setTotal(e.target.value)} min="1" max="120" className={INPUT_CLS} />
          <input type="date" value={firstDue} onChange={(e) => setFirstDue(e.target.value)} className={INPUT_CLS} title="İlk taksit tarihi" />
        </div>
        {monthlyPreview && (
          <p className="text-xs text-gray-500">
            Aylık: <span className="font-semibold text-gray-700">{monthlyPreview} ₺</span> · Kalan taksit ilk vadeye göre otomatik hesaplanır.
          </p>
        )}
        <input
          placeholder="Notlar (ops.)" value={notes} onChange={(e) => setNotes(e.target.value)}
          className={INPUT_CLS} maxLength={500}
        />
        {err && <p className="text-xs text-red-500">{err}</p>}
        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="text-sm bg-rose-600 text-white px-4 py-2 rounded-lg hover:bg-rose-700 disabled:opacity-50">{submitLabel}</button>
          {editing && <button type="button" onClick={reset} className="text-sm border border-gray-200 text-gray-600 px-4 py-2 rounded-lg">İptal</button>}
        </div>
      </form>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">Henüz taksit kaydı yok.</p>
      ) : (
        <ul className="divide-y divide-gray-50">
          {items.map((i) => (
            <li key={i.id} className="py-3 flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{i.description}</p>
                <p className="text-xs text-gray-500">
                  {i.installments_remaining}/{i.installments_total} taksit kalan ·
                  ilk vade {i.first_due_date}
                </p>
                {i.notes && <p className="text-xs text-gray-400 mt-0.5">{i.notes}</p>}
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-sm font-semibold text-rose-600 tabular-nums">
                    {fmtTL(parseFloat(i.monthly_amount))} ₺/ay
                  </p>
                  <p className="text-[10px] text-gray-400">
                    Toplam: {fmtTL(parseFloat(i.total_amount))} ₺
                  </p>
                </div>
                <button onClick={() => startEdit(i)} className="text-xs text-gray-500 hover:text-gray-800">Düzenle</button>
                <button onClick={() => handleDelete(i)} className="text-xs text-red-400 hover:text-red-600">✕</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
