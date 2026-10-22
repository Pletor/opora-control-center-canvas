import type { GraphDoc } from "@coldtea/pr-lens-schema";
import { blobUrl, fileLabel, safePath, type Repo } from "../logic/code-links";

export const DELTA_WORD: Record<string, string> = { added: "nové", modified: "změněné", removed: "odebrané", unchanged: "beze změny" };

type Props = { doc: GraphDoc; nodeId: string; repo: Repo; headSha: string; onSelect: (nodeId: string) => void; onClose: () => void };

/** Panel části: co to je, jak se změnila, kde v kódu leží (cesty a řádky, odkazy jen přes naši bránu) a s čím je spojená. */
export default function CardPanel({ doc, nodeId, repo, headSha, onSelect, onClose }: Props) {
  const node = doc.nodes.find(item => item.id === nodeId);
  if (!node) return null;
  const label = (id: string) => doc.nodes.find(item => item.id === id)?.label ?? id;
  const lane = doc.lanes.find(item => item.id === node.lane)?.label;
  const incoming = doc.edges.filter(edge => edge.to === nodeId), outgoing = doc.edges.filter(edge => edge.from === nodeId);
  const edgeList = (edges: typeof incoming, other: "from" | "to", arrow: string) => edges.length
    ? <ul className="review-lens__list">{edges.map(edge => <li key={edge.id} className="review-lens__edge" data-oh-lens-edge={edge.id}>
      <span className={`review-lens__delta review-lens__delta--${edge.delta}`}>{arrow}</span>
      <button type="button" className="review-lens__link-button" onClick={() => onSelect(edge[other])}>{label(edge[other])}</button>
      {edge.label && <span className="review-lens__muted">{edge.label}</span>}</li>)}</ul>
    : <p className="review-lens__muted">žádné</p>;
  return <section className="review-lens__panel" data-oh-lens-card={nodeId} data-oh-lens-delta={node.delta}>
    <div className="review-lens__panel-head">
      <span className={`review-lens__chip review-lens__chip--${node.delta}`}>{DELTA_WORD[node.delta] ?? node.delta}</span>
      {node.badges.map(badge => <span key={badge} className={`review-lens__chip${badge === "plán" ? " review-lens__chip--plan" : ""}`} data-oh-lens-badge={badge}>{badge}</span>)}
      <code className="review-lens__muted">{node.kind}{lane ? ` · ${lane}` : ""}</code>
      <span className="review-lens__grow" />
      <button type="button" className="review-lens__close" aria-label="Zavřít detail části" onClick={onClose}>✕</button>
    </div>
    <h3 className="review-lens__panel-title">{node.label}</h3>
    {node.subtitle && <code className="review-lens__muted">{node.subtitle}</code>}
    {node.summary && <p className="review-lens__panel-text">{node.summary}</p>}
    <h4 className="review-lens__panel-label">Soubory</h4>
    {node.files.length ? <ul className="review-lens__list">{node.files.map((file, index) => {
      const path = safePath(file.path);
      const url = path ? blobUrl(repo, file.revision === "base" ? doc.provenance.base.sha : headSha, file) : null;
      return <li key={index} className="review-lens__file" data-oh-lens-file={path ?? ""}>
        <code className="review-lens__path">{path ? fileLabel(file) : "neplatná cesta"}</code>
        {url && <a className="review-lens__ext" href={url} target="_blank" rel="noreferrer noopener">GitHub ↗</a>}
      </li>;
    })}</ul> : <p className="review-lens__muted">bez souborů (vnější část)</p>}
    <h4 className="review-lens__panel-label">Příchozí vazby</h4>{edgeList(incoming, "from", "←")}
    <h4 className="review-lens__panel-label">Odchozí vazby</h4>{edgeList(outgoing, "to", "→")}
  </section>;
}
