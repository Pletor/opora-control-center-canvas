import type { ReactNode } from "react";
import type { DodView } from "../logic/card-dod";
import type { StatusLine } from "../logic/card-header";

type Props = {
  title: string; nodeId: string; kind: string; trail: string; status: StatusLine; lease: ReactNode; holder: string;
  dod: DodView; onClose: () => void;
};

/** Hlavička: druh a cesta, název, jeden stavový řádek, kdo kartu drží a šest dílků definice hotovo. */
export default function DrawerHeader({ title, nodeId, kind, trail, status, lease, holder, dod, onClose }: Props) {
  return <header className="card-drawer__head">
    <div className="card-drawer__topline">
      <span className="card-drawer__kind" data-oh-field="kind" data-oh-value={kind}>{kind}</span>
      <span className="card-drawer__trail">{trail}</span>
      <kbd className="card-drawer__esc" aria-hidden="true">Esc</kbd>
      <button type="button" className="card-drawer__close" aria-label="Zavřít detail karty" data-oh-close="card-drawer" onClick={onClose}>✕</button>
    </div>
    <h2 id="card-drawer-title" className="card-drawer__title" data-oh-node-id={nodeId}>{title}</h2>
    <div className="card-drawer__status" data-oh-field="status" data-oh-health={status.health} data-oh-stage={status.stage} data-oh-reason={status.reasonCode}>
      <span className={`card-drawer__health card-drawer__health--${status.health}`}><span aria-hidden="true">{status.glyph}</span> {status.word}</span>
      <span className="card-drawer__status-text">{status.stage} · {status.reason}{lease && <> · lease {lease}</>}</span>
      {holder && <span className="card-drawer__holder" data-oh-field="lease-holder" data-oh-value={holder}>
        <span className="card-drawer__avatar card-drawer__avatar--agent" aria-hidden="true">A</span>{holder}</span>}
    </div>
    <div className="card-drawer__dod" role="list" aria-label="Definice hotového" data-oh-dod-source={dod.source} data-oh-dod-done={String(dod.done)}>
      <span className="card-drawer__dod-label">Definice hotového{dod.source === "computed" ? "" : " · server"}</span>
      <div className="card-drawer__dod-bars">
        {dod.segments.map(segment => <div key={segment.key} role="listitem" className={`card-drawer__dod-seg card-drawer__dod-seg--${segment.state}${segment.key === "human_close" ? " card-drawer__dod-seg--human" : ""}`}
          data-oh-dod={segment.key} data-oh-dod-state={segment.state} title={`${segment.label}: ${segment.state}${segment.detail ? ` · ${segment.detail}` : ""}`}>
          <span className="card-drawer__dod-track"><i className="card-drawer__dod-fill" style={{ width: `${Math.round(segment.progress * 100)}%` }} /></span>
          <span className="card-drawer__dod-name">{segment.label}{segment.key === "steps" && segment.detail ? ` ${segment.detail}` : ""}</span>
        </div>)}
      </div>
    </div>
  </header>;
}
