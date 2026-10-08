import { Handle, Position } from "@xyflow/react";
import type { CardBlockRow } from "@/editor/canvas/node-card/logic/card-model";
import { blockHandleId } from "@/shared/types/logic/types";
import "@/editor/card-dna/styles/card-dna.css";

/** Jednořádkový obraz bloků pro plátno; editory a jejich lokální stav patří až do DNA dialogu. */
export default function CardDnaCompactBlocks({ id, rows, selectedBlockId }: { id: string; rows: CardBlockRow[]; selectedBlockId?: string }) {
  return <ol className="card-dna-compact__blocks" data-testid={`card-dna-compact-blocks-${id}`}>
    {rows.map(row => <li key={row.id} className={"card-dna-compact__block card-dna-compact__block--" + row.status + (selectedBlockId === row.id ? " card-dna-compact__block--selected" : "")} data-block-id={row.id}>
      <span className="card-dna-compact__number">{row.number}</span>
      <span className="card-dna-compact__title" title={row.title}>{row.title}</span>
      <span className="card-dna-compact__state" aria-label={row.status} title={row.status} />
      {row.ports.map(port => <span key={port.id} className="card-dna-compact__port" title={port.label}>
        <span className="card-dna-compact__port-label">{port.label}</span>
        <Handle type="source" position={Position.Right} id={blockHandleId(row.id, port.id)} className="nodrag card-dna-compact__port-handle" isConnectableStart isConnectableEnd={false} data-testid={`card-port-handle-${port.id}`} />
      </span>)}
    </li>)}
  </ol>;
}
