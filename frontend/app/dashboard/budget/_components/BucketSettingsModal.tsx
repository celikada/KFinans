"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { useFocusTrap } from "@/app/_hooks/useFocusTrap";

interface Props {
  readonly onClose: () => void;
  readonly onSaved: () => void;
}

export function BucketSettingsModal({ onClose, onSaved }: Props) {
  const { t } = useTranslation();
  const ref = useFocusTrap<HTMLDialogElement>(true, onClose);
  const [fundamental, setFundamental] = useState(50);
  const [fun, setFun] = useState(30);
  const [future, setFuture] = useState(20);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getBudgetSettings()
      .then((s) => {
        setFundamental(Math.round(s.fundamental_ratio * 100));
        setFun(Math.round(s.fun_ratio * 100));
        setFuture(Math.round(s.future_ratio * 100));
      })
      .catch(() => undefined);
  }, []);

  async function handleSave() {
    setError("");
    if (fundamental + fun + future !== 100) {
      setError(t("content.budgetV2.settings.sumError"));
      return;
    }
    setSaving(true);
    try {
      await api.updateBudgetSettings({
        fundamental_ratio: fundamental / 100,
        fun_ratio: fun / 100,
        future_ratio: future / 100,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("content.budgetV2.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <dialog
        ref={ref}
        open
        aria-modal="true"
        aria-labelledby="bucket-settings-title"
        className="static bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm space-y-4 border-0 m-0"
      >
        <h2 id="bucket-settings-title" className="font-semibold text-gray-800">
          {t("content.budgetV2.settings.title")}
        </h2>
        <p className="text-xs text-gray-400">{t("content.budgetV2.settings.ratiosHint")}</p>
        {[
          { label: t("content.budgetV2.settings.fundamental"), value: fundamental, set: setFundamental },
          { label: t("content.budgetV2.settings.fun"), value: fun, set: setFun },
          { label: t("content.budgetV2.settings.future"), value: future, set: setFuture },
        ].map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <label className="text-sm text-gray-600">{row.label}</label>
            <input type="number" min={0} max={100} value={row.value}
              onChange={(e) => row.set(Number.parseInt(e.target.value) || 0)}
              className="w-20 px-2 py-1 border border-gray-200 rounded-lg text-sm text-right" />
          </div>
        ))}
        <p className={`text-xs text-right ${fundamental + fun + future === 100 ? "text-gray-400" : "text-red-500"}`}>
          Σ {fundamental + fun + future}%
        </p>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">
            {t("common.cancel")}
          </button>
          <button type="button" onClick={handleSave} disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {t("content.budgetV2.settings.save")}
          </button>
        </div>
      </dialog>
    </div>
  );
}
