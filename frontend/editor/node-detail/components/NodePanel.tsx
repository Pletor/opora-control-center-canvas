import { useEffect, useRef, useState, type ReactNode } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import DetailFold from "./DetailFold";
import ResultHistory from "@/editor/llm-control/editor-context/components/ResultHistory";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import NodeProcesses from "@/editor/node-detail/process/components/NodeProcesses";
import NodeTree from "@/editor/node-detail/tree/components/NodeTree";
import NodeTabs, { type NodeTab } from "@/editor/node-detail/components/NodeTabs";
import SyncBadge from "@/editor/node-detail/sync-badge/components/SyncBadge";
import type { BadgeView } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import NodeCardEditor from "@/editor/node-detail/card-fields/components/NodeCardEditor";
import FactRefsEditor from "@/editor/node-detail/card-fields/components/FactRefsEditor";
import DoneControl from "@/editor/node-detail/done/components/DoneControl";
import IdeasPanel, { IdeasCount } from "@/editor/node-detail/ideas/components/IdeasPanel";
import { openIdeas, type CardIdea, type IdeaStatus } from "@/editor/node-detail/ideas/logic/ideas-model";
import type { NodeDone } from "@/shared/desktop-state/logic/types";
import type { CanvasNode, Workspace } from "@/shared/types/logic/types";

export type { NodeTab };

/**
 * Jeden inspektor: Zadání · Vazby · Práce · Podněty. Sekundární editory se načtou při prvním rozbalení
 * a zůstanou připojené, aby sbalení nebo přepnutí záložky nesmazalo rozepsaný text.
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
  graphNodes,
  onPickTag,
  onSelectBlock,
  done,
  onDone,
  ideas,
  onIdeaStatus,
  onIdeaRemove,
  syncView,
  onCommitSpec,
  workflow,
  resultRevision,
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
  /** Podněty k dalšímu vývoji ze stavu Desktop v3; odškrtává a maže člověk, ukládá rodič. */
  ideas: CardIdea[];
  onIdeaStatus: (id: string, status: IdeaStatus) => void;
  onIdeaRemove: (id: string) => void;
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
  /** Verdikt Oracle pro tento uzel; hotová data z reportu, dílek je jen zobrazuje. */
  syncView?: BadgeView | null;
  /** Zapíše commit zadání v OporaHubu; bez něj brána 1:1 zůstane zavřená. */
  onCommitSpec?: () => void;
  workflow?: ReactNode;
  resultRevision: number;
}) {
  const [purpose, setPurpose] = useState(node.purpose);
  const [confirmed, setConfirmed] = useState(false);
  const [textRevision, setTextRevision] = useState(0);
  const storedPurpose = useRef(node.purpose);
  useEffect(() => {
    const previous = storedPurpose.current;
    storedPurpose.current = node.purpose;
    setPurpose((draft) => draft === previous ? node.purpose : draft);
  }, [node.purpose]);
  const purposeDirty = useRef(purpose !== node.purpose);
  purposeDirty.current = purpose !== node.purpose;
  useScopedSaveParticipant({ id: `node-purpose:${node.id}`, label: `Účel: ${node.name}`,
    dirty: purposeDirty.current, isDirty: () => purposeDirty.current,
    blocked: !confirmed ? "Nejprve potvrďte změnu podstaty v detailu uzlu." : readOnly ? "Karta je pouze ke čtení." : undefined,
    flush: () => confirmSavedChange(() => onSave({ ...node, purpose }), () => purposeDirty.current) });
  const assigned = workspaces.filter((w) => w.node_id === node.id);
  const kind = node.site?.kind === "application" ? "Aplikace" : node.site?.kind === "page" ? "Stránka" : node.kind === "sector" ? "Sektor" : "Uzel";
  return (
    <div className="node-panel">
      <header className="panel-head">
        <div className="eyebrow">{kind.toLocaleUpperCase("cs")} · DETAIL</div>
        <h2>{node.name}</h2>
        <details><summary>Identita a zdroj</summary><code className="identity">{node.id}</code>
        {node.sourceRef && (
          <p className={"source-badge " + (node.sourceRef.origin === "existing" ? "source-badge-existing" : "source-badge-planned")}>
            {node.sourceRef.origin === "existing" ? "Existující zdroj" : "Návrh zdroje"}: <code>{node.sourceRef.path || (node.sourceRef.origin === "planned" ? "cesta neurčena" : "/")}</code> ({node.sourceRef.kind === "directory" ? "složka" : "soubor"})
          </p>
        )}
        </details>
        <div className="action-row">
          <button type="button" className="primary" onClick={onEnter}>
            Otevřít vnitřní plátno
          </button>
          <button type="button" data-testid="agent-task-action" disabled={busy} onClick={onAgentTask} title="Načte uložené zadání a souvislosti pro předání agentovi.">
            Předat zadání
          </button>
        </div>
      </header>
      <NodeTabs tab={tab} onTab={onTab} badges={{ ideas: <IdeasCount count={openIdeas(ideas)} /> }} />
      <div className="panel-body">
        <section role="tabpanel" id="node-panel-links" aria-labelledby="node-tab-links" hidden={tab !== "links"}>
          <h3>Vazby a souvislosti</h3>
          <NodeLinksPanel project={project} workspace={workspace} node={node.id} revision={textRevision} readOnly={readOnly} onOpenNode={onOpenNode} />
          <DetailFold title="Bloky, porty a větvení">
            <NodeTree key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} nodeId={node.id} graphNodes={graphNodes} onPickTag={onPickTag} onSelectBlock={onSelectBlock} />
          </DetailFold>
        </section>
        <section role="tabpanel" id="node-panel-spec" aria-labelledby="node-tab-spec" hidden={tab !== "spec"}>
          <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={busy} />
          <DetailFold title="Účel komponenty">
          <p className="muted">Dlouhodobý smysl této části. Konkrétní práci určuje zadání výše.</p>
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
          </DetailFold>
          <DetailFold title="Popis a podklady">
            <NodeTextEditor key={JSON.stringify([project, workspace, node.id])} project={project} workspace={workspace} node={node.id} onSaved={() => setTextRevision((value) => value + 1)} />
          </DetailFold>
          {node.kind === "node" && <DetailFold title="Nastavení karty"><NodeCardEditor node={node} readOnly={readOnly} busy={busy} onSave={onSave} /></DetailFold>}
          {(node.kind === "node" || node.kind === "sector") && <DetailFold title="Fakta projektu"><FactRefsEditor key={`${project}:${workspace}:${node.id}`} node={node} project={project} workspace={workspace} disabled={readOnly || busy} onSave={onSave} /></DetailFold>}
        </section>
        <section role="tabpanel" id="node-panel-work" aria-labelledby="node-tab-work" hidden={tab !== "work"}>
          <DetailFold title="Výsledky a původní zadání"><ResultHistory project={project} workspace={workspace} nodeId={node.id} revision={resultRevision} /></DetailFold>
          <DetailFold title="Postup, kritéria a kroky">{workflow}</DetailFold>
          <DetailFold title="Ověření a uzavření">
            <SyncBadge view={syncView ?? null} />
            {onCommitSpec && !readOnly && <button type="button" className="sync-badge__commit" onClick={onCommitSpec}>Zacommitovat zadání</button>}
            <DoneControl done={done} readOnly={readOnly} busy={busy} onDone={onDone} />
          </DetailFold>
          <DetailFold title="Pracovní paměť a předávka">
              <AgentWorkspace
                key={project + ":" + workspace + ":" + node.id}
                project={project}
                workspace={workspace}
                nodeId={node.id}
                readOnly={readOnly || done.confirmed}
              />
          </DetailFold>
          <DetailFold title="Procesy"><NodeProcesses key={project + ":" + node.id} project={project} nodeId={node.id} readOnly={readOnly} /></DetailFold>
          <DetailFold title="Pracovní prostory">
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
          </DetailFold>
        </section>
        <section role="tabpanel" id="node-panel-ideas" aria-labelledby="node-tab-ideas" hidden={tab !== "ideas"}>
          <h3>Podněty k dalšímu vývoji</h3>
          <IdeasPanel ideas={ideas} readOnly={readOnly} busy={busy} onStatus={onIdeaStatus} onRemove={onIdeaRemove} />
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
