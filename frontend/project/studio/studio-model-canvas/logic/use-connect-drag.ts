// Tažení vazby z portu (prototyp `connection-gesture.mjs`): stisk na portu ještě nic nedělá, pohyb o víc než 5 px
// začne tah s náhledem čáry od portu ke kurzoru, puštění na portu ohlásí cíl, puštění jinde nebo Escape tah zruší
// (a puštění mimo port to řekne). Bez pohybu je to obyčejný klik na port. Model se mění až u rodiče po puštění.
import { useCallback, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { Point, PortDirection } from "../../model/logic/model-types";
import type { PendingPort } from "./connect-gesture";

export type ConnectDrag = { start: PendingPort; from: Point; to: Point };
type Handlers = { onClick: (start: PendingPort) => void; onDrop: (start: PendingPort, target: PendingPort | null) => void };

/** Port pod kurzorem podle datových atributů tlačítka portu (`data-port-node`, `data-port-id`, `data-port-direction`). */
function portAt(x: number, y: number): PendingPort | null {
  const element = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-port-node]");
  const { portNode, portId, portDirection } = element?.dataset ?? {};
  return portNode && portId && portDirection ? { nodeId: portNode, portId, direction: portDirection as PortDirection } : null;
}

export function useConnectDrag(toFlow: (point: Point) => Point, handlers: Handlers) {
  const [drag, setDrag] = useState<ConnectDrag | null>(null);
  const latest = useRef(handlers);
  latest.current = handlers;
  const begin = useCallback((start: PendingPort, from: Point, event: ReactPointerEvent) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    const x0 = event.clientX, y0 = event.clientY;
    let moved = false;
    const finish = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("keydown", key);
      setDrag(null);
    };
    const move = (e: PointerEvent) => {
      if (!moved && Math.hypot(e.clientX - x0, e.clientY - y0) < 5) return;
      moved = true;
      setDrag({ start, from, to: toFlow({ x: e.clientX, y: e.clientY }) });
    };
    const up = (e: PointerEvent) => {
      finish();
      if (moved) latest.current.onDrop(start, portAt(e.clientX, e.clientY)); else latest.current.onClick(start);
    };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") finish(); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("keydown", key);
  }, [toFlow]);
  return { drag, begin };
}
