import { useEffect, useRef, type RefObject } from "react";

const CONTROLS = 'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]';

/**
 * Fokus detailu: po otevření skočí do draweru, Tab v něm koluje, Escape zavře a po zavření se fokus
 * vrátí tam, odkud uživatel detail otevřel (karta, odznak, řádek Velínu). Vnořený dialog (`[role=dialog]`
 * uvnitř) si Escape vyřeší sám, proto se bere jen událost, kterou nikdo nezastavil.
 */
export function useDrawerFocus(dialog: RefObject<HTMLElement | null>, onClose: () => void) {
  const latest = useRef(onClose);
  latest.current = onClose;
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current;
    if (!element) return;
    const controls = () => [...element.querySelectorAll<HTMLElement>(CONTROLS)].filter(item => item.getClientRects().length);
    const keyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        const nested = event.target instanceof Element ? event.target.closest('[role="dialog"]') : null;
        if (nested && nested !== element) return;
        event.preventDefault(); event.stopPropagation(); latest.current(); return;
      }
      if (event.key !== "Tab" || !element.contains(document.activeElement)) return;
      const items = controls(), first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keyDown);
    element.focus({ preventScroll: true });
    return () => {
      document.removeEventListener("keydown", keyDown);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [dialog]);
}
