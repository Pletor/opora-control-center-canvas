// Detail fragmentu schránky: cesta ve stromu, doslovný text vybrané revize (jen ke čtení, zachované řádky),
// historie revizí s výběrem, čipy karet vzniklých z fragmentu a jeho Podněty. Nic nezapisuje.
import { useState, type ReactNode } from "react";
import { revisionLabel, statusDot } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useFragmentDetail } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import "@/editor/node-detail/ideas/styles/ideas.css";

export default function FragmentDetailView({ project, workspace, id, nodeNames, onOpenNode, onClose, refresh, actions }: {
  project: string;
  workspace: string;
  id: string;
  nodeNames: Record<string, string>;
  onOpenNode: (id: string) => void;
  onClose: () => void;
  /** Změna (nový strom) načte detail znovu. */
  refresh: unknown;
  /** Akce nad fragmentem od rodiče (Schránka: stopa, výzkum, otázka). */
  actions?: ReactNode;
}) {
  const [revision, setRevision] = useState<number | null>(null);
  const { detail, error } = useFragmentDetail(project, workspace, id, revision, refresh);
  if (error) return <section className="brief-vault__detail"><p className="error" role="alert">Fragment nelze načíst: {error}</p></section>;
  if (!detail) return <section className="brief-vault__detail"><p className="muted" role="status">Načítám fragment…</p></section>;
  const { fragment } = detail;
  const dot = statusDot({ ...fragment, status: detail.status });
  const old = fragment.revision !== detail.latestRevision;
  return (
    <section className="brief-vault__detail" aria-label={"Fragment " + fragment.title} data-testid="brief-vault-detail">
      <header className="brief-vault__detail-head">
        <div>
          <div className="brief-vault__path">{detail.path.map((item) => item.title).join(" › ")}</div>
          <h4>
            <span className={"brief-vault__dot brief-vault__dot--" + dot.tone} aria-hidden="true" /> {fragment.title}
          </h4>
          <span className="brief-vault__meta">{dot.label} · r{fragment.revision} z {detail.latestRevision} · {fragment.text.length} znaků</span>
        </div>
        <button type="button" className="brief-vault__close" aria-label="Zavřít detail fragmentu" onClick={onClose}>×</button>
      </header>
      {old && <p className="brief-vault__old" role="status">Prohlížíte starší revizi r{fragment.revision}; poslední je r{detail.latestRevision}.</p>}
      <pre className="brief-vault__text" tabIndex={0} aria-label="Doslovný text fragmentu">{fragment.text || "(prázdný text)"}</pre>
      {actions && <div className="brief-vault__actions">{actions}</div>}

      <h5>Karty ze schránky</h5>
      {detail.cards.length ? (
        <div className="brief-vault__chips">
          {detail.cards.map((card) => (
            <button key={card.nodeId} type="button" className={"brief-chip" + (card.changedSinceInsert ? " brief-chip--changed" : "")}
              title={card.changedSinceInsert ? `Karta vznikla z r${card.revision}, poslední je r${detail.latestRevision}` : `Karta vznikla z r${card.revision}`}
              onClick={() => onOpenNode(card.nodeId)}>
              {nodeNames[card.nodeId] ?? card.nodeId.slice(0, 8)} · r{card.revision}{card.changedSinceInsert ? " ⚠" : ""}
            </button>
          ))}
        </div>
      ) : <p className="muted">Zatím žádná karta: fragment je uložený, nevložený.</p>}

      <h5>Historie revizí</h5>
      <ol className="brief-vault__history">
        {detail.history.slice().reverse().map((item) => (
          <li key={item.revision}>
            <button type="button" className="brief-vault__revision" aria-pressed={item.revision === fragment.revision}
              onClick={() => setRevision(item.revision === detail.latestRevision ? null : item.revision)}>
              {revisionLabel(item)}
            </button>
            {item.note && <span className="brief-vault__note">{item.note}</span>}
          </li>
        ))}
      </ol>

      {detail.children.some((child) => child.kind === "research") && (
        <>
          <h5>Výzkum</h5>
          <ul className="brief-vault__research">
            {detail.children.filter((child) => child.kind === "research").map((child) => (
              <li key={child.id}>
                <span className={"brief-vault__dot brief-vault__dot--" + statusDot(child).tone} aria-hidden="true" /> {child.title}
                <span className="brief-vault__meta"> · {statusDot(child).label}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h5>Podněty fragmentu</h5>
      {detail.ideas.length ? (
        <ul className="ideas">
          {detail.ideas.map((idea) => (
            <li key={idea.nodeId + ":" + idea.ideaId} className={"ideas__item" + (idea.status === "done" ? " ideas__item--done" : "")}>
              <span className="ideas__text">{idea.text}</span>
              <span className="ideas__meta">{nodeNames[idea.nodeId] ?? idea.nodeId.slice(0, 8)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="ideas__empty">K fragmentu zatím nejsou Podněty.</p>}
    </section>
  );
}
