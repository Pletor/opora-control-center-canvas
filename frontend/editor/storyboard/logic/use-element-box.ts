// Zobrazená velikost a poloha prvku (obsah bez rámečku, vůči offsetParent): webová scéna se podle ní zmenší na přesně tu
// plochu, kterou ukazuje plátno nebo miniatura. Měří ResizeObserver nad prvkem i rodičem (rodič mění vystředění).
import { useEffect, useState, type RefObject } from "react";

export type ElementBox = { left: number; top: number; width: number; height: number };

const same = (a: ElementBox | null, b: ElementBox) => !!a && a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height;

export function useElementBox(ref: RefObject<HTMLElement | null>, enabled: boolean): ElementBox | null {
  const [box, setBox] = useState<ElementBox | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const next = { left: el.offsetLeft + el.clientLeft, top: el.offsetTop + el.clientTop, width: el.clientWidth, height: el.clientHeight };
      setBox((old) => (same(old, next) ? old : next));
    };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    if (el.parentElement) observer.observe(el.parentElement);
    measure();
    return () => observer.disconnect();
  }, [ref, enabled]);
  return enabled ? box : null;
}
