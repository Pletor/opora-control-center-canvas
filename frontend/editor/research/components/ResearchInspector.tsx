import ResearchAttachments from "./ResearchAttachments";
import ResearchDecision from "./ResearchDecision";
import ResearchContent from "./ResearchContent";
import type { ResearchDetail, ResearchEdgeDetail, ResearchEdge, ResearchHeader, ResearchScope } from "../logic/research-types";
import { KIND_LABELS, RELATION_LABELS, sourceUrl, topicLabel, VERIFICATION_LABELS } from "../logic/research-model";
type Props = {
  scope: ResearchScope; edgeDetail: ResearchEdgeDetail | null;
  card: ResearchHeader | undefined; detail: ResearchDetail | null; edge: ResearchEdge | undefined; cards: ResearchHeader[];
  loading: boolean; error: string; revision?: number; writing: boolean; readOnly: boolean; nodeNames: Map<string,string>;
  onRevision: (revision?: number) => void; onSelect: (id: string) => void; onClose: () => void;
  onArchive: (entity: "card" | "edge", id: string, revision: number, archived: boolean) => void;
  onOpenNode: (id: string) => void; onDraw: (id: string) => void;
};
const date = (value?: string) => value ? new Date(value).toLocaleString("cs-CZ") : "Neuvedeno";
export default function ResearchInspector(props: Props) {
  const { card, detail, edge, cards, loading, error, revision, writing, readOnly, nodeNames, onRevision, onSelect, onClose, onArchive, onOpenNode, onDraw } = props;
  const archiveButton = (entity: "card" | "edge", item: { id: string; revision: number; archived: boolean }) => <button type="button" disabled={writing || readOnly} onClick={() => onArchive(entity, item.id, item.revision, !item.archived)}>{item.archived ? "Obnovit z archivu" : "Archivovat"}</button>;
  const cardLink = (id: string) => <button className="research-inspector__link" type="button" key={id} onClick={() => onSelect(id)}>{cards.find(item => item.id === id)?.title ?? id}</button>;
  const full = detail?.card;
  const historySelect = (history: ResearchDetail["history"]) => <label className="research-inspector__history">Verze <select aria-label="Verze záznamu" value={revision ?? "current"} onChange={event => onRevision(event.target.value === "current" ? undefined : Number(event.target.value))}>
    <option value="current">Aktuální</option>{history.map(item => <option key={item.revision} value={item.revision}>Revize {item.revision}{item.updatedAt ? ` · ${date(item.updatedAt)}` : ""}</option>)}
  </select></label>;
  return <aside className="research-inspector" aria-label={edge ? "Význam propojení" : "Detail rešerše"}>
    <header><span>{edge ? "Odkud → kam → proč" : "Úplný kontext"}</span><button type="button" aria-label="Zavřít detail" onClick={onClose}>×</button></header>
    {edge ? <>
      {loading && <p role="status">Načítám význam a historii propojení…</p>}{error && <p role="alert">{error}</p>}
      {props.edgeDetail && historySelect(props.edgeDetail.history)}
      {revision !== undefined && <p className="research-inspector__notice">Historická revize {revision} této vazby.</p>}
      {!loading && !error && (revision === undefined || props.edgeDetail) && <>
      <div className="research-inspector__route">{cardLink(edge.fromId)}<strong>→ {RELATION_LABELS[edge.relation]} →</strong>{cardLink(edge.toId)}</div>
      <section><h3>Proč tato cesta</h3><p>{edge.reason}</p></section>
      <section><h3>Co je vyřešeno</h3><p>{edge.resolved || "Na této vazbě neuvedeno."}</p></section>
      <section><h3>Co ještě chybí</h3><p>{edge.missing || "Na této vazbě neuvedeno."}</p></section>
      {!!edge.evidenceIds.length && <section><h3>Podklady</h3>{edge.evidenceIds.map(cardLink)}</section>}
      <small>{edge.id} · revize {edge.revision}</small>{revision === undefined && !loading && archiveButton("edge", edge)}
      </>}
    </> : <>
      <h2>{full?.title ?? card?.title ?? "Načítání kartičky"}</h2>
      {loading && <p role="status">Načítám úplný kontext…</p>}{error && <p role="alert">{error}</p>}
      {full && <>
        <div className="research-card__badges"><span className="research-badge">{KIND_LABELS[full.kind]}</span><span className={`research-badge research-badge--${full.verification.status}`}>{VERIFICATION_LABELS[full.verification.status]}</span>{full.archived && <span className="research-badge">Archiv</span>}</div>
        <p className="research-inspector__topic">{topicLabel(full.topicPath)}</p>
        {full.kind === "decision" && <p className="research-inspector__notice">Záznam rozhodnutí sám o sobě nedokládá schválení člověkem. Rozhodující jsou připojené podklady.</p>}
        {historySelect(detail.history)}
        {revision !== undefined && <p className="research-inspector__notice">Historická revize {revision}. Vazby níže zobrazují současné souvislosti.</p>}
        <section><h3>Závěr</h3><p>{full.summary}</p></section>
        <section><h3>Úplný obsah</h3><ResearchContent content={full.content} /></section>
        {full.kind === "decision" && <ResearchDecision key={`${props.scope.project}:${props.scope.workspace}:${full.id}:${full.revision}`}
          scope={props.scope} card={full} cards={cards} nodeNames={nodeNames} readOnly={readOnly || revision !== undefined || writing} onOpenNode={onOpenNode} />}
        <section><h3>Ověření</h3><p>{full.verification.method || "Způsob ověření neuveden."}</p><small>{date(full.verification.at)}</small></section>
        <section><h3>Zdroje a citace · {full.sources.length}</h3>{!full.sources.length && <p>Bez připojeného zdroje.</p>}
          {full.sources.map((source, index) => { const url = sourceUrl(source.ref); return <article className="research-source" key={`${source.ref}:${index}`}>
            <span className="research-badge">{source.platform}</span><h4>{source.title || "Zdroj"}</h4>
            {source.verification && <p>Doklad: {VERIFICATION_LABELS[source.verification.status]} · {source.verification.method} · {date(source.verification.at)}</p>}
            {url ? <a href={url} target="_blank" rel="noopener noreferrer">{source.ref}</a> : <code>{source.ref}</code>}
            {source.quote && <blockquote>{source.quote}</blockquote>}<small>Získáno {date(source.accessedAt)}{source.timestamp ? ` · Čas ve videu: ${source.timestamp}` : ""}{source.revision ? ` · Revize: ${source.revision}` : ""}{source.location ? ` · Umístění: ${source.location}` : ""}{source.discoveredVia ? ` · Nalezeno přes: ${source.discoveredVia}` : ""}</small>
          </article>; })}
        </section>
        {!!full.refs.nodeIds.length && <section><h3>Ve Struktuře</h3>{full.refs.nodeIds.map(id => <div className="research-inspector__node" key={id}>
          {nodeNames.has(id) ? <><button type="button" onClick={() => onOpenNode(id)}>{nodeNames.get(id)}</button><button type="button" onClick={() => onDraw(id)}>Kreslení</button></> : <span>{id} · původní uzel nyní není v plátně</span>}
        </div>)}</section>}
        {Object.entries(full.refs).filter(([key, values]) => key !== "nodeIds" && key !== "attachmentIds" && values.length).map(([key, values]) => <section key={key}><h3>{{ questionIds: "Otázky Pletora", ticketIds: "Tickety", sessionIds: "Relace", fragmentIds: "Schránka", attachmentIds: "Přílohy / vizuální podklady" }[key] ?? key}</h3>{(values as string[]).map(id => <code className="research-inspector__ref" key={id}>{id}</code>)}</section>)}
        {!!full.refs.attachmentIds.length && <ResearchAttachments key={`${full.id}:${full.revision}`} scope={props.scope} ids={full.refs.attachmentIds} />}
        {!!detail.edges.length && <section><h3>Navazující cesta</h3>{detail.edges.map(link => <div className="research-inspector__connection" key={link.id}><strong>{link.fromId === full.id ? "→" : "←"} {RELATION_LABELS[link.relation]}{link.archived ? " · Archiv" : ""}</strong>{cardLink(link.fromId === full.id ? link.toId : link.fromId)}<p>{link.reason}</p></div>)}</section>}
        <small>{full.id} · revize {full.revision} · {full.by} · {date(full.updatedAt)}</small>
        {revision === undefined && archiveButton("card", full)}
      </>}
    </>}
  </aside>;
}
