import type { DodView } from "../logic/card-dod";
import "../styles/card-drawer.css";

/** Sedm dílků definice hotovo (brány karty). Hlavička detailu je kreslí v řádku, úzký sloupec (Detail prvku) jako dlaždice. */
export default function DodBars({ dod, tiles = false }: { dod: DodView; tiles?: boolean }) {
  return <div className={`card-drawer__dod${tiles ? " card-drawer__dod--tiles" : ""}`} role="list" aria-label="Definice hotového"
    data-oh-dod-source={dod.source} data-oh-dod-done={String(dod.done)}>
    <span className="card-drawer__dod-label">Definice hotového{dod.source === "computed" ? "" : " · server"}</span>
    <div className="card-drawer__dod-bars">
      {dod.segments.map(segment => <div key={segment.key} role="listitem" className={`card-drawer__dod-seg card-drawer__dod-seg--${segment.state}${segment.key === "human_close" ? " card-drawer__dod-seg--human" : ""}`}
        data-oh-dod={segment.key} data-oh-dod-state={segment.state} title={`${segment.label}: ${segment.state}${segment.detail ? ` · ${segment.detail}` : ""}`}>
        <span className="card-drawer__dod-track"><i className="card-drawer__dod-fill" style={{ width: `${Math.round(segment.progress * 100)}%` }} /></span>
        <span className="card-drawer__dod-name">{segment.label}{segment.key === "steps" && segment.detail ? ` ${segment.detail}` : ""}</span>
      </div>)}
    </div>
  </div>;
}
