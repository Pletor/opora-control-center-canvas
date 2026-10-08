// Porty bloku: pod řádkem bloku stojí řada tlačítek jako v chat-builderu. Každé nese popisek a na pravé
// hraně karty kuličku — zdrojový úchyt React Flow s id `block:<blockId>:<portId>`, ze kterého se táhne
// vazba na jinou kartu. Dílek nic neukládá; přidání, přejmenování i odebrání bublá nahoru do rodiče.
import { useRef, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import { Handle, Position } from "@xyflow/react";
import { blockHandleId } from "@/shared/types/logic/types";
import { MAX_BLOCK_PORTS, type BlockPortDef } from "@/shared/desktop-state/logic/types";
import PortDecisionEditor from "./PortDecisionEditor";
import PortSpawnEditor from "./PortSpawnEditor";
import { useAddedPulse } from "../logic/use-added-pulse";

export type CardPortHandlers = {
  configureSpawn?: (blockId: string, portId: string, action: BlockPortDef["onMet"]) => void;
  decidePort?: (blockId: string, portId: string, status: "chosen" | "rejected" | "", reason: string) => void;
  addPort: (blockId: string) => void;
  renamePort: (blockId: string, portId: string, label: string) => void;
  removePort: (blockId: string, portId: string) => void;
};

export default function CardBlockPorts({
  blockId,
  ports,
  disabled,
  handlers,
  compact = false,
  showHandles = true,
}: {
  blockId: string;
  ports: BlockPortDef[];
  disabled: boolean;
  handlers: CardPortHandlers;
  compact?: boolean;
  showHandles?: boolean;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const added = useAddedPulse(ports.map(port => port.id));
  const field = useRef<HTMLInputElement>(null);
  const [, changed] = useState(0);
  const dirty = () => !!editing && !!field.current && field.current.value !== ports.find((port) => port.id === editing)?.label;
  useScopedSaveParticipant({ id: `canvas-block-port:${blockId}`, label: "Popisek portu na plátně",
    dirty: dirty(), isDirty: dirty, blocked: "Dokončete přejmenování portu a vyčkejte na uložení." });
  const commit = (portId: string, label: string, current: string) => {
    setEditing(null);
    const value = label.trim();
    if (value && value !== current) handlers.renamePort(blockId, portId, value);
  };
  if (!ports.length && disabled) return null;
  return (
    <>
      {ports.length > 0 && (
        <ul className="node-card__block-ports" data-testid={"card-block-ports-" + blockId}>
          {ports.map((port) => (
            <li key={port.id} className={"node-card__port-row" + (added.includes(port.id) ? " node-card__added-pulse" : "") + (port.status ? " node-card__port-row--" + port.status : "")} title={port.reason}>
              {editing === port.id ? (
                <input
                  ref={field}
                  className="nodrag node-card__block-port-input"
                  aria-label="Popisek portu"
                  defaultValue={port.label}
                  onInput={() => changed((value) => value + 1)}
                  autoFocus
                  maxLength={80}
                  onFocus={(e) => e.currentTarget.select()}
                  onKeyDown={(e) => {
                    e.stopPropagation();
                    if (e.key === "Enter") commit(port.id, e.currentTarget.value, port.label);
                    if (e.key === "Escape") setEditing(null);
                  }}
                  onBlur={(e) => commit(port.id, e.currentTarget.value, port.label)}
                />
              ) : (
                <button
                  type="button"
                  className="nodrag node-card__block-port"
                  title="Tažením z kuličky vpravo vznikne vazba na jinou kartu · dvojklik přejmenuje port"
                  data-testid={"card-port-" + port.id}
                  onClick={(e) => e.stopPropagation()}
                  onDoubleClick={(e) => { e.stopPropagation(); if (!disabled) setEditing(port.id); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !disabled) setEditing(port.id); }}
                >
                  {port.onMet ? "+ " : ""}{port.status === "chosen" ? "● " : port.status === "rejected" ? "⊗ " : ""}{port.label}
                </button>
              )}
              {!disabled && (
                <button
                  type="button"
                  className="nodrag node-card__port-remove"
                  aria-label={`Odebrat port ${port.label}`}
                  onClick={(e) => { e.stopPropagation(); handlers.removePort(blockId, port.id); }}
                  onDoubleClick={(e) => e.stopPropagation()}
                >
                  ✕
                </button>
              )}
              {!compact && handlers.decidePort && <PortDecisionEditor key={JSON.stringify(port)} port={port} blockId={blockId} disabled={disabled}
                onSave={(status, reason) => handlers.decidePort?.(blockId, port.id, status, reason)} />}
              {!compact && handlers.configureSpawn && <PortSpawnEditor key={"spawn:" + JSON.stringify(port)} port={port} blockId={blockId} disabled={disabled}
                onSave={action => handlers.configureSpawn?.(blockId, port.id, action)} />}
              {showHandles && <Handle
                type="source"
                position={Position.Right}
                id={blockHandleId(blockId, port.id)}
                className="nodrag node-card__block-port-dot"
                style={port.status === "chosen" ? { background: "var(--accent)", borderWidth: 2 } : port.status === "rejected" ? { background: "#94a3b8", borderStyle: "dashed" } : undefined}
                isConnectableStart
                isConnectableEnd={false}
                data-testid={"card-port-handle-" + port.id}
              />}
            </li>
          ))}
        </ul>
      )}
      {!disabled && ports.length < MAX_BLOCK_PORTS && (
        <button
          type="button"
          className="nodrag node-card__port-add"
          title="Nový port bloku; z jeho kuličky se táhne vazba na další kartu"
          onClick={(e) => { e.stopPropagation(); handlers.addPort(blockId); }}
          onDoubleClick={(e) => e.stopPropagation()}
        >
          + port
        </button>
      )}
    </>
  );
}
