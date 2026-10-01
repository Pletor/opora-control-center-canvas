// Pořadí segmentů na ploše Agenti: pás Přehled přes celou šířku, pod ním dvojice Start pro agenta
// a Komunikace, za nimi Paměť role přes celý řádek a nakonec pět polí paměti karty jako stejně
// široké sloupce. Dílek jen rozestavuje hotové kusy, které mu pracovní prostor podá v props —
// o jejich obsah, načítání ani ukládání se nestará. Paměť role je volitelná: v inspektoru
// (`layout="stack"`) se nekreslí vůbec, takže do úzkého sloupce nepřibude cizí služba.
// Přehled se nesbaluje; zbytek má rozbalení od desky, aby platilo pro celou aplikaci, ne pro kartu.
import type { ReactNode } from "react";
import AgentSegment from "@/editor/node-detail/agent-workspace/segments/components/AgentSegment";
import { SEGMENTS, type SegmentDef, type SegmentId, type SegmentOpen } from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";

const of = (id: SegmentId): SegmentDef => SEGMENTS.find((segment) => segment.id === id) as SegmentDef;

export default function AgentSegmentsLayout({
  nodeId,
  open,
  onToggle,
  overview,
  start,
  communication,
  roleMemory,
  memory,
}: {
  nodeId: string;
  open?: SegmentOpen;
  onToggle?: (id: SegmentId, open: boolean) => void;
  overview: ReactNode;
  start: ReactNode;
  communication: ReactNode;
  /** Paměť role (OpenViking). Chybí-li, segment se vůbec nekreslí — nic se tím nenačítá naprázdno. */
  roleMemory?: ReactNode;
  /** Pět polí paměti karty už jako hotové segmenty: skládá je `AgentMemorySections`, ne tenhle dílek. */
  memory: ReactNode;
}) {
  const toggle = (id: SegmentId) => (isOpen: boolean) => onToggle?.(id, isOpen);
  return <>
    <AgentSegment nodeId={nodeId} segment={of("overview")} open collapsible={false} onToggle={toggle("overview")}>
      {overview}
    </AgentSegment>
    <AgentSegment nodeId={nodeId} segment={of("orientation")} open={open?.orientation !== false} onToggle={toggle("orientation")}>
      {start}
    </AgentSegment>
    <AgentSegment nodeId={nodeId} segment={of("communication")} open={open?.communication !== false} onToggle={toggle("communication")}>
      {communication}
    </AgentSegment>
    {roleMemory && <AgentSegment nodeId={nodeId} segment={of("memory")} open={open?.memory === true} onToggle={toggle("memory")}>
      {roleMemory}
    </AgentSegment>}
    {memory}
  </>;
}
