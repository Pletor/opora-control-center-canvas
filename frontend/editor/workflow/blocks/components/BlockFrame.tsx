// Rám bloku u karty: levý úchyt, hlavička s názvem a zavřením, tělo. Obsah dodává potomek (Akce / Pravidla).
// Přetahovat blok po plátně jde za hlavičku; tělo a zavírací křížek nesou `nodrag` jako na kartě.
import type { ReactNode } from "react";
import { Handle, Position } from "@xyflow/react";
import { BLOCK_LABEL, blockNodeId, type BlockPort } from "@/editor/workflow/blocks/logic/block-model";

export default function BlockFrame({
  nodeId,
  nodeName,
  port,
  note,
  onClose,
  children,
}: {
  nodeId: string;
  nodeName: string;
  port: BlockPort;
  note: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className={`canvas-block block-${port}`} data-testid={blockNodeId(nodeId, port)}>
      <Handle type="target" position={Position.Left} id={port} isConnectable={false} />
      <header title="Táhnutím za hlavičku blok přesuneš po plátně">
        <span>{port === "action" ? "⚡" : port === "rule" ? "◎" : port === "pipeline" ? "⇶" : "▣"} {BLOCK_LABEL[port]} · {nodeName}</span>
        <button type="button" className="nodrag" title="Skrýt blok (položky zůstávají uložené)" onClick={onClose}>✕</button>
      </header>
      <div className="block-body nodrag">
        <p className="block-note">{note}</p>
        {children}
      </div>
    </div>
  );
}
