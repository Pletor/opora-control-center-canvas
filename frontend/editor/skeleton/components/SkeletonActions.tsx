import { useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { STARTER_SECTORS, structureNodes } from "../logic/skeleton";
import "../styles/skeleton.css";

/** Creation controls for the single project tree in Library > Structure. */
export default function SkeletonActions({ nodes, selected, readOnly, busy, onEnter, onAdd }: {
  nodes: CanvasNode[]; selected: string | null; readOnly: boolean; busy: boolean;
  onEnter: (id: string | null) => void;
  onAdd: (parentId: string | null, names: string[], kind: "node" | "sector") => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [atRoot, setAtRoot] = useState(false);
  const [optional, setOptional] = useState<string[]>([]);
  const [error, setError] = useState("");
  const selectedNode = structureNodes(nodes).find((node) => node.id === selected);
  const parentId = atRoot ? null : selectedNode?.id ?? null;
  async function add(names: string[], target: string | null, kind: "node" | "sector") {
    setError("");
    try { await onAdd(target, names, kind); if (names.length === 1) setName(""); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  return <div className="skeleton">
    <div className="action-row"><button type="button" onClick={() => onEnter(null)}>Kořen návrhu</button>
      {selectedNode && <button type="button" onClick={() => onEnter(selectedNode.id)}>Otevřít uvnitř: {selectedNode.name}</button>}
    </div>
    <form className="skeleton__form" onSubmit={(event) => { event.preventDefault(); if (name.trim()) void add([name], parentId, parentId ? "node" : "sector"); }}>
      <label className="field">Nová část<input aria-label="Název nové části" maxLength={160} value={name} onChange={(event) => setName(event.target.value)} disabled={readOnly || busy} /></label>
      {selectedNode && <label className="check"><input type="checkbox" checked={atRoot} onChange={(event) => setAtRoot(event.target.checked)} /> Přidat do kořene</label>}
      <small>Umístění: {parentId ? selectedNode?.name : "kořen návrhu"}</small>
      <button type="submit" disabled={readOnly || busy || !name.trim()}>Přidat část</button>
    </form>
    <details className="skeleton__starter"><summary>Založit hlavní části</summary>
      <p>Frontend · Backend · Databáze</p>
      {STARTER_SECTORS.slice(3).map((item) => <label className="check" key={item}><input type="checkbox" disabled={readOnly || busy} checked={optional.includes(item)} onChange={(event) => setOptional((current) => event.target.checked ? [...current, item] : current.filter((value) => value !== item))} />{item}</label>)}
      <button type="button" disabled={readOnly || busy} onClick={() => void add([...STARTER_SECTORS.slice(0, 3), ...optional], null, "sector")}>Doplnit chybějící části</button>
    </details>
    {readOnly && <p className="skeleton__hint">Pro úpravy otevřete pracovní prostor.</p>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
