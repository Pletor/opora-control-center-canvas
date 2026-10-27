// Porty karty: pět kuliček na pravé hraně. Tah = zdroj vazby (React Flow Handle), klik bez tahu = otevřít/skrýt blok.
// Který port je otevřený rozhoduje rodič; sem přichází jen `open` a událost `onToggle` bublá nahoru.
import { useRef, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { Position } from "@xyflow/react";
import PortHandle from "@/shared/flow-ports/components/PortHandle";
import { CARD_PORTS, LINKABLE_PORTS, PORT_LABEL, type CardPort } from "@/editor/canvas/node-card/logic/card-model";

export type BlockPort = Exclude<CardPort, "next">;

export default function CardPorts({ id, open, onToggle }: { id: string; open: BlockPort[]; onToggle: (port: BlockPort) => void }) {
  const pressedAt = useRef<{ x: number; y: number } | null>(null);
  const click = (port: BlockPort) => ({
    onPointerDown: (e: ReactPointerEvent) => { pressedAt.current = { x: e.clientX, y: e.clientY }; },
    onPointerUp: (e: ReactPointerEvent) => {
      const start = pressedAt.current;
      pressedAt.current = null;
      if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 4) onToggle(port);
    },
  });
  return (
    <>
      <PortHandle kind="next" type="target" position={Position.Left} hint="sem se zapojí vazba z jiné karty" />
      {CARD_PORTS.map((port) => (
        <PortHandle
          key={port}
          kind={port}
          type="source"
          position={Position.Right}
          id={port}
          className={`nodrag node-card__port node-card__port--${port}` + (port !== "next" && open.includes(port) ? " node-card__port--open" : "")}
          isConnectableStart={LINKABLE_PORTS.includes(port)}
          hint={
            port === "next"
              ? "tahem propojit s další kartou"
              : port === "material"
                ? "klik otevře blok s obrázky a odkazy pro tento uzel"
                : port === "pipeline"
                  ? "klik otevře etapy práce, testů, review, oprav a tří kritiků"
                  : "klik otevře blok, tah propojí s kartou"
          }
          data-testid={`port-${port}-${id}`}
          {...(port === "next" ? {} : click(port))}
          {...(port === "next" ? {} : { onKeyDown: (e: ReactKeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); onToggle(port); } } })}
        />
      ))}
      <div className="node-card__port-labels" aria-hidden="true">
        {CARD_PORTS.map((port) => (
          <span key={port} className={`node-card__port-label node-card__port-label--${port}`}>{PORT_LABEL[port]}</span>
        ))}
      </div>
    </>
  );
}
