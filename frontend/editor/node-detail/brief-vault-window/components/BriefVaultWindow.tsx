// Okno schránky zadání (modální pop-up s levým menu, návrh Claude Design „Main“): vlevo hledání a sekce
// Plán · Vývoj · Know-how · Historie s počty, vpravo jedna sekce. Esc i × zavírá (nativní <dialog>, pozadí
// je neaktivní); s rozepsaným polem se nejdřív zeptá, aby se text neztratil. Strom bere ze sdíleného zdroje schránky; plátno po vložení karet obnoví rodič (onPlanApplied).
import { useEffect, useMemo, useRef, useState } from "react";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { rootsOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import BriefVaultPanel from "@/editor/node-detail/brief-vault/components/BriefVaultPanel";
import { SECTIONS, filterTree, flatten, sectionCounts, type SectionId } from "../logic/vault-window-model";
import { planParent } from "../logic/vault-plan";
import VaultNav from "./VaultNav";
import OverviewSection from "./OverviewSection";
import MvpSection from "./MvpSection";
import ResearchSection from "./ResearchSection";
import QuestionsSection from "./QuestionsSection";
import FeedbackSection from "./FeedbackSection";
import HistorySection from "./HistorySection";
import FragmentActions from "./FragmentActions";
import { DecisionsSection, IdeasSection, MaterialsSection } from "./KnowHowSections";
import "../styles/brief-vault-window.css";

export type VaultWindowRequest = { scope: string; owner: string; focus?: string | null; section?: SectionId };
type GraphNode = { id: string; name: string; kind: string; parentId: string | null };

/** Esc (i nativní `cancel` dialogu) zavře okno přes rodiče; událost nepropadne do plátna pod oknem. */
export function closeOnEscape(event: { type: string; key?: string; preventDefault: () => void; stopPropagation: () => void }, onClose: () => void) {
  if (event.type !== "cancel" && event.key !== "Escape") return;
  event.preventDefault();
  event.stopPropagation();
  onClose();
}

type DraftField = { isConnected: boolean; value: string };
export const DRAFT_CONFIRM = "Rozepsaný text ve schránce není uložený a zavřením se ztratí. Zavřít přesto?";

/** Pole, do kterého člověk psal, je pořád v okně a není prázdné (odeslaný formulář zmizí nebo se vyprázdní). */
export function hasUnsavedDraft(fields: Iterable<DraftField>): boolean {
  for (const field of fields) if (field.isConnected && field.value.trim()) return true;
  return false;
}

/** Zavření okna: s rozepsaným polem až po potvrzení člověka. */
export function closeUnlessDraft(fields: Iterable<DraftField>, ask: (message: string) => boolean, onClose: () => void) {
  if (hasUnsavedDraft(fields) && !ask(DRAFT_CONFIRM)) return;
  onClose();
}

/** Psaní do textového pole okna (ne hledání, ne přepínače) si okno zapamatuje kvůli dotazu při zavření. */
function isDraftField(target: EventTarget | null): target is HTMLInputElement | HTMLTextAreaElement {
  if (target instanceof HTMLTextAreaElement) return true;
  return target instanceof HTMLInputElement && !["search", "checkbox", "radio", "button", "submit"].includes(target.type);
}

/** Uzly v rozsahu schránky: vlastník a všichni jeho potomci (plátno = všechny). */
function scopeIds(scope: string, nodes: GraphNode[]): Set<string> {
  if (!scope) return new Set(nodes.map((node) => node.id));
  const ids = new Set([scope]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const node of nodes) if (node.parentId && ids.has(node.parentId) && !ids.has(node.id)) { ids.add(node.id); grew = true; }
  }
  return ids;
}

export default function BriefVaultWindow({ project, workspace, request, state, nodes, digest, readOnly, onOpenNode, onClose, onPlanApplied, onStateChanged }: {
  project: string;
  workspace: string;
  request: VaultWindowRequest;
  state: DesktopState;
  nodes: GraphNode[];
  digest: string;
  readOnly: boolean;
  onOpenNode: (id: string) => void;
  onClose: () => void;
  onPlanApplied: () => void;
  /** Zápis změnil i stav plátna (Podnět dostal fragmentId): rodič ho načte znovu. */
  onStateChanged: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const [section, setSection] = useState<SectionId>(request.section ?? (request.focus ? "tree" : "overview"));
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const scope = useMemo(() => ({ project, workspace }), [project, workspace]);
  const vault = useBriefVault(scope, null);
  const drafts = useRef(new Set<HTMLInputElement | HTMLTextAreaElement>());
  const requestClose = () => closeUnlessDraft(drafts.current, (message) => window.confirm(message), onClose);
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current!;
    if (!element.open) element.showModal?.();
    close.current?.focus();
    return () => { element.close?.(); if (opener?.isConnected) opener.focus(); };
  }, []);
  const roots = useMemo(() => rootsOf(vault.tree?.roots ?? [], request.scope), [vault.tree, request.scope]);
  const ids = useMemo(() => new Set(flatten(roots).map((item) => item.node.id)), [roots]);
  const feedback = useMemo(() => (vault.tree?.feedback ?? []).filter((item) => ids.has(item.fragmentId)), [vault.tree, ids]);
  const inScope = useMemo(() => scopeIds(request.scope, nodes), [request.scope, nodes]);
  const nodeNames = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, node.name])), [nodes]);
  const ideas = useMemo(() => Object.entries(state.nodes).flatMap(([nodeId, node]) => (node.ideas ?? [])
    .filter((idea) => inScope.has(nodeId) || (idea.fragmentId && ids.has(idea.fragmentId))).map((idea) => ({ nodeId, idea }))), [state.nodes, inScope, ids]);
  const materials = useMemo(() => Object.entries(state.nodes).filter(([nodeId]) => inScope.has(nodeId))
    .flatMap(([nodeId, node]) => (node.materials ?? []).map((item) => ({ nodeId, item }))), [state.nodes, inScope]);
  const linkedDecisions = new Set(flatten(roots).flatMap((item) => item.node.decisions ?? []));
  const counts = sectionCounts(roots, { feedback: feedback.length, decisions: linkedDecisions.size, materials: materials.length, ideas: ideas.length });
  const title = SECTIONS.find((item) => item.id === section)?.title ?? "";
  const editable = !readOnly && !vault.tree?.readOnly;
  const parent = planParent(request.scope, nodes);
  const content = () => {
    if (vault.error && !vault.tree) return <p className="vault-window__error" role="alert">Schránku nelze načíst: {vault.error}</p>;
    if (!vault.tree) return <p className="vault-window__notice" role="status">Načítám schránku…</p>;
    if (vault.tree.readOnly) return <div className="vault-window__empty">Main je jen ke čtení. Schránka zadání žije v pracovním prostoru; přepněte do něj.</div>;
    if (!roots.length && section !== "history" && section !== "ideas" && section !== "decisions" && section !== "materials") {
      return (
        <div className="vault-window__empty" data-testid="vault-window-empty">
          <p><strong>Schránka {request.owner} je prázdná.</strong></p>
          <p>Sem se ukládá dlouhé zadání doslova a s historií verzí. Agent ho vloží a rozdělí na kapitoly (<code>/api/brief-vault</code>,
            recept ve skillu OPORA); pak tu běží výzkum, otázky, výběr MVP a vložení jako karty. Podněty a rozhodnutí karet vidíš i bez zadání.</p>
        </div>
      );
    }
    switch (section) {
      case "overview": return <OverviewSection roots={roots} feedback={feedback} onSection={setSection} />;
      case "tree": return (
        <BriefVaultPanel project={project} workspace={workspace} roots={filterTree(roots, query)} loading={false} readOnly={false}
          error={vault.error} scopeLabel={request.owner} nodeNames={nodeNames} onOpenNode={(id) => closeUnlessDraft(drafts.current, (message) => window.confirm(message), () => { onOpenNode(id); onClose(); })}
          initialSelected={request.focus ?? null} emptyHint={query ? "Hledání nenašlo žádnou kapitolu." : undefined}
          detailActions={editable ? (id) => <FragmentActions scope={scope} fragmentId={id} onSection={setSection} /> : undefined} />
      );
      case "mvp": return <MvpSection scope={scope} roots={roots} query={query} readOnly={!editable} digest={digest} parent={parent}
        onApplied={(_, message) => { setNotice(message); onPlanApplied(); }} />;
      case "research": return <ResearchSection scope={scope} roots={roots} query={query} feedback={feedback} readOnly={!editable} />;
      case "questions": return <QuestionsSection scope={scope} roots={roots} query={query} readOnly={!editable} />;
      case "feedback": return <FeedbackSection roots={roots} feedback={feedback} query={query} />;
      case "decisions": return <DecisionsSection scope={scope} roots={roots} decisions={state.decisions} inScope={inScope} nodeNames={nodeNames} query={query} readOnly={!editable} />;
      case "materials": return <MaterialsSection materials={materials} nodeNames={nodeNames} query={query} />;
      case "ideas": return <IdeasSection scope={scope} roots={roots} ideas={ideas} nodeNames={nodeNames} vaultScope={request.scope} query={query} readOnly={!editable} onLinked={onStateChanged} />;
      case "history": return <HistorySection scope={scope} vaultScope={request.scope} roots={roots} query={query} />;
    }
  };
  return (
    <dialog ref={dialog} className="vault-window" aria-modal="true" aria-label="Schránka zadání" data-testid="brief-vault-window"
      onCancel={(event) => closeOnEscape(event, requestClose)}
      onKeyDown={(event) => closeOnEscape(event, requestClose)}
      onInput={(event) => { if (isDraftField(event.target)) drafts.current.add(event.target); }}>
      <div className="vault-window__frame">
        <VaultNav section={section} counts={counts} query={query} owner={request.owner} onSection={setSection} onQuery={setQuery} />
        <main className="vault-window__main">
          <header className="vault-window__head">
            <div>
              <div className="vault-window__crumb">Schránka zadání · {request.owner}</div>
              <h2 className="vault-window__title">{title}</h2>
            </div>
            <button type="button" ref={close} className="vault-window__close" aria-label="Zavřít schránku" onClick={requestClose}>×</button>
          </header>
          {notice && <p className="vault-window__notice" role="status">{notice}</p>}
          {vault.error && vault.tree && <p className="vault-window__notice" role="status">Obnovení selhalo, ukazuji poslední načtený stav.</p>}
          {content()}
        </main>
      </div>
    </dialog>
  );
}
