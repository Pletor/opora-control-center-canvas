// Porty bloku: pod řádkem bloku stojí řada tlačítek jako v chat-builderu. Každé nese popisek a na pravé
// hraně karty kuličku — zdrojový úchyt React Flow s id `block:<blockId>:<portId>`, ze kterého se táhne
// vazba na jinou kartu. Dílek nic neukládá; přidání, přejmenování i odebrání bublá nahoru do rodiče.
import { useState } from "react";
import { Handle, Position } from "@xyflow/react";
import { blockHandleId } from "@/shared/types/logic/types";
import { MAX_BLOCK_PORTS, type BlockPortDef } from "@/shared/desktop-state/logic/types";

export type CardPortHandlers = {
  addPort: (blockId: string) => void;
  renamePort: (blockId: string, portId: string, label: string) => void;
  removePort: (blockId: string, portId: string) => void;
};

export default function CardBlockPorts({
  blockId,
  ports,
  disabled,
  handlers,
}: {
  blockId: string;
  ports: BlockPortDef[];
  disabled: boolean;
  handlers: CardPortHandlers;
}) {
  const [editing, setEditing] = useState<string | null>(null);
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
            <li key={port.id} className="node-card__port-row">
              {editing === port.id ? (
                <input
                  className="nodrag node-card__block-port-input"
                  aria-label="Popisek portu"
                  defaultValue={port.label}
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
                  {port.label}
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
              <Handle
                type="source"
                position={Position.Right}
                id={blockHandleId(blockId, port.id)}
                className="nodrag node-card__block-port-dot"
                isConnectableStart
                isConnectableEnd={false}
                data-testid={"card-port-handle-" + port.id}
              />
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
