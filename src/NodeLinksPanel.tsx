import { useEffect, useState } from "react";
import { api } from "@/types";
import "@/natural-canvas.css";

export type NodeLink = { nodeId: string; name: string; kind: string; via: "text" | "edge"; direction: "in" | "out" };
export type NodeLinksResult = {
  node: string;
  outgoing: NodeLink[];
  unresolved: string[];
  backlinks: NodeLink[];
  edges: NodeLink[];
  counts: { outgoing: number; backlinks: number; edges: number; unresolved: number };
};

/** Souvislosti se čtou ze stejné autority jako plátno: text uzlu a hrany grafu. */
export default function NodeLinksPanel({
  project,
  workspace,
  node,
  revision,
  readOnly,
  onOpenNode,
}: {
  project: string;
  workspace: string;
  node: string;
  /** Změna vynutí přenačtení po uložení textu. */
  revision: number;
  /** Na mainu se souvislosti nepočítají: je to jen projekce schválené větve. */
  readOnly: boolean;
  onOpenNode: (nodeId: string) => void;
}) {
  const [value, setValue] = useState<NodeLinksResult | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (readOnly) return;
    let alive = true;
    api<NodeLinksResult>("/api/node-links?" + new URLSearchParams({ project, workspace, node }))
      .then((result) => alive && setValue(result))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [project, workspace, node, revision, readOnly]);

  function group(title: string, items: NodeLink[], testId: string) {
    return (
      <div className="links-group">
        <h4>
          {title} <span data-testid={testId + "-count"}>{items.length}</span>
        </h4>
        {items.length ? (
          <ul>
            {items.map((link) => (
              <li key={link.via + link.direction + link.nodeId}>
                <button type="button" data-testid={testId} onClick={() => onOpenNode(link.nodeId)}>
                  {link.direction === "out" ? "→" : "←"} {link.name}
                  <em>{link.via === "edge" ? "hrana plátna" : "odkaz v textu"}</em>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Žádné.</p>
        )}
      </div>
    );
  }

  return (
    <section className="node-links" aria-label="Souvislosti uzlu" data-testid="node-links">
      {readOnly && <p className="muted">Main je pouze pro čtení; souvislosti se počítají v pracovním prostoru.</p>}
      {!readOnly && error && <div role="alert">{error}</div>}
      {!readOnly && !value && !error && <p className="muted">Načítám souvislosti…</p>}
      {!readOnly && value && (
        <>
          {group("Odkazuje na", value.outgoing, "link-out")}
          {group("Odkazuje sem", value.backlinks, "link-in")}
          {group("Hrany plátna", value.edges, "link-edge")}
          {!!value.unresolved.length && (
            <p className="muted" data-testid="link-unresolved">
              Nevyřešené odkazy ({value.unresolved.length}): {value.unresolved.join(", ")} — uzel s tímto jménem
              zatím neexistuje a sám nevznikne.
            </p>
          )}
        </>
      )}
    </section>
  );
}
