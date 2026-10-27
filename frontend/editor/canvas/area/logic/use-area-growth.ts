// Živý náhled rostoucí oblasti při tahu karty (docs/architektura-pro-agenty.md §3.5, §8). Drží jeden tah
// (`GrowthSession` z `area-growth.ts`) a při každém pohybu přepíše jen uzel domovské oblasti — polohu a
// `style` rozměr. Ostatní uzly zůstávají stejné objekty, takže karty se nepřestaví a vstupy v nich neztratí
// fokus. Nic se neukládá; ukládá rodič až po puštění (`dropCard`).
import { useMemo, useRef, type Dispatch, type SetStateAction } from "react";
import type { Node } from "@xyflow/react";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { Body } from "@/editor/canvas/board/logic/solid-bodies";
import { startGrowth, stepGrowth, type GrowthSession, type Rect } from "@/editor/canvas/area/logic/area-growth";

type Drag = { session: GrowthSession; card: CanvasNode; body: Body; nodes: CanvasNode[] };

export type AreaGrowth = {
  /** Začátek tahu karty: `nodes` jsou uložené uzly vrstvy, `bodies` obdélníky karet vrstvy na uložených místech. */
  begin: (card: CanvasNode, nodes: CanvasNode[], bodies: Body[]) => void;
  /** Karta je teď na (x, y): domovská oblast v náhledu vyroste, projde-li růst. */
  preview: (x: number, y: number) => void;
  /** Konec tahu: vrátí tah (nebo `null`, když karta neměla domovskou oblast) a zapomene ho. */
  finish: () => GrowthSession | null;
  /** Ukáže rámeček oblasti v daném obdélníku (náhled zpět na `start`, nebo na uložený růst). */
  show: (areaId: string, rect: Rect) => void;
};

export function useAreaGrowth<N extends Node>(setNodes: Dispatch<SetStateAction<N[]>>): AreaGrowth {
  const drag = useRef<Drag | null>(null);
  return useMemo(() => {
    const show = (areaId: string, rect: Rect) => setNodes((nodes) => nodes.map((n) => n.id !== areaId ? n
      : { ...n, position: { x: rect.x, y: rect.y }, style: { ...n.style, width: rect.w, height: rect.h } }));
    return {
      show,
      begin(card, nodes, bodies) {
        const session = startGrowth(card, nodes, bodies);
        const body = bodies.find((b) => b.id === card.id);
        drag.current = session && body ? { session, card, body, nodes } : null;
      },
      preview(x, y) {
        const current = drag.current;
        if (!current) return;
        const { session, card, body } = current;
        const moved = { ...card, x, y };
        const grown = stepGrowth(session, moved, { ...body, x: body.x + x - card.x, y: body.y + y - card.y }, current.nodes);
        if (!grown) return;
        const before = session.current;
        if (grown.x === before.x && grown.y === before.y && grown.w === before.w && grown.h === before.h) return;
        session.current = grown;
        show(session.homeId, grown);
      },
      finish() {
        const session = drag.current?.session ?? null;
        drag.current = null;
        return session;
      },
    };
  }, [setNodes]);
}
