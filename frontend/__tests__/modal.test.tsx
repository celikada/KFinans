import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { Modal } from "@/app/_components/Modal";

// jsdom <dialog>.showModal/close desteklemez; native Modal için mock'la.
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.open = true;
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.open = false;
  });
});

function renderModal(open: boolean, onClose: () => void) {
  return render(
    <Modal open={open} onClose={onClose} labelledById="t" describedById="d">
      <div>
        <h3 id="t">Başlık</h3>
        <p id="d">Açıklama</p>
        <button type="button">İçerik butonu</button>
      </div>
    </Modal>,
  );
}

describe("Modal", () => {
  it("open=false iken hiçbir şey render etmez", () => {
    renderModal(false, vi.fn());
    expect(screen.queryByText("Başlık")).not.toBeInTheDocument();
  });

  it("open=true iken içeriği render eder + showModal çağrılır", () => {
    renderModal(true, vi.fn());
    expect(screen.getByText("Başlık")).toBeInTheDocument();
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled();
  });

  it("native dialog kullanır (implicit role=dialog, elle role yok)", () => {
    const { container } = renderModal(true, vi.fn());
    const dialog = container.querySelector("dialog");
    expect(dialog).not.toBeNull();
    // S6819: dialog'a elle role="dialog" verilmemeli.
    expect(dialog?.getAttribute("role")).toBeNull();
    expect(dialog?.getAttribute("aria-labelledby")).toBe("t");
    expect(dialog?.getAttribute("aria-describedby")).toBe("d");
  });

  it("ESC (cancel event) → onClose çağrılır", () => {
    const onClose = vi.fn();
    const { container } = renderModal(true, onClose);
    const dialog = container.querySelector("dialog")!;
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("backdrop (dialog) tıklama → onClose ÇAĞRILMAZ (bilinçli; kazara kapatma önlenir)", () => {
    const onClose = vi.fn();
    const { container } = renderModal(true, onClose);
    const dialog = container.querySelector("dialog")!;
    fireEvent.click(dialog);
    // Backdrop-click ile kapatma yok (alertdialog güvenliği + a11y); ESC + buton ile kapatılır.
    expect(onClose).not.toHaveBeenCalled();
  });

  it("içerik tıklaması → onClose çağrılmaz", () => {
    const onClose = vi.fn();
    renderModal(true, onClose);
    fireEvent.click(screen.getByText("İçerik butonu"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("role='alertdialog' override edilebilir", () => {
    const { container } = render(
      <Modal open onClose={vi.fn()} role="alertdialog">
        <div>x</div>
      </Modal>,
    );
    expect(container.querySelector("dialog")?.getAttribute("role")).toBe("alertdialog");
  });
});
