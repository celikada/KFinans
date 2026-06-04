"use client";
/**
 * Erişilebilir Modal primitifi — native <dialog showModal()> tabanlı.
 *
 * Neden native <dialog>:
 *   - showModal() focus'u modal'a alır + arka planı `inert` yapar (top layer);
 *     bu yüzden manuel useFocusTrap'e GEREK KALMAZ (native focus trap).
 *   - <dialog> implicit `role=dialog` + `aria-modal` sağlar → SonarQube S6819
 *     (a11y-role) uyarıları ortadan kalkar; elle role="presentation"/role="dialog"
 *     yazmaya gerek yok.
 *   - ESC native `cancel` event'i tetikler → kontrollü kapatma için preventDefault.
 *
 * Kullanım:
 *   <Modal open={open} onClose={() => setOpen(false)}
 *          labelledById="x-title" describedById="x-desc">
 *     <h3 id="x-title">...</h3>
 *     <p id="x-desc">...</p>
 *     ...
 *   </Modal>
 *
 * jsdom showModal/close desteklemediği için defensive guard kullanılır; testlerde
 * HTMLDialogElement.prototype.showModal/close mock'lanmalıdır.
 */
import * as React from "react";

export function Modal({
  open,
  onClose,
  labelledById,
  describedById,
  className,
  role,
  children,
}: {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly labelledById?: string;
  readonly describedById?: string;
  readonly className?: string;
  /**
   * Native <dialog> zaten implicit role=dialog verir; bu prop'u SADECE
   * `alertdialog` gibi geçerli bir override için kullan. `role="dialog"`
   * verme — gereksizdir (SonarQube S6819).
   */
  readonly role?: "alertdialog";
  readonly children: React.ReactNode;
}) {
  const dialogRef = React.useRef<HTMLDialogElement | null>(null);

  React.useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      // jsdom showModal'ı desteklemez → guard.
      if (typeof dialog.showModal === "function" && !dialog.open) {
        dialog.showModal();
      }
    } else if (typeof dialog.close === "function" && dialog.open) {
      dialog.close();
    }
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      role={role}
      aria-labelledby={labelledById}
      aria-describedby={describedById}
      onCancel={(e) => {
        // ESC → native cancel; kontrollü kapatma için varsayılanı engelle.
        e.preventDefault();
        onClose();
      }}
      className={
        "m-auto bg-transparent p-0 backdrop:bg-black/40" +
        (className ? ` ${className}` : "")
      }
    >
      {/* Kapatma: ESC (native cancel) + her modal'ın kendi kapatma/iptal butonu.
          Backdrop tıklamasıyla kapatma bilinçli olarak yok — özellikle alertdialog
          (onay) için kazara kapanmayı önler; <dialog>'a click handler eklemek de
          erişilebilirlik açısından önerilmez (non-interactive element). */}
      <div className="p-4">{children}</div>
    </dialog>
  );
}
