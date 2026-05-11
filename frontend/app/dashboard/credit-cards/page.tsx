"use client";
import { useEffect, useState, useCallback, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, CreditCardDTO, CreditCardInput, CreditCardSummaryDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { TLValue } from "@/app/_components/TLValue";
import { fmtTL, INPUT_CLS } from "@/lib/format";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useConfirm } from "@/app/_components/ConfirmDialog";

export default function CreditCardsPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [summary, setSummary] = useState<CreditCardSummaryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<CreditCardDTO | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [bankName, setBankName] = useState("");
  const [last4, setLast4] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [statementDay, setStatementDay] = useState("1");
  const [paymentDueDay, setPaymentDueDay] = useState("10");
  const [currentDebt, setCurrentDebt] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.listCreditCards());
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

  function startEdit(c: CreditCardDTO) {
    setEditing(c);
    setName(c.name);
    setBankName(c.bank_name ?? "");
    setLast4(c.last_4 ?? "");
    setCreditLimit(c.credit_limit ?? "");
    setStatementDay(c.statement_day.toString());
    setPaymentDueDay(c.payment_due_day.toString());
    setCurrentDebt(c.current_period_debt);
    setNotes(c.notes ?? "");
  }

  function cancelEdit() {
    setEditing(null);
    setName(""); setBankName(""); setLast4("");
    setCreditLimit(""); setStatementDay("1"); setPaymentDueDay("10");
    setCurrentDebt(""); setNotes("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Kart adı zorunlu");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: CreditCardInput = {
        name: name.trim(),
        bank_name: bankName.trim() || null,
        last_4: last4.trim() || null,
        credit_limit: creditLimit.trim() ? parseFloat(creditLimit) : null,
        statement_day: parseInt(statementDay) || 1,
        payment_due_day: parseInt(paymentDueDay) || 10,
        current_period_debt: currentDebt.trim() ? parseFloat(currentDebt) : 0,
        notes: notes.trim() || null,
      };
      if (editing) {
        await api.updateCreditCard(editing.id, payload);
      } else {
        await api.createCreditCard(payload);
      }
      cancelEdit();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, cardName: string) {
    if (!(await confirm(`"${cardName}" kartı silinsin mi? Bu kartla ilişkili ileride eklenecek ekstreler ve taksitler de silinecek.`))) return;
    try {
      await api.deleteCreditCard(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silme başarısız");
    }
  }

  const totalDebtAll = summary ? parseFloat(summary.total_debt) : 0;
  const totalPeriodAll = summary ? parseFloat(summary.total_period_debt) : 0;
  const cards = summary?.cards ?? [];
  // Birden fazla ödenmemiş ekstresi olan kartlar (data hijyeni uyarısı)
  const cardsWithMultipleUnpaid = cards.filter((c) => c.unpaid_statement_count >= 2);

  let submitLabel: string;
  if (saving) submitLabel = "Kaydediliyor...";
  else if (editing) submitLabel = "Güncelle";
  else submitLabel = "Ekle";

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title={t("pages.creditCards")} />

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Birden fazla ödenmemiş ekstre uyarısı */}
        {cardsWithMultipleUnpaid.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
            <p className="font-medium mb-1">⚠ {cardsWithMultipleUnpaid.length} kartta birden fazla ödenmemiş ekstre var</p>
            <p className="text-xs text-amber-800">
              Normalde ödenmemiş ekstre bir sonraki ekstreye devreder. Aşağıdaki kart(lar)da fazla ödenmemiş ekstre kayıtı bulunduğu için <strong>çift sayım yapılıyor olabilir</strong>:
              <strong> {cardsWithMultipleUnpaid.map((c) => `${c.name} (${c.unpaid_statement_count})`).join(", ")}</strong>.
              Detayına gidip eski olanları "Ödendi" olarak işaretle ya da sil.
            </p>
          </div>
        )}

        {/* Özet panel: 2 metrik */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <p className="text-xs text-gray-400 mb-1">Toplam borç</p>
            <TLValue
              tl={totalDebtAll}
              className="text-3xl font-bold text-rose-600"
              usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums"
            />
            <p className="text-xs text-gray-400 mt-1">Dönem içi + gelecek taksitler · {cards.length} kart</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Dönem içi borç</p>
            <TLValue
              tl={totalPeriodAll}
              className="text-3xl font-bold text-rose-500"
              usdClassName="block text-sm text-gray-400 font-normal mt-1 tabular-nums"
            />
            <p className="text-xs text-gray-400 mt-1">Ödenmemiş ekstre + henüz ekstreye düşmemiş</p>
          </div>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-3"
        >
          <h3 className="text-sm font-semibold text-gray-700">{editing ? "Kartı düzenle" : "Yeni kart"}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              required
              placeholder="Kart adı (Akbank Visa)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`sm:col-span-2 ${INPUT_CLS}`}
              maxLength={100}
            />
            <input
              placeholder="Banka adı (ops.)"
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              className={INPUT_CLS}
              maxLength={60}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <input
              placeholder="Son 4 hane"
              value={last4}
              onChange={(e) => setLast4(e.target.value)}
              maxLength={4}
              pattern="\d{4}"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder="Limit (TL, ops.)"
              value={creditLimit}
              onChange={(e) => setCreditLimit(e.target.value)}
              min="0"
              step="0.01"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder="Kesim günü (1-28)"
              value={statementDay}
              onChange={(e) => setStatementDay(e.target.value)}
              min="1"
              max="28"
              className={INPUT_CLS}
            />
            <input
              type="number"
              placeholder="Son ödeme (1-28)"
              value={paymentDueDay}
              onChange={(e) => setPaymentDueDay(e.target.value)}
              min="1"
              max="28"
              className={INPUT_CLS}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              type="number"
              placeholder="Dönem içi borç (TL) — henüz ekstreye düşmemiş"
              value={currentDebt}
              onChange={(e) => setCurrentDebt(e.target.value)}
              min="0"
              step="0.01"
              className={INPUT_CLS}
            />
            <input
              placeholder="Notlar (ops.)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={INPUT_CLS}
              maxLength={500}
            />
          </div>
          {error && <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-rose-600 text-white text-sm font-medium rounded-lg hover:bg-rose-700 disabled:opacity-50"
            >
              {submitLabel}
            </button>
            {editing && (
              <button
                type="button"
                onClick={cancelEdit}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
              >
                İptal
              </button>
            )}
          </div>
        </form>

        {/* Liste */}
        {loading && <p className="text-sm text-gray-400 text-center py-4">Yükleniyor...</p>}
        {!loading && cards.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">Henüz kart yok. Yukarıdaki formdan ekleyebilirsin.</p>
        )}
        {!loading && cards.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">{t("table.card")}</th>
                  <th className="px-4 py-3 text-center">{t("table.statementDue")}</th>
                  <th className="px-4 py-3 text-right">{t("table.periodPending")}</th>
                  <th className="px-4 py-3 text-right">{t("table.unpaidStatement")}</th>
                  <th className="px-4 py-3 text-right">{t("table.futureInstallment")}</th>
                  <th className="px-4 py-3 text-right">{t("table.totalDebt")}</th>
                  <th className="px-4 py-3 text-right">{t("table.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {cards.map((c) => {
                  const currentPeriod = parseFloat(c.current_period_debt);
                  const unpaid = parseFloat(c.unpaid_statement_total);
                  const future = parseFloat(c.future_installment_total);
                  const total = parseFloat(c.total_debt);
                  return (
                    <tr key={c.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{c.name}</p>
                        {c.bank_name && <p className="text-xs text-gray-500">{c.bank_name}</p>}
                        {c.last_4 && (
                          <p className="text-xs text-gray-400 font-mono">**** {c.last_4}</p>
                        )}
                        {c.notes && <p className="text-xs text-gray-400 mt-0.5">{c.notes}</p>}
                      </td>
                      <td className="px-4 py-3 text-center text-gray-600 text-xs">
                        Kesim: {c.statement_day}.<br />
                        Son ödeme: {c.payment_due_day}.
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {fmtTL(currentPeriod)} ₺
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span className={unpaid > 0 ? "text-rose-600" : "text-gray-400"}>
                          {fmtTL(unpaid)} ₺
                        </span>
                        {c.unpaid_statement_count >= 2 && (
                          <p className="text-[10px] text-amber-600 mt-0.5">
                            ⚠ {c.unpaid_statement_count} kayıt
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                        {fmtTL(future)} ₺
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`font-semibold tabular-nums ${total > 0 ? "text-rose-600" : "text-gray-400"}`}>
                          {fmtTL(total)} ₺
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            type="button"
                            onClick={() => router.push(`/dashboard/credit-cards/${c.id}`)}
                            className="text-xs px-2 py-1 rounded text-rose-700 border border-rose-200 hover:bg-rose-50"
                          >
                            Ekstre / Taksit
                          </button>
                          <button
                            type="button"
                            onClick={() => startEdit(c)}
                            className="text-xs px-2 py-1 rounded text-gray-600 border border-gray-200 hover:bg-gray-50"
                          >
                            Düzenle
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(c.id, c.name)}
                            className="text-gray-400 hover:text-red-500 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                            title="Sil"
                            aria-label={`${c.name} kartını sil`}
                          >
                            <span aria-hidden="true">✕</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
