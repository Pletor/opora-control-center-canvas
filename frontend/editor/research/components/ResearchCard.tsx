import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { KIND_LABELS, topicLabel, VERIFICATION_LABELS } from "../logic/research-model";
import type { ResearchHeader } from "../logic/research-types";
export type ResearchFlowNode = Node<{ card: ResearchHeader }, "research">;
export default function ResearchCard({ data: { card }, selected }: NodeProps<ResearchFlowNode>) {
  return <article className={`research-card${selected ? " research-card--selected" : ""}${card.archived ? " research-card--archived" : ""}`}>
    <Handle type="target" position={Position.Left} />
    <div className="research-card__eyebrow"><span>{KIND_LABELS[card.kind]}</span><span>{card.archived ? "Archiv" : card.status === "resolved" ? "Uzavřeno" : "Otevřeno"}</span></div>
    <div className="research-card__topic" title={topicLabel(card.topicPath)}>{topicLabel(card.topicPath)}</div>
    <h3>{card.title}</h3><p>{card.summary}</p>
    <div className="research-card__badges"><span className={`research-badge research-badge--${card.verification.status}`}>{VERIFICATION_LABELS[card.verification.status]}</span>
      {card.refs.nodeIds.length > 1 && <span className="research-badge" title="Jeden podklad připojený k více pracovním kontextům">Sdílený podklad</span>}
      {card.platforms.slice(0, 4).map(platform => <span className="research-badge" key={platform}>{platform}</span>)}
      {card.platforms.length > 4 && <span className="research-badge">+{card.platforms.length - 4} dalších</span>}
    </div>
    {card.relationCounts && <div className="research-card__relations" aria-label="Návaznosti" title="Směrované vazby v načtené rešerši před filtrováním">
      {card.relationCounts.incoming} příchozích · {card.relationCounts.outgoing} odchozích vazeb
    </div>}
    <footer><span>{card.sourceCount} zdrojů</span><span title={card.id}>{card.id}</span></footer>
    <Handle type="source" position={Position.Right} />
  </article>;
}
