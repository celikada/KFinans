"use client";

interface Props {
  saved: boolean;
  saving: boolean;
  exporting: boolean;
  importing: boolean;
  loading: boolean;
  onAddRow: () => void;
  onSave: () => void;
  onExport: () => void;
  onImport: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFetchPrices: () => void;
}

export function Toolbar({
  saved, saving, exporting, importing, loading,
  onAddRow, onSave, onExport, onImport, onFetchPrices,
}: Props) {
  return (
    <div className="flex gap-3 mt-4 items-center flex-wrap">
      <button onClick={onAddRow} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
        + Hisse ekle
      </button>
      <button
        onClick={onSave}
        disabled={saving}
        className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
      >
        {saved ? "✓ Kaydedildi" : saving ? "Kaydediliyor..." : "Kaydet"}
      </button>
      <button
        onClick={onExport}
        disabled={exporting}
        className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
      >
        {exporting ? "İndiriliyor..." : "Excel İndir"}
      </button>
      <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
        {importing ? "İçe aktarılıyor..." : "Excel Yükle"}
        <input type="file" accept=".xlsx,.xls" className="hidden" onChange={onImport} disabled={importing} />
      </label>
      <button
        onClick={onFetchPrices}
        disabled={loading}
        className="ml-auto px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Yükleniyor..." : "Fiyatları Getir"}
      </button>
    </div>
  );
}
