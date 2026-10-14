import { useEffect, useMemo, useRef, useState } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import DetailFold from "./DetailFold";
import ResultHistory from "@/editor/llm-control/editor-context/components/ResultHistory";
import NodeSpecEditor from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import SectorDecompose from "@/editor/sector-detail/components/SectorDecompose";
import IdeasSummary from "@/editor/sector-detail/components/IdeasSummary";
import CardHandoff from "@/editor/node-detail/handoff/components/CardHandoff";
import NodeTextEditor from "@/editor/node-detail/content/components/NodeTextEditor";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import NodeLinksPanel from "@/editor/node-detail/links/components/NodeLinksPanel";
import NodeTree from "@/editor/node-detail/tree/components/NodeTree";
import NodeTabs, { type NodeTab } from "@/editor/node-detail/components/NodeTabs";
import SyncBadge from "@/editor/node-detail/sync-badge/components/SyncBadge";
import type { BadgeView } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import NodeCardEditor from "@/editor/node-detail/card-fields/components/NodeCardEditor";
import DoneControl from "@/editor/node-detail/done/components/DoneControl";
import IdeasPanel, { IdeasCount } from "@/editor/node-detail/ideas/components/IdeasPanel";
import { openIdeas, type CardIdea, type IdeaStatus } from "@/editor/node-detail/ideas/logic/ideas-model";
import BriefChips from "@/editor/node-detail/brief-vault/components/BriefChips";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { changedSinceInsert, hasOwnVault, indexVault, scopeOfFragment, type FragmentRef } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import RoundsPanel, { OpenRoundOffer, RoundSwitch } from "@/editor/node-detail/rounds/components/RoundsPanel";
import { roundNumber, roundOffer, type CardRound } from "@/editor/node-detail/rounds/logic/rounds-model";
import type { NodeDone } from "@/shared/desktop-state/logic/types";
import type { CanvasNode, Workspace } from "@/shared/types/logic/types";

export type { NodeTab };

/**
 * Jeden inspektor: Zadání · Vazby · Práce · Podněty · Historie kol · Schránka (sektor, nebo karta s vlastní schránkou). Sekundární editory se načtou při prvním rozbalení
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
  fragmentRefs,
  onIdeaStatus,
  onIdeaRemove,
  syncView,
  onCommitSpec,
  resultRevision,
  onOpenVault,
  round,
  onOpenRound,
  childCount = 0,
  stageHint = "",
  openIdeasInSector = 0,
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
  /** Fragmenty schránky zadání, ze kterých karta vznikla (stav uzlu `fragmentRefs`). */
  fragmentRefs?: FragmentRef[];
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
  resultRevision: number;
  /** Otevře Schránku v levém menu (rozsah = vlastník kořene, volitelně rovnou na fragmentu a v jeho disciplíně). */
  onOpenVault?: (scope: string, focus?: string) => void;
  /** Aktuální kolo karty ze stavu Desktop v3 (chybí = kolo 1). */
  round?: CardRound;
  /** Člověk otevře uzavřenou kartu jako nové kolo; zapisuje rodič (App) přes POST /api/desktop-v3/card-round. */
  onOpenRound?: (reason: string) => Promise<void>;
  /** Počet karet (`kind: "node"`) přímo v sektoru; spočítá rodič z grafu, čte ho jen rozklad sektoru. */
  childCount?: number;
  /** Věta o etapě pipeline na řadě pro předání agentovi (`handoffStageHint`); spočítá rodič ze stavu karty. */
  stageHint?: string;
  /** Otevřené podněty v kartách sektoru; spočítá rodič, > 0 ukáže „Shrnout podněty“. */
  openIdeasInSector?: number;
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
  const vault = useBriefVault({ project, workspace }, resultRevision);
  const vaultRoots = vault.tree?.roots ?? [];
  const vaultIndex = useMemo(() => indexVault(vaultRoots), [vaultRoots]);
  const showVault = node.kind === "sector" || hasOwnVault(vaultRoots, node.id);
  const fragmentTitles = useMemo(() => Object.fromEntries([...vaultIndex].map(([id, item]) => [id, item.title])), [vaultIndex]);
  const openFragment = (fragmentId: string) => {
    const scope = scopeOfFragment(vaultIndex, fragmentId);
    if (scope != null) onOpenVault?.(scope, fragmentId);
  };
  const currentRound = roundNumber(round);
  const [selectedRound, setSelectedRound] = useState(currentRound);
  useEffect(() => setSelectedRound(currentRound), [currentRound, node.id]);
  const briefChanged = changedSinceInsert(fragmentRefs, vaultIndex);
  const offer = onOpenRound ? roundOffer(done.confirmed, readOnly, briefChanged) : null;
  const pickRound = (value: number) => {
    setSelectedRound(value);
    onTab(value === currentRound ? "work" : "rounds");
  };
  const assigned = workspaces.filter((w) => w.node_id === node.id);
  const kind = node.site?.kind === "application" ? "Aplikace" : node.site?.kind === "page" ? "Stránka" : node.kind === "sector" ? "Sektor" : "Uzel";
  return (
    <div className="node-panel">
      <header className="panel-head">
        <div className="eyebrow">{kind.toLocaleUpperCase("cs")} · DETAIL</div>
        <h2>{node.name}</h2>
        <RoundSwitch current={currentRound} closed={done.confirmed} selected={tab === "rounds" ? selectedRound : currentRound} onSelect={pickRound} />
        {offer === "prominent" && onOpenRound && (
          <OpenRoundOffer current={currentRound} closed={done.confirmed} readOnly={readOnly} busy={busy} briefChanged={briefChanged} onOpenRound={onOpenRound} />
        )}
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
          {showVault && onOpenVault && (
            <button type="button" data-testid="open-in-vault" onClick={() => onOpenVault(node.id)}
              title="Schránka zadání tohoto sektoru nebo karty v levém menu Editoru.">
              Otevřít ve Schránce
            </button>
          )}
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
          <BriefChips refs={fragmentRefs} index={vaultIndex} onOpen={onOpenVault ? openFragment : undefined} />
          <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={busy} />
          {node.kind === "sector" && (
            <SectorDecompose project={project} workspace={workspace} sectorId={node.id} sectorName={node.name} purpose={node.purpose} cards={childCount} />
          )}
          {node.kind === "sector" && openIdeasInSector > 0 && (
            <IdeasSummary project={project} workspace={workspace} sectorId={node.id} sectorName={node.name} openIdeas={openIdeasInSector} />
          )}
          {node.kind === "node" && (
            <CardHandoff project={project} workspace={workspace} nodeId={node.id} name={node.name} stageHint={stageHint} />
          )}
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
        </section>
        <section role="tabpanel" id="node-panel-work" aria-labelledby="node-tab-work" hidden={tab !== "work"}>
          <DetailFold title="Výsledky a původní zadání"><ResultHistory project={project} workspace={workspace} nodeId={node.id} revision={resultRevision} /></DetailFold>
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
          <IdeasPanel ideas={ideas} readOnly={readOnly} busy={busy} onStatus={onIdeaStatus} onRemove={onIdeaRemove}
            fragmentTitles={fragmentTitles} onOpenFragment={onOpenVault ? openFragment : undefined} />
        </section>
        <section role="tabpanel" id="node-panel-rounds" aria-labelledby="node-tab-rounds" hidden={tab !== "rounds"}>
          <h3>Historie kol</h3>
          {tab === "rounds" && (
            <RoundsPanel project={project} workspace={workspace} nodeId={node.id} current={currentRound} closed={done.confirmed}
              readOnly={readOnly} busy={busy} briefChanged={briefChanged} revision={resultRevision}
              selected={selectedRound} onSelect={pickRound} onOpenRound={offer === "prominent" ? undefined : onOpenRound} />
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
