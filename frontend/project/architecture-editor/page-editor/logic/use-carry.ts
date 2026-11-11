// Tah z palety (box, prvek logiky) nebo štítku prvku na plátno 2 na pointer eventech, bez knihovny: stisk si zapamatuje
// položku, pohyb nad 5 px z něj udělá tah (duch u ukazatele), puštění ohlásí bod puštění. Bez pohybu zůstane obyčejný klik.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { CanvasNode, ElementKind } from "@/shared/types/logic/types";
import type { BoxKind } from "../layout-canvas/logic/layout-edit";
import type { Point } from "../layout-canvas/logic/layout-grid";

export type CarryItem = { kind: "box"; box: BoxKind } | { kind: "logic"; element: ElementKind; label: string } | { kind: "chip"; node: CanvasNode };
type Carry = { item: CarryItem; from: Point; at: Point; active: boolean };

const START_PX = 5;

export function useCarry(onDrop: (item: CarryItem, point: Point) => void) {
  const [carry, setCarry] = useState<Carry | null>(null);
  const live = useRef<Carry | null>(null);
  const drop = useRef(onDrop); drop.current = onDrop;
  const pending = carry !== null;
  useEffect(() => {
    if (!pending) return;
    const move = (event: PointerEvent) => {
      const current = live.current;
      if (!current || (!current.active && Math.hypot(event.clientX - current.from.x, event.clientY - current.from.y) < START_PX)) return;
      live.current = { ...current, at: { x: event.clientX, y: event.clientY }, active: true };
      setCarry(live.current);
    };
    const up = (event: PointerEvent) => {
      const current = live.current;
      live.current = null; setCarry(null);
      if (current?.active) drop.current(current.item, { x: event.clientX, y: event.clientY });
    };
    const cancel = () => { live.current = null; setCarry(null); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", cancel); };
  }, [pending]);
  function start(item: CarryItem, event: ReactPointerEvent) {
    if (event.button !== 0) return;
    live.current = { item, from: { x: event.clientX, y: event.clientY }, at: { x: event.clientX, y: event.clientY }, active: false };
    setCarry(live.current);
  }
  return { carrying: carry?.active ? carry : null, start };
}
