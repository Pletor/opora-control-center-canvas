import { useState } from "react";
import type { Graph, Project, View } from "./types";
import { downloadArchify } from "./project-map";

/** Kontext módu Mapa: skutečné počty, propojení výběrem (klávesnicová cesta k tažení na mapě) a export. */
export default function MapTools({
  graph,
  view,
  activeProject,
  editable,
  onConnect,
}: {
  graph: Graph;
  view: View | null;
  activeProject?: Project;
  editable: boolean;
  onConnect: (source: string, target: string) => void;
}) {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const name = activeProject?.name ?? "Lokální návrh";
  const options = graph.nodes.map((n) => (
    <option key={n.id} value={n.id}>
      {n.name}
    </option>
  ));
  return (
    <section className="map-tools" aria-label="Nástroje mapy">
      <dl className="facts">
        <dt>Uzly</dt>
        <dd data-testid="map-node-count">{graph.nodes.length}</dd>
        <dt>Propojení</dt>
        <dd>{graph.edges.length}</dd>
      </dl>
      {view?.graphStatus === "missing" && (
        <p role="status" className="muted">
          Repozitář nemá uložený graf. Mapa není automatická analýza jeho souborů.
        </p>
      )}
      <p className="muted">Přerušovaně: struktura. Plně: explicitní propojení. Dvojklik otevře uzel ve Struktuře.</p>
      <div className="field-row">
        <label className="field">
          Propojit z
          <select aria-label="Propojit z" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Vyber uzel</option>
            {options}
          </select>
        </label>
        <label className="field">
          Propojit do
          <select aria-label="Propojit do" value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Vyber uzel</option>
            {options}
          </select>
        </label>
      </div>
      <div className="action-row">
        <button type="button" disabled={!editable || !source || !target || source === target} onClick={() => onConnect(source, target)}>
          Propojit uzly
        </button>
        <button type="button" onClick={() => downloadArchify(graph, name)} title="Export odráží tato data, nikoli odhad technologií ze zdrojového kódu.">
          Export pro Archify
        </button>
      </div>
    </section>
  );
}
