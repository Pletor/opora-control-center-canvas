import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { PAD, widthText, xOf, zoomAt, zoomLimits } from "./linie-zoom";

/**
 * Ovládání jediného posuvného prvku Linie: kolečko nad plátnem = čas blíž/dál kolem kurzoru, Shift+kolečko = posun,
 * tažení prázdného místa = ruka všemi směry. Měřítko `k` je stav (null = vše se vejde); nová data ani překreslení ho
 * nemění. Kolečko nad sloupcem názvů nechává prohlížeči (svislý posun řádků).
 */
export function useLinieZoom(scrollRef: RefObject<HTMLDivElement | null>, names: number, plotWidth: number, t0: number, t1: number, active: boolean) {
  const [chosen, setChosen] = useState<number | null>(null);
  const limits = zoomLimits(t1 - t0, plotWidth);
  const k = Math.min(limits.max, Math.max(limits.min, chosen ?? limits.min));
  const pending = useRef<number | null>(null);
  const live = useRef({ k, limits, names, t0 });
  live.current = { k, limits, names, t0 };

  useLayoutEffect(() => {
    if (pending.current === null || !scrollRef.current) return;
    scrollRef.current.scrollLeft = pending.current;
    pending.current = null;
  });

  const zoom = (cursor: number, factor: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const now = live.current;
    const next = zoomAt({ t0: now.t0, k: now.k }, el.scrollLeft, cursor, factor, now.limits);
    pending.current = next.scrollLeft;
    setChosen(next.k);
  };
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      const cursor = event.clientX - el.getBoundingClientRect().left - live.current.names;
      if (cursor < 0) return; // nad názvy: obyčejný svislý posun
      event.preventDefault();
      if (event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) el.scrollLeft += event.deltaX || event.deltaY;
      else zoomRef.current(cursor, Math.exp(-event.deltaY * 0.0015));
    };
    // Ruka: jen z prázdného místa plátna (ne z kuličky ani ovládacího prvku), aby tažení nespolklo klik.
    let drag: { x: number; y: number; left: number; top: number; id: number } | null = null;
    const onDown = (event: PointerEvent) => {
      const target = event.target as Element;
      if (event.button !== 0 || !target.closest("[data-pan]") || target.closest("[role=button], button, input")) return;
      drag = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop, id: event.pointerId };
      el.setPointerCapture?.(event.pointerId);
    };
    const onMove = (event: PointerEvent) => {
      if (!drag) return;
      el.scrollLeft = drag.left - (event.clientX - drag.x);
      el.scrollTop = drag.top - (event.clientY - drag.y);
    };
    const onUp = () => { if (drag) el.releasePointerCapture?.(drag.id); drag = null; };
    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
    };
  }, [scrollRef, active]); // Git graf posuvný prvek odpojí; po návratu do editoru se posluchače navážou znovu

  return {
    k,
    text: widthText(k, Math.max(1, plotWidth)),
    zoomIn: () => zoom(plotWidth / 2, 1.5),
    zoomOut: () => zoom(plotWidth / 2, 1 / 1.5),
    /** Vše: celý rozsah na šířku, svislá poloha zůstane. */
    all: () => { pending.current = 0; scrollRef.current?.scrollTo({ left: 0 }); setChosen(null); },
    /** Teď: měřítko zůstane, „teď“ se posune k pravému okraji plátna. */
    now: (now: number) => { if (scrollRef.current) scrollRef.current.scrollLeft = xOf({ t0, k }, now) - plotWidth + PAD; },
    /** Výchozí: celý rozsah a návrat na začátek vodorovně i svisle. */
    reset: () => { pending.current = 0; scrollRef.current?.scrollTo({ left: 0, top: 0 }); setChosen(null); },
  };
}
