"use client";
/**
 * FE-013 (FAZ H): Native window.confirm() yerine accessible + i18n-li dialog.
 *
 * Provider tek dialog state'i tutar; useConfirm() async fonksiyon doner.
 * Kullanim:
 *   const confirm = useConfirm();
 *   if (!(await confirm("Silinsin mi?"))) return;
 *
 * Onceki: `if (!window.confirm("..."))` — stil yok, a11y zayif, i18n yok.
 *
 * A11y:
 *   - role="alertdialog" (destrüktif onay icin role=dialog'tan daha uygun)
 *   - aria-labelledby + aria-describedby
 *   - useFocusTrap: Tab dongusu + Esc kapatma + initial focus
 *   - aria-modal=true
 */
import * as React from "react";

import { useFocusTrap } from "@/app/_hooks/useFocusTrap";
import { useTranslation } from "@/app/_i18n/I18nProvider";

interface ConfirmOptions {
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface PendingConfirm {
  message: string;
  options: ConfirmOptions;
  resolve: (value: boolean) => void;
}

interface ConfirmContextValue {
  confirm: (message: string, options?: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = React.createContext<ConfirmContextValue>({
  confirm: async () => false,
});

export function ConfirmDialogProvider({ children }: { readonly children: React.ReactNode }) {
  const [pending, setPending] = React.useState<PendingConfirm | null>(null);

  const confirm = React.useCallback(
    (message: string, options: ConfirmOptions = {}) =>
      new Promise<boolean>((resolve) => {
        setPending({ message, options, resolve });
      }),
    [],
  );

  const close = React.useCallback((result: boolean) => {
    setPending((prev) => {
      if (prev) prev.resolve(result);
      return null;
    });
  }, []);

  const value = React.useMemo(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending && (
        <ConfirmDialog
          pending={pending}
          onConfirm={() => close(true)}
          onCancel={() => close(false)}
        />
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  return React.useContext(ConfirmContext).confirm;
}

function ConfirmDialog({
  pending, onConfirm, onCancel,
}: {
  readonly pending: PendingConfirm;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}) {
  const { t } = useTranslation();
  const containerRef = useFocusTrap<HTMLDivElement>(true, onCancel);
  const destructive = pending.options.destructive ?? true;

  const title = pending.options.title ?? t("common.confirm");
  const confirmLabel = pending.options.confirmLabel ?? t("common.yes");
  const cancelLabel = pending.options.cancelLabel ?? t("common.cancel");

  return (
    <div
      role="presentation"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
      onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }}
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-[60]"
    >
      <div
        ref={containerRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="bg-white rounded-2xl border border-gray-100 shadow-xl p-6 max-w-md w-full"
      >
        <h3 id="confirm-dialog-title" className="text-base font-semibold text-gray-900 mb-2">
          {title}
        </h3>
        <p id="confirm-dialog-message" className="text-sm text-gray-700 mb-5 whitespace-pre-line">
          {pending.message}
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            autoFocus
            className={
              destructive
                ? "px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
                : "px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
