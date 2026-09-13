import { useState, type KeyboardEvent } from "react";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import NodeActivity from "@/live-run/node-activity/components/NodeActivity";
import type { CanvasNode, Workspace } from "@/shared/types/logic/types";

export type NodeTab = "content" | "spec" | "work";
const TABS: { key: NodeTab; label: string }[] = [
  { key: "content", label: "Obsah" },
  { key: "spec", label: "Zadání" },
  { key: "work", label: "Práce" },
];

/**
 * Inspektor uzlu: hlavička s primárními akcemi, tři karty (Obsah · Zadání · Práce)
 * a patička s destruktivní akcí. Karty zůstávají připojené, aby rozepsaný text nezmizel.
 */
export default function NodePanel({
  node,
  project,
  workspace,
  readOnly,
  busy,
  workspaces,
  tab,
  onTab,
  onEnter,
  onSave,
  onWorkspace,
  onDelete,
  onOpenNode,
  onAgentTask,
  onOpenRun,
  onLiveRun,
}: {
  node: CanvasNode;
  project: string;
  workspace: string;
  readOnly: boolean;
  busy: boolean;
  workspaces: Workspace[];
  tab: NodeTab;
  onTab: (tab: NodeTab) => void;
  onEnter: () => void;
  onSave: (n: CanvasNode) => void;
  onWorkspace: () => void;
  onDelete: () => void;
  /** Souvislost vede na tentýž uzel v plátně. */
  onOpenNode: (id: string) => void;
  /** Připraví scope úkolu pro panel agenta; žádný běh nespouští. */
  onAgentTask: () => void;
  /** Běh → detail zdroje v módu Běhy; jen čtení. */
  onOpenRun: (sourceId: string, runId: string) => void;
  /** Přepne na skutečné sessions tohoto uzlu; nic nespouští. */
  onLiveRun?: () => void;
}) {
  const [purpose, setPurpose] = useState(node.purpose);
  const [confirmed, setConfirmed] = useState(false);
  const [textRevision, setTextRevision] = useState(0);
  const assigned = workspaces.filter((w) => w.node_id === node.id);
  const kind = node.kind === "sector" ? "Sektor" : "Uzel";
  function navigateTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    switch (event.key) {
      case "ArrowRight": next = (index + 1) % TABS.length; break;
      case "ArrowLeft": next = (index + TABS.length - 1) % TABS.length; break;
      case "Home": next = 0; break;
      case "End": next = TABS.length - 1; break;
      default: return;
    }
    event.preventDefault();
    onTab(TABS[next].key);
    // Fokus zůstává v tomto tablistu, ne v jiném inspektoru či skrytém panelu.
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }
  return (
    <div className="node-panel">
      <header className="panel-head">
        <div className="eyebrow">{kind.toLocaleUpperCase("cs")} · DETAIL</div>
        <h2>{node.name}</h2>
        <code className="identity">{node.id}</code>
        {node.sourceRef && (
          <p className={"source-badge " + (node.sourceRef.origin === "existing" ? "source-badge-existing" : "source-badge-planned")}>
            {node.sourceRef.origin === "existing" ? "Existující zdroj" : "Návrh zdroje"}: <code>{node.sourceRef.path || (node.sourceRef.origin === "planned" ? "cesta neurčena" : "/")}</code> ({node.sourceRef.kind === "directory" ? "složka" : "soubor"})
          </p>
        )}
        <div className="action-row">
          <button type="button" className="primary" onClick={onEnter}>
            Otevřít vnitřní plátno
          </button>
          <button type="button" data-testid="agent-task-action" disabled={busy} onClick={onAgentTask} title="Vydá přesný scope pro panel agenta. Nic se nespouští.">
            Připravit úkol pro agenta
          </button>
          {onLiveRun && <button type="button" data-testid="node-live-run-action" onClick={onLiveRun}
            title="Sledovat skutečné sessions a aktivitu na tomto uzlu. Žádný běh se nespustí.">
            Sledovat v Live Run ↗
          </button>}
        </div>
      </header>
      <div className="panel-tabs" role="tablist" aria-label="Části uzlu">
        {TABS.map((item, index) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            id={"node-tab-" + item.key}
            aria-selected={tab === item.key}
            aria-controls={"node-panel-" + item.key}
            tabIndex={tab === item.key ? 0 : -1}
            onKeyDown={(event) => navigateTab(event, index)}
            onClick={() => onTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="panel-body">
        <section role="tabpanel" id="node-panel-content" aria-labelledby="node-tab-content" hidden={tab !== "content"}>
          <NodeTextEditor key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} node={node.id} onSaved={() => setTextRevision((value) => value + 1)} />
          <h3>Souvislosti</h3>
          <NodeLinksPanel project={project} workspace={workspace} node={node.id} revision={textRevision} readOnly={readOnly} onOpenNode={onOpenNode} />
        </section>
        <section role="tabpanel" id="node-panel-spec" aria-labelledby="node-tab-spec" hidden={tab !== "spec"}>
          <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={busy} />
          <h3>Podstata</h3>
          <label className="field">
            Proč tento uzel existuje
            <textarea
              aria-label="Podstata uzlu"
              rows={5}
              maxLength={12000}
              value={purpose}
              readOnly={readOnly}
              onChange={(e) => {
                setPurpose(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          {!readOnly && purpose !== node.purpose && (
            <>
              <label className="check">
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                Potvrzuji změnu podstaty.
              </label>
              <button type="button" disabled={busy || !confirmed} onClick={() => onSave({ ...node, purpose })}>
                Uložit podstatu
              </button>
            </>
          )}
        </section>
        <section role="tabpanel" id="node-panel-work" aria-labelledby="node-tab-work" hidden={tab !== "work"}>
          <h3>Pracovní prostory uzlu</h3>
          {assigned.length ? (
            assigned.map((w) => (
              <div className="assignment" key={w.id}>
                <strong>{w.actor}</strong>
                <code>{w.branch}</code>
                <p>Přiřazený vlastník, aktivita agenta není ověřena.</p>
              </div>
            ))
          ) : (
            <p className="muted">Žádný doložený pracovní prostor tohoto uzlu.</p>
          )}
          <button type="button" onClick={onWorkspace}>
            Připravit oddělený worktree
          </button>
          <h3>Aktivita agenta</h3>
          {tab === "work" && (
            <NodeActivity project={project} workspace={workspace} nodeId={node.id} isSector={node.kind === "sector"} onOpenRun={onOpenRun} />
          )}
        </section>
      </div>
      <footer className="panel-foot">
        <button
          type="button"
          className="danger"
          disabled={readOnly || busy}
          title={readOnly ? "Main je pouze pro čtení. Přepněte do pracovního prostoru." : "Zobrazí dopad před smazáním"}
          onClick={onDelete}
        >
          {node.kind === "sector" ? "Smazat sektor" : "Smazat uzel"}
        </button>
        <span className="muted">Hotovo dokládají testy, review a merge, ne barva karty.</span>
      </footer>
    </div>
  );
}
