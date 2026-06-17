"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface Props {
  readonly year: number;
  readonly month: number;
}

export function MonthNotePanel({ year, month }: Props) {
  const { t } = useTranslation();
  const [analysis, setAnalysis] = useState("");
  const [actionPlan, setActionPlan] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(false);

  useEffect(() => {
    let active = true;
    setSavedAt(false);
    api
      .getMonthNote(year, month)
      .then((n) => {
        if (!active) return;
        setAnalysis(n.analysis ?? "");
        setActionPlan(n.action_plan ?? "");
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [year, month]);

  async function handleSave() {
    setSaving(true);
    setSavedAt(false);
    try {
      await api.upsertMonthNote(year, month, analysis.trim() || null, actionPlan.trim() || null);
      setSavedAt(true);
    } catch {
      // sessiz — kullanıcı tekrar deneyebilir
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-3">
      <h3 className="font-semibold text-gray-700">{t("content.budgetV2.notes.title")}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1" htmlFor="note-analysis">
            {t("content.budgetV2.notes.analysis")}
          </label>
          <textarea id="note-analysis" rows={4} value={analysis} onChange={(e) => setAnalysis(e.target.value)}
            placeholder={t("content.budgetV2.notes.placeholder")}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-y" />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1" htmlFor="note-action">
            {t("content.budgetV2.notes.actionPlan")}
          </label>
          <textarea id="note-action" rows={4} value={actionPlan} onChange={(e) => setActionPlan(e.target.value)}
            placeholder={t("content.budgetV2.notes.actionPlaceholder")}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-y" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button type="button" onClick={handleSave} disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {t("content.budgetV2.notes.save")}
        </button>
        {savedAt && <span className="text-xs text-emerald-600">{t("content.budgetV2.notes.saved")}</span>}
      </div>
    </div>
  );
}
