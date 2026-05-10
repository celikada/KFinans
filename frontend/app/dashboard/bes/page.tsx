"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, BesHoldingDTO } from "@/lib/api";
import { TLValue } from "@/app/_components/TLValue";

interface Holding {
  plan_name: string;
  contract_number: string;
  paid_principal: string;
  paid_returns: string;
  govt_contribution: string;
  govt_returns: string;
}

const INPUT_CLS =
  "px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-green-500 placeholder:text-gray-400";

const EMPTY_ROW: Holding = {
  plan_name: "",
  contract_number: "",
  paid_principal: "",
  paid_returns: "",
  govt_contribution: "",
  govt_returns: "",
};

function fmtTL(val: number) {
  return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function rowTotal(h: Holding): number {
  return (
    (parseFloat(h.paid_principal) || 0) +
    (parseFloat(h.paid_returns) || 0) +
    (parseFloat(h.govt_contribution) || 0) +
    (parseFloat(h.govt_returns) || 0)
  );
}

function toDTO(holdings: Holding[]): BesHoldingDTO[] {
  return holdings
    .filter((h) => h.plan_name.trim() && rowTotal(h) > 0)
    .map((h) => ({
      plan_name: h.plan_name.trim(),
      contract_number: h.contract_number.trim() || null,
      paid_principal: parseFloat(h.paid_principal) || 0,
      paid_returns: parseFloat(h.paid_returns) || 0,
      govt_contribution: parseFloat(h.govt_contribution) || 0,
      govt_returns: parseFloat(h.govt_returns) || 0,
    }));
}

export default function BesPage() {
  const router = useRouter();
  const [holdings, setHoldings] = useState<Holding[]>([{ ...EMPTY_ROW }]);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);

  const handle401 = useCallback(() => router.replace("/login"), [router]);

  useEffect(() => {
    api.getBesHoldings()
      .then((data) => {
        if (data.length > 0) {
          setHoldings(data.map((h) => ({
            plan_name: h.plan_name,
            contract_number: h.contract_number ?? "",
            paid_principal: h.paid_principal.toString(),
            paid_returns: h.paid_returns.toString(),
            govt_contribution: h.govt_contribution.toString(),
            govt_returns: h.govt_returns.toString(),
          })));
        }
      })
      .catch((err) => {
        if (err instanceof Error && err.message.includes("401")) handle401();
      })
      .finally(() => setInitialLoad(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveHoldings() {
    const valid = toDTO(holdings);
    setSaving(true);
    setError("");
    try {
      await api.saveBesHoldings(valid);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) {
        handle401();
        return;
      }
      setError(err instanceof Error ? err.message : "Kaydetme başarısız");
    } finally {
      setSaving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setError("");
    try {
      await api.exportBesHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export başarısız");
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const imported = await api.importBesHoldings(file);
      setHoldings(imported.map((h) => ({
        plan_name: h.plan_name,
        contract_number: h.contract_number ?? "",
        paid_principal: h.paid_principal.toString(),
        paid_returns: h.paid_returns.toString(),
        govt_contribution: h.govt_contribution.toString(),
        govt_returns: h.govt_returns.toString(),
      })));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err instanceof Error && err.message.includes("401")) {
        handle401();
        return;
      }
      setError(err instanceof Error ? err.message : "Import başarısız");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  function addRow() {
    setHoldings((h) => [...h, { ...EMPTY_ROW }]);
  }

  function removeRow(i: number) {
    setHoldings((h) => h.filter((_, idx) => idx !== i));
  }

  function updateRow(i: number, field: keyof Holding, val: string) {
    setHoldings((h) => h.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));
  }

  const grandTotal = holdings.reduce((s, h) => s + rowTotal(h), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          ← Geri
        </button>
        <h1 className="text-lg font-semibold text-gray-900">BES — Bireysel Emeklilik</h1>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">BES Birikimleri</h2>
          <p className="text-xs text-gray-400 mb-4">
            BES şirketinden son ekstrenizdeki <span className="font-medium">4 ana kalemi</span> ayrı
            girin: yatırdığınız ana para + getirisi, devlet katkısı + getirisi. Toplam BES değeriniz
            otomatik hesaplanır.
          </p>

          {initialLoad ? (
            <p className="text-sm text-gray-400">Yükleniyor...</p>
          ) : (
            <div className="space-y-4">
              {holdings.map((row, i) => (
                <div key={i} className="border border-gray-100 rounded-xl p-4 space-y-3">
                  <div className="flex gap-2 items-center">
                    <input
                      placeholder="Plan adı (örn. AvivaSA Atak Hisse)"
                      value={row.plan_name}
                      onChange={(e) => updateRow(i, "plan_name", e.target.value)}
                      className={`flex-1 ${INPUT_CLS}`}
                      maxLength={200}
                    />
                    <input
                      placeholder="Sözleşme no (opsiyonel)"
                      value={row.contract_number}
                      onChange={(e) => updateRow(i, "contract_number", e.target.value)}
                      className={`w-44 font-mono text-xs ${INPUT_CLS}`}
                      maxLength={100}
                    />
                    {holdings.length > 1 && (
                      <button
                        onClick={() => removeRow(i)}
                        className="text-gray-300 hover:text-red-400 text-lg leading-none px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                        aria-label="Satırı sil"
                      >
                        <span aria-hidden="true">×</span>
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <NumField label="Yatırdığım" value={row.paid_principal}
                      onChange={(v) => updateRow(i, "paid_principal", v)} />
                    <NumField label="Yatırım getirisi" value={row.paid_returns}
                      onChange={(v) => updateRow(i, "paid_returns", v)} />
                    <NumField label="Devlet katkısı" value={row.govt_contribution}
                      onChange={(v) => updateRow(i, "govt_contribution", v)} />
                    <NumField label="Devlet katkı getirisi" value={row.govt_returns}
                      onChange={(v) => updateRow(i, "govt_returns", v)} />
                  </div>

                  <div className="text-right text-xs text-gray-500">
                    Bu plan toplamı: <span className="font-semibold text-gray-700">{fmtTL(rowTotal(row))} ₺</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3 mt-4 items-center flex-wrap">
            <button onClick={addRow} className="text-sm text-green-600 hover:text-green-700 font-medium">
              + Plan ekle
            </button>
            <button
              onClick={saveHoldings}
              disabled={saving}
              className="text-sm text-white bg-green-600 hover:bg-green-700 font-medium px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {saved ? "✓ Kaydedildi" : saving ? "Kaydediliyor..." : "Kaydet"}
            </button>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {exporting ? "İndiriliyor..." : "Excel İndir"}
            </button>
            <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
              {importing ? "İçe aktarılıyor..." : "Excel Yükle"}
              <input
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleImport}
                disabled={importing}
              />
            </label>
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          {grandTotal > 0 && (
            <div className="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between">
              <span className="text-sm text-gray-500">Toplam BES Değeri</span>
              <TLValue tl={grandTotal} className="text-lg font-bold text-gray-900" usdClassName="block text-xs text-gray-400 font-normal mt-0.5 tabular-nums text-right" />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label} (₺)</label>
      <input
        type="number"
        min="0"
        step="0.01"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0,00"
        className={`w-full text-right ${INPUT_CLS}`}
      />
    </div>
  );
}
