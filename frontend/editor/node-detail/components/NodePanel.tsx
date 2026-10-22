import { useState } from "react";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import SectorDecompose from "@/editor/sector-detail/components/SectorDecompose";
import IdeasSummary from "@/editor/sector-detail/components/IdeasSummary";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import type { CanvasNode, SpecFields } from "@/shared/types/logic/types";

/**
 * Inspektor vybraného uzlu v Editoru. Celý detail karty (zadání, kroky, běh, review, historie) je jediný
 * drawer `hub/oporahub-card-drawer`; tady zůstává jen to, co patří plátnu: identita a zdroj, vstup do
 * vnitřního plátna, balíček pro agenta, Schránka, rozklad sektoru a smazání. Ukládá rodič (App).
 */
export default function NodePanel({
  node, project, workspace, readOnly, busy, onEnter, onDelete, onAgentTask, onOpenVault, specRefreshRevision,
  childCount = 0, openIdeasInSector = 0,
}: {
  node: CanvasNode;
  project: string;
  workspace: string;
  readOnly: boolean;
  busy: boolean;
  onEnter: () => void;
  onDelete: () => void;
  /** Připraví scope úkolu pro panel agenta; žádný běh nespouští. */
  onAgentTask: () => void;
  /** Otevře Schránku v levém menu na rozsahu uzlu. */
  onOpenVault?: (scope: string, focus?: string) => void;
  specRefreshRevision?: number;
  /** Počet karet (`kind: "node"`) přímo v sektoru; spočítá rodič z grafu, čte ho jen rozklad sektoru. */
  childCount?: number;
  /** Otevřené podněty v kartách sektoru; spočítá rodič, > 0 ukáže „Shrnout podněty“. */
  openIdeasInSector?: number;
}) {
  // Uložené zadání sektoru i s klíčem uzlu: rozkladač ho dostane jen pro právě vybraný uzel.
  const [storedSpec, setStoredSpec] = useState<{ key: string; fields: SpecFields | null; error: string } | null>(null);
  const specForNode = storedSpec?.key === JSON.stringify([project, workspace, node.id]) ? storedSpec : null;
  const sector = node.kind === "sector";
  const kind = node.site?.kind === "application" ? "Aplikace" : node.site?.kind === "page" ? "Stránka" : sector ? "Sektor" : "Karta";
  return (
    <div className="node-panel">
      <header className="panel-head">
        <div className="eyebrow">{kind.toLocaleUpperCase("cs")} · INSPEKTOR</div>
        <h2>{node.name}</h2>
        <details><summary>Identita a zdroj</summary><code className="identity">{node.id}</code>
        {node.sourceRef && (
          <p className={"source-badge " + (node.sourceRef.origin === "existing" ? "source-badge-existing" : "source-badge-planned")}>
            {node.sourceRef.origin === "existing" ? "Existující zdroj" : "Návrh zdroje"}: <code>{node.sourceRef.path || (node.sourceRef.origin === "planned" ? "cesta neurčena" : "/")}</code> ({node.sourceRef.kind === "directory" ? "složka" : "soubor"})
          </p>
        )}
        </details>
        <div className="action-row">
          <button type="button" className="primary" data-testid="open-card-drawer" onClick={() => openCardDrawer(node.id)}
            title="Jednotný detail: zadání, kroky, běh, review & PR, historie (dvojklik na kartu).">
            {sector ? "Detail sektoru" : "Detail karty"}
          </button>
          <button type="button" onClick={onEnter}>Otevřít vnitřní plátno</button>
          <button type="button" data-testid="agent-task-action" disabled={busy} onClick={onAgentTask}
            title="Otevře uložené zadání, souvislosti a kontrakt výsledku jako balíček ke čtení.">Načíst balíček karty</button>
          {onOpenVault && <button type="button" data-testid="open-in-vault" onClick={() => onOpenVault(node.id)}
            title="Schránka zadání tohoto sektoru nebo karty v levém menu Editoru.">Otevřít ve Schránce</button>}
        </div>
      </header>
      <div className="panel-body">
        {sector ? <>
          <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={busy || readOnly} onStored={setStoredSpec} refreshRevision={specRefreshRevision} />
          <SectorDecompose project={project} workspace={workspace} sectorId={node.id} sectorName={node.name} purpose={node.purpose} cards={childCount}
            spec={specForNode?.fields ?? null} specError={specForNode?.error ?? ""} />
          {openIdeasInSector > 0 && <IdeasSummary project={project} workspace={workspace} sectorId={node.id} sectorName={node.name} openIdeas={openIdeasInSector} />}
        </> : <p className="muted">Zadání, kroky plánu, běh, review a historie karty jsou v jednom detailu. Otevřete ho tlačítkem nahoře nebo dvojklikem na kartu.</p>}
      </div>
      <footer className="panel-foot">
        <button type="button" className="danger" disabled={readOnly || busy}
          title={readOnly ? "Main je pouze pro čtení. Přepněte do pracovního prostoru." : "Zobrazí dopad před smazáním"} onClick={onDelete}>
          {sector ? "Smazat sektor" : "Smazat uzel"}
        </button>
        <span className="muted">Hotovo dokládají kroky, brána review, merge a zápis do plánu, ne barva karty.</span>
      </footer>
    </div>
  );
}
