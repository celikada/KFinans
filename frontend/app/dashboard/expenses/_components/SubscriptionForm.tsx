"use client";
import { useEffect, useState } from "react";
import {
  api,
  CurrencyType,
  CURRENCIES,
  ProviderDTO,
  SubscriptionDTO,
  SubscriptionInput,
} from "@/lib/api";
import { INPUT_CLS } from "@/lib/format";
import { getDefaultCurrency } from "@/lib/defaultCurrency";
import { useTranslation } from "@/app/_i18n/I18nProvider";
import { categoryMeta } from "./subscriptionMeta";

interface Props {
  /** Create modunda yeni kayıt; edit modunda güncellenmiş kayıt döner. */
  readonly onSaved: (sub: SubscriptionDTO) => void;
  /** Doluysa edit modunda; boşsa create. */
  readonly existing?: SubscriptionDTO | null;
  readonly onCancel?: () => void;
}

export function SubscriptionForm({ onSaved, existing, onCancel }: Props) {
  const { t } = useTranslation();
  const isEdit = !!existing;
  // Create modunda formu katlanabilir tut; edit modunda her zaman açık.
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [providers, setProviders] = useState<ProviderDTO[]>([]);

  const [providerCode, setProviderCode] = useState(existing?.provider_code ?? "");
  const [subscriberNo, setSubscriberNo] = useState(existing?.subscriber_no ?? "");
  const [budgetAmount, setBudgetAmount] = useState(existing?.budget_amount ?? "");
  const [currency, setCurrency] = useState<CurrencyType>(existing?.currency ?? getDefaultCurrency());
  const [label, setLabel] = useState(existing?.label ?? "");
  const [billingDay, setBillingDay] = useState(existing?.billing_day?.toString() ?? "");
  const [dueDay, setDueDay] = useState(existing?.due_day?.toString() ?? "");
  const [active, setActive] = useState(existing?.active ?? true);
  const [notes, setNotes] = useState(existing?.notes ?? "");

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => {});
  }, []);

  // existing değişirse formu yenile (edit moduna geçiş / başka kayda geçiş).
  useEffect(() => {
    if (existing) {
      setProviderCode(existing.provider_code);
      setSubscriberNo(existing.subscriber_no);
      setBudgetAmount(existing.budget_amount);
      setCurrency(existing.currency ?? getDefaultCurrency());
      setLabel(existing.label ?? "");
      setBillingDay(existing.billing_day?.toString() ?? "");
      setDueDay(existing.due_day?.toString() ?? "");
      setActive(existing.active);
      setNotes(existing.notes ?? "");
      setOpen(true);
    }
  }, [existing]);

  function resetForm() {
    setProviderCode(""); setSubscriberNo(""); setBudgetAmount(""); setLabel("");
    setBillingDay(""); setDueDay(""); setActive(true); setNotes("");
    setCurrency(getDefaultCurrency());
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload: SubscriptionInput = {
        provider_code: providerCode,
        subscriber_no: subscriberNo.trim(),
        budget_amount: Number.parseFloat(budgetAmount),
        currency,
        label: label.trim() || null,
        billing_day: billingDay ? Number.parseInt(billingDay) : null,
        due_day: dueDay ? Number.parseInt(dueDay) : null,
        active,
        notes: notes.trim() || null,
      };
      const result = isEdit && existing
        ? await api.updateSubscription(existing.id, payload)
        : await api.createSubscription(payload);
      onSaved(result);
      if (!isEdit) {
        resetForm();
        setOpen(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  function renderForm() {
    let submitLabel: string;
    if (saving) submitLabel = t("form.saving");
    else if (isEdit) submitLabel = t("form.update");
    else submitLabel = t("form.save");

    return (
      <form onSubmit={handleSubmit} className={isEdit ? "space-y-4" : "mt-4 space-y-4"}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2">
            <label htmlFor="sub_provider" className="block text-xs text-gray-500 mb-1">
              {t("content.subscriptions.providerLabel")}
            </label>
            <select
              id="sub_provider"
              className={INPUT_CLS}
              value={providerCode}
              onChange={(e) => setProviderCode(e.target.value)}
              required
            >
              <option value="">{t("content.subscriptions.providerPlaceholder")}</option>
              {providers.map((p) => (
                <option key={p.code} value={p.code}>
                  {categoryMeta(p.category).icon} {p.name} · {t(`content.subscriptions.category.${p.category}`)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="sub_no" className="block text-xs text-gray-500 mb-1">
              {t("content.subscriptions.subscriberNoLabel")}
            </label>
            <input
              id="sub_no"
              className={INPUT_CLS}
              placeholder={t("content.subscriptions.subscriberNoPlaceholder")}
              value={subscriberNo}
              onChange={(e) => setSubscriberNo(e.target.value)}
              required
              maxLength={64}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">{t("content.subscriptions.budgetLabel")}</label>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.01"
                min="0.01"
                className={`flex-1 min-w-0 ${INPUT_CLS}`}
                placeholder={t("form.amountPlaceholder")}
                value={budgetAmount}
                onChange={(e) => setBudgetAmount(e.target.value)}
                required
              />
              <select
                aria-label={t("form.currencyLabel")}
                className={`w-20 ${INPUT_CLS}`}
                value={currency}
                onChange={(e) => setCurrency(e.target.value as CurrencyType)}
              >
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="sub_label" className="block text-xs text-gray-500 mb-1">
              {t("content.subscriptions.labelLabel")}
            </label>
            <input
              id="sub_label"
              className={INPUT_CLS}
              placeholder={t("form.optional")}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              maxLength={100}
            />
          </div>

          <div>
            <label htmlFor="sub_billing_day" className="block text-xs text-gray-500 mb-1">
              {t("content.subscriptions.billingDayLabel")}
            </label>
            <input
              id="sub_billing_day"
              type="number"
              min="1"
              max="28"
              className={INPUT_CLS}
              placeholder={t("form.optional")}
              value={billingDay}
              onChange={(e) => setBillingDay(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="sub_due_day" className="block text-xs text-gray-500 mb-1">
              {t("content.subscriptions.dueDayLabel")}
            </label>
            <input
              id="sub_due_day"
              type="number"
              min="1"
              max="28"
              className={INPUT_CLS}
              placeholder={t("form.optional")}
              value={dueDay}
              onChange={(e) => setDueDay(e.target.value)}
            />
          </div>

          <div className="sm:col-span-2">
            <label htmlFor="sub_notes" className="block text-xs text-gray-500 mb-1">{t("form.notes")}</label>
            <input
              id="sub_notes"
              className={INPUT_CLS}
              placeholder={t("form.optional")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
            />
          </div>

          <div className="sm:col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              id="sub_active"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="sub_active" className="text-xs text-gray-500">
              {t("content.subscriptions.activeLabel")}
            </label>
          </div>
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={saving}
            className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {submitLabel}
          </button>
          {isEdit && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-sm px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50"
            >
              {t("common.cancel")}
            </button>
          )}
        </div>
      </form>
    );
  }

  // Edit modunda toggle yok — form doğrudan açık.
  if (isEdit) {
    return (
      <div className="bg-white rounded-2xl border border-indigo-200 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">{t("content.subscriptions.editTitle")}</h3>
        {renderForm()}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
      >
        {open ? t("content.subscriptions.toggleClose") : t("content.subscriptions.toggleOpen")}
      </button>

      {open && renderForm()}
    </div>
  );
}
