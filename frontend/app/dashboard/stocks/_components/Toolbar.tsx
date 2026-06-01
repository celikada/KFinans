"use client";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly saved: boolean;
  readonly saving: boolean;
  readonly exporting: boolean;
  readonly importing: boolean;
  readonly loading: boolean;
  readonly onAddRow: () => void;
  readonly onSave: () => void;
  readonly onExport: () => void;
  readonly onImport: (e: React.ChangeEvent<HTMLInputElement>) => void;
  readonly onFetchPrices: () => void;
}

export function Toolbar({
  saved, saving, exporting, importing, loading,
  onAddRow, onSave, onExport, onImport, onFetchPrices,
}: Props) {
  const { t } = useTranslation();
  let saveLabel = t("content.stocks.save");
  if (saved) saveLabel = t("content.stocks.saved");
  else if (saving) saveLabel = t("content.stocks.saving");
  return (
    <div className="flex gap-3 mt-4 items-center flex-wrap">
      <button onClick={onAddRow} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
        {t("content.stocks.addStock")}
      </button>
      <button
        onClick={onSave}
        disabled={saving}
        className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
      >
        {saveLabel}
      </button>
      <button
        onClick={onExport}
        disabled={exporting}
        className="text-sm text-gray-500 hover:text-gray-700 font-medium border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
      >
        {exporting ? t("content.stocks.downloading") : t("content.stocks.excelDownload")}
      </button>
      <label className={`text-sm font-medium border px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${importing ? "text-gray-400 border-gray-100" : "text-gray-500 hover:text-gray-700 border-gray-200"}`}>
        {importing ? t("content.stocks.importing") : t("content.stocks.excelUpload")}
        <input type="file" accept=".xlsx,.xls" className="hidden" onChange={onImport} disabled={importing} />
      </label>
      <button
        onClick={onFetchPrices}
        disabled={loading}
        className="ml-auto px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
      >
        {loading ? t("content.stocks.fetching") : t("content.stocks.fetchPrices")}
      </button>
    </div>
  );
}
