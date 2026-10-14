// Porty bloku: pod řádkem bloku stojí řada tlačítek jako v chat-builderu. Každé nese popisek a na pravé
// hraně karty kuličku — zdrojový úchyt React Flow s id `block:<blockId>:<portId>`, ze kterého se táhne
// vazba na jinou kartu. Dílek nic neukládá; přidání, přejmenování i odebrání bublá nahoru do rodiče.
// Úroveň detailu (oprava 4 v docs/navrhy/2026-10-14-vykon-platna.md): editory rozhodnutí a navazující karty,
// odebrání a „+ port“ má jen vybraná karta (`full`); nevybraná (`row`) kreslí popisek a kuličku, oddálená
// (`far`) jen popisek a kuličku bez tlačítka. Kulička (`Handle`) zůstává ve všech úrovních, jinak by se
// vazby z portu neměly kam připojit. Editor, který je po zrušení výběru rozepsaný (`data-dirty`) nebo má
// fokus, zůstane namontovaný a vidět, dokud ho člověk neuloží nebo neopustí.
import { useRef, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import { Handle, Position } from "@xyflow/react";
import { blockHandleId } from "@/shared/types/logic/types";
import { MAX_BLOCK_PORTS, type BlockPortDef } from "@/shared/desktop-state/logic/types";
import PortDecisionEditor from "./PortDecisionEditor";
import PortSpawnEditor from "./PortSpawnEditor";
import { useAddedPulse } from "../logic/use-added-pulse";
import { portEditorsShown } from "../logic/card-lod";

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
  detail = "full",
}: {
  blockId: string;
  ports: BlockPortDef[];
  disabled: boolean;
  handlers: CardPortHandlers;
  detail?: "full" | "row" | "far";
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
  const tools = detail === "full" && !disabled;
  // Porty, jejichž editor je rozepsaný nebo zaměřený: čte se z DOM jen při renderu (změna výběru, zoomu).
  const list = useRef<HTMLUListElement>(null);
  const held = new Set<string>();
  if (detail !== "full" && list.current && typeof document !== "undefined") {
    for (const row of Array.from(list.current.querySelectorAll<HTMLElement>("li[data-port-id]")))
      if (row.querySelector("[data-dirty]") || row.contains(document.activeElement)) held.add(row.dataset.portId ?? "");
  }
  if (!ports.length && !tools) return null;
  return (
    <>
      {ports.length > 0 && (
        <ul ref={list} className="node-card__block-ports" data-testid={"card-block-ports-" + blockId}>
          {ports.map((port) => (
            <li key={port.id} className={"node-card__port-row" + (added.includes(port.id) ? " node-card__added-pulse" : "") + (port.status ? " node-card__port-row--" + port.status : "") + (detail !== "full" && held.has(port.id) ? " node-card__port-row--held" : "")} title={port.reason} data-port-id={port.id}>
              {detail === "far" ? (
                <span className="node-card__block-port node-card__block-port--far">{port.status === "chosen" ? "● " : port.status === "rejected" ? "⊗ " : ""}{port.label}</span>
              ) : editing === port.id ? (
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
              {tools && (
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
              {portEditorsShown(detail, held.has(port.id)) && handlers.decidePort && <PortDecisionEditor key={"decision:" + port.id} port={port} blockId={blockId} disabled={disabled}
                onSave={(status, reason) => handlers.decidePort?.(blockId, port.id, status, reason)} />}
              {portEditorsShown(detail, held.has(port.id)) && handlers.configureSpawn && <PortSpawnEditor key={"spawn:" + port.id} port={port} blockId={blockId} disabled={disabled}
                onSave={action => handlers.configureSpawn?.(blockId, port.id, action)} />}
              <Handle
                type="source"
                position={Position.Right}
                id={blockHandleId(blockId, port.id)}
                className="nodrag node-card__block-port-dot"
                style={port.status === "chosen" ? { background: "var(--accent)", borderWidth: 2 } : port.status === "rejected" ? { background: "#94a3b8", borderStyle: "dashed" } : undefined}
                isConnectableStart
                isConnectableEnd={false}
                data-testid={"card-port-handle-" + port.id}
              />
            </li>
          ))}
        </ul>
      )}
      {tools && ports.length < MAX_BLOCK_PORTS && (
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
