"use client";

/**
 * A11Y-001 (FAZ H): Modal/dialog focus trap hook.
 *
 * Modal acilinca:
 *   - onceki aktif element saklanir (modal kapanisinda geri verilir).
 *   - Modal icindeki ilk focusable element'e focus atilir.
 *   - Tab + Shift+Tab modal disina cikamaz (cyclic).
 *   - Esc kapatma external `onClose` callback'i ile.
 *
 * WCAG 2.1 SC 2.4.3 Focus Order + 2.1.2 No Keyboard Trap (modal disinda).
 */
import { useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function useFocusTrap(active: boolean, onClose?: () => void) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!active) return;

    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    const focusables = () =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
        .filter((el) => !el.hasAttribute("data-focus-skip"));

    // Initial focus: ilk focusable, yoksa container kendisi.
    const initial = focusables()[0];
    if (initial) {
      initial.focus();
    } else {
      container.setAttribute("tabindex", "-1");
      container.focus();
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
        return;
      }
      if (e.key !== "Tab") return;

      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;

      if (e.shiftKey && activeEl === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && activeEl === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [active, onClose]);

  return containerRef;
}
