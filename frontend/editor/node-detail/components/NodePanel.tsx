import { useState } from "react";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import NodeProcesses from "@/editor/node-detail/process/components/NodeProcesses";
import NodeTree from "@/editor/node-detail/tree/components/NodeTree";
import NodeTabs, { type NodeTab } from "@/editor/node-detail/components/NodeTabs";
import SyncBadge from "@/editor/node-detail/sync-badge/components/SyncBadge";
import type { BadgeView } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import DoneControl from "@/editor/node-detail/done/components/DoneControl";
import NodeActivity from "@/live-run/node-activity/components/NodeActivity";
import type { NodeDone } from "@/shared/desktop-state/logic/types";
import type { CanvasNode, Workspace } from "@/shared/types/logic/types";

export type { NodeTab };

/**
 * Inspektor uzlu: hlavička s primárními akcemi, pět záložek (Obsah · Strom · Zadání · Proces · Práce)
 * a patička s destruktivní akcí. Záložky zůstávají připojené, aby rozepsaný text nezmizel.
 * Uzavření karty (`done`) drží dílek `done/DoneControl`; ukládá rodič (App).
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
  graphNodes,
  onPickTag,
  onSelectBlock,
  done,
  onDone,
  syncView,
  onCommitSpec,
}: {
  node: CanvasNode;
  project: string;
  workspace: string;
  readOnly: boolean;
  busy: boolean;
  workspaces: Workspace[];
  /** Uzavření karty ze stavu Desktop v3; potvrzuje člověk, agent smí jen navrhnout. */
  done: NodeDone;
  onDone: (patch: Partial<NodeDone>) => void;
  /** Uzly grafu jako cíle větví ve Stromu. */
  graphNodes: { id: string; name: string }[];
  /** Klik na štítek ve Stromu nastaví filtr plátna. */
  onPickTag?: (tag: string) => void;
  /** Klik na číslo bloku ve Stromu otevře jeho Editor v levé zásuvce. */
  onSelectBlock?: (blockId: string) => void;
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
  /** Verdikt Oracle pro tento uzel; hotová data z reportu, dílek je jen zobrazuje. */
  syncView?: BadgeView | null;
  /** Zapíše commit zadání v OporaHubu; bez něj brána 1:1 zůstane zavřená. */
  onCommitSpec?: () => void;
}) {
  const [purpose, setPurpose] = useState(node.purpose);
  const [confirmed, setConfirmed] = useState(false);
  const [textRevision, setTextRevision] = useState(0);
  const assigned = workspaces.filter((w) => w.node_id === node.id);
  const kind = node.kind === "sector" ? "Sektor" : "Uzel";
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
        <SyncBadge view={syncView ?? null} />
        {onCommitSpec && !readOnly && (
          <button type="button" className="sync-badge__commit" onClick={onCommitSpec}
            title="Zapíše revizi zadání do OporaHubu. Nic se tím nespouští.">
            Zacommitovat zadání
          </button>
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
      <NodeTabs tab={tab} onTab={onTab} />
      <div className="panel-body">
        <section role="tabpanel" id="node-panel-content" aria-labelledby="node-tab-content" hidden={tab !== "content"}>
          <NodeTextEditor key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} node={node.id} onSaved={() => setTextRevision((value) => value + 1)} />
          <h3>Souvislosti</h3>
          <NodeLinksPanel project={project} workspace={workspace} node={node.id} revision={textRevision} readOnly={readOnly} onOpenNode={onOpenNode} />
        </section>
        <section role="tabpanel" id="node-panel-tree" aria-labelledby="node-tab-tree" hidden={tab !== "tree"}>
          {tab === "tree" && <NodeTree key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} nodeId={node.id} graphNodes={graphNodes} onPickTag={onPickTag} onSelectBlock={onSelectBlock} />}
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
          {node.kind === "sector" && (
            <>
              <h3>Pracovní prostor agenta</h3>
              <AgentWorkspace
                key={project + ":" + workspace + ":" + node.id}
                project={project}
                workspace={workspace}
                nodeId={node.id}
                readOnly={readOnly || done.confirmed}
              />
            </>
          )}
        </section>
        <section role="tabpanel" id="node-panel-process" aria-labelledby="node-tab-process" hidden={tab !== "process"}>
          <h3>Uzavření karty</h3>
          <DoneControl done={done} readOnly={readOnly} busy={busy} onDone={onDone} />
          {tab === "process" && <NodeProcesses key={project + ":" + node.id} project={project} nodeId={node.id} readOnly={readOnly} />}
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
