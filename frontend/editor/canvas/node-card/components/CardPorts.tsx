// Porty karty: pět kuliček na pravé hraně. Tah = zdroj vazby (React Flow Handle), klik bez tahu = otevřít/skrýt blok.
// Který port je otevřený rozhoduje rodič; sem přichází jen `open` a událost `onToggle` bublá nahoru.
import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import { Handle, Position } from "@xyflow/react";
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
      <Handle type="target" position={Position.Left} />
      {CARD_PORTS.map((port) => (
        <Handle
          key={port}
          type="source"
          position={Position.Right}
          id={port}
          className={`nodrag node-card__port node-card__port--${port}` + (port !== "next" && open.includes(port) ? " node-card__port--open" : "")}
          isConnectableStart={LINKABLE_PORTS.includes(port)}
          title={
            port === "next"
              ? "Další krok: tahem propojit s další kartou"
              : port === "material"
                ? "Podklady: klik otevře blok s obrázky a odkazy pro tento uzel"
                : port === "pipeline"
                  ? "Pipeline: klik otevře etapy práce, testů, review, oprav a tří kritiků"
                  : `${PORT_LABEL[port]}: klik otevře blok, tah propojí s kartou`
          }
          data-testid={`port-${port}-${id}`}
          {...(port === "next" ? {} : click(port))}
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
