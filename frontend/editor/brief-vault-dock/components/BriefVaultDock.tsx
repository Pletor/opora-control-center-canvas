// Schránka v levém menu Editoru (docs/navrh-schranka-zadani.md, „Dvě stopy a levé menu“): v širokém panelu
// vedle lišty nahoře přepínač stop CX/UX/UI · Backend + DB · Nezařazené s počty, pod ním vnitřní menu
// (Plán · Vývoj · Know-how · Historie) a jedna sekce naplno. Všechno se počítá nad vybranou stopou. Strom bere
// ze sdíleného zdroje schránky; rozsah, fokus a obnovu plátna po vložení karet drží rodič (App). Rozepsaný
// text hlásí nahoru (`onDirty`), aby ho rodič při zavření panelu nezahodil (nechá Schránku skrytou).
import { useEffect, useMemo, useRef, useState } from "react";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { indexVault, rootsOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import BriefVaultPanel from "@/editor/node-detail/brief-vault/components/BriefVaultPanel";
import { SECTIONS, filterTree, flatten, scopeIds, sectionCounts, type SectionId } from "../logic/vault-dock-model";
import { filterByTrack, pickTrack, trackCounts, trackLabel, viewOf } from "../logic/vault-tracks";
import { useVaultTrack } from "../logic/use-vault-track";
import { hasUnsavedDraft, isDraftField, pruneDrafts } from "../logic/vault-drafts";
import { createPoller } from "@/shared/hooks/logic/poller";
import VaultNav from "./VaultNav";
import TrackSwitch from "./TrackSwitch";
import RootCreateForm from "./RootCreateForm";
import TrackReassign from "./TrackReassign";
import OverviewSection from "./OverviewSection";
import MvpSection from "./MvpSection";
import ResearchSection from "./ResearchSection";
import QuestionsSection from "./QuestionsSection";
import FeedbackSection from "./FeedbackSection";
import HistorySection from "./HistorySection";
import FragmentActions from "./FragmentActions";
import { DecisionsSection, IdeasSection, MaterialsSection } from "./KnowHowSections";
import "../styles/brief-vault-dock.css";

type GraphNode = { id: string; name: string; kind: string; parentId: string | null };
/** Požadavek „otevři Schránku na fragmentu“ (čip Ze schránky, Podnět); `nonce` odliší opakovaný klik. */
export type VaultFocus = { id: string; nonce: number };

export default function BriefVaultDock({ project, workspace, scope: vaultScope, owner, focus, state, nodes, digest, readOnly, onOpenNode, onPlanApplied, onStateChanged, onDirty }: {
  project: string;
  workspace: string;
  /** `""` = plátno, jinak id sektoru nebo karty s vlastní schránkou. */
  scope: string;
  owner: string;
  focus: VaultFocus | null;
  state: DesktopState;
  nodes: GraphNode[];
  digest: string;
  readOnly: boolean;
  onOpenNode: (id: string) => void;
  onPlanApplied: () => void;
  /** Zápis změnil i stav plátna (Podnět dostal fragmentId): rodič ho načte znovu. */
  onStateChanged: () => void;
  /** Ve Schránce je (není) neodeslaný rozepsaný text. */
  onDirty?: (dirty: boolean) => void;
}) {
  const drafts = useRef(new Set<HTMLInputElement | HTMLTextAreaElement>());
  const [dirty, setDirty] = useState(false);
  const recheck = () => { pruneDrafts(drafts.current); setDirty(hasUnsavedDraft(drafts.current)); };
  const report = useRef(onDirty);
  report.current = onDirty;
  useEffect(() => { report.current?.(dirty); }, [dirty]);
  useEffect(() => () => report.current?.(false), []);
  // Odeslaný formulář se vyprázdní až po odpovědi serveru: dokud je text rozepsaný, kontroluje se znovu
  // (sdílený poller, jen místní kontrola polí, žádná síť).
  const recheckRef = useRef(recheck);
  recheckRef.current = recheck;
  useEffect(() => {
    if (!dirty) return;
    const poller = createPoller({ run: async () => recheckRef.current(), intervalMs: 800, immediate: false });
    poller.start(false);
    return () => poller.stop();
  }, [dirty]);
  const [section, setSection] = useState<SectionId>(focus ? "tree" : "overview");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [stored, setTrack] = useVaultTrack();
  const scope = useMemo(() => ({ project, workspace }), [project, workspace]);
  const vault = useBriefVault(scope, null);
  const all = useMemo(() => rootsOf(vault.tree?.roots ?? [], vaultScope), [vault.tree, vaultScope]);
  const index = useMemo(() => indexVault(all), [all]);
  const counts = useMemo(() => trackCounts(all), [all]);
  const track = pickTrack(stored, counts);
  // Fokus z karty: sekce Zadání a stopa fragmentu, jednou na každý požadavek (až je strom načtený).
  const focused = useRef<number | null>(null);
  useEffect(() => {
    if (!focus || focused.current === focus.nonce) return;
    const node = index.get(focus.id);
    if (!node && !vault.tree) return;
    focused.current = focus.nonce;
    setSection("tree");
    if (node) setTrack(viewOf(node));
  }, [focus, index, vault.tree, setTrack]);
  const roots = useMemo(() => filterByTrack(all, track), [all, track]);
  const ids = useMemo(() => new Set(flatten(roots).map((item) => item.node.id)), [roots]);
  const feedback = useMemo(() => (vault.tree?.feedback ?? []).filter((item) => ids.has(item.fragmentId)), [vault.tree, ids]);
  const inScope = useMemo(() => scopeIds(vaultScope, nodes), [vaultScope, nodes]);
  const nodeNames = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, node.name])), [nodes]);
  const ideas = useMemo(() => Object.entries(state.nodes).flatMap(([nodeId, node]) => (node.ideas ?? [])
    .filter((idea) => inScope.has(nodeId) || (idea.fragmentId && ids.has(idea.fragmentId))).map((idea) => ({ nodeId, idea }))), [state.nodes, inScope, ids]);
  const materials = useMemo(() => Object.entries(state.nodes).filter(([nodeId]) => inScope.has(nodeId))
    .flatMap(([nodeId, node]) => (node.materials ?? []).map((item) => ({ nodeId, item }))), [state.nodes, inScope]);
  const linkedDecisions = new Set(flatten(roots).flatMap((item) => item.node.decisions ?? []));
  const sections = sectionCounts(roots, { feedback: feedback.length, decisions: linkedDecisions.size, materials: materials.length, ideas: ideas.length });
  const title = SECTIONS.find((item) => item.id === section)?.title ?? "";
  const editable = !readOnly && !vault.tree?.readOnly;
  const create = editable ? <RootCreateForm scope={scope} vaultScope={vaultScope} track={track} onCreated={setTrack} /> : null;
  const content = () => {
    if (vault.error && !vault.tree) return <p className="vault-dock__error" role="alert">Schránku nelze načíst: {vault.error}</p>;
    if (!vault.tree) return <p className="vault-dock__notice" role="status">Načítám schránku…</p>;
    if (vault.tree.readOnly) return <div className="vault-dock__empty">Main je jen ke čtení. Schránka zadání žije v pracovním prostoru; přepněte do něj.</div>;
    if (!roots.length && section !== "history" && section !== "ideas" && section !== "decisions" && section !== "materials") {
      return (
        <div className="vault-dock__empty" data-testid="vault-dock-empty">
          <p><strong>{all.length ? `Ve stopě ${trackLabel(track)} schránka ${owner} zatím nic nemá.` : `Schránka ${owner} je prázdná.`}</strong></p>
          <p>Sem se ukládá dlouhé zadání doslova a s historií verzí. Agent nebo člověk ho vloží jako kořen se stopou a rozdělí na kapitoly
            (<code>/api/brief-vault</code>, recept ve skillu OPORA); pak tu běží výzkum, otázky, výběr MVP a vložení jako karty.</p>
          {create}
        </div>
      );
    }
    switch (section) {
      case "overview": return <OverviewSection roots={roots} feedback={feedback} onSection={setSection} />;
      case "tree": return (
        <>
          {create}
          <BriefVaultPanel key={focus?.nonce ?? 0} project={project} workspace={workspace} roots={filterTree(roots, query)} loading={false} readOnly={false}
            error={vault.error} scopeLabel={owner} nodeNames={nodeNames} onOpenNode={onOpenNode}
            initialSelected={focus?.id ?? null} emptyHint={query ? "Hledání nenašlo žádnou kapitolu." : undefined}
            detailActions={(id) => (
              <>
                <TrackReassign scope={scope} fragment={index.get(id)} readOnly={!editable} onMoved={setTrack} />
                {editable && <FragmentActions scope={scope} fragmentId={id} onSection={setSection} />}
              </>
            )} />
        </>
      );
      case "mvp": return <MvpSection key={track} scope={scope} roots={roots} query={query} readOnly={!editable} digest={digest}
        onApplied={(_, message) => { setNotice(message); onPlanApplied(); }} />;
      case "research": return <ResearchSection scope={scope} roots={roots} query={query} feedback={feedback} readOnly={!editable} />;
      case "questions": return <QuestionsSection scope={scope} roots={roots} query={query} readOnly={!editable} />;
      case "feedback": return <FeedbackSection roots={roots} feedback={feedback} query={query} />;
      case "decisions": return <DecisionsSection scope={scope} roots={roots} decisions={state.decisions} inScope={inScope} nodeNames={nodeNames} query={query} readOnly={!editable} />;
      case "materials": return <MaterialsSection materials={materials} nodeNames={nodeNames} query={query} />;
      case "ideas": return <IdeasSection scope={scope} roots={roots} ideas={ideas} nodeNames={nodeNames} vaultScope={vaultScope} track={track} query={query} readOnly={!editable} onLinked={onStateChanged} />;
      case "history": return <HistorySection scope={scope} vaultScope={vaultScope} roots={roots} query={query} />;
    }
  };
  return (
    <div className="vault-dock" data-testid="brief-vault-dock" data-dirty={dirty || undefined}
      onInput={(event) => { if (isDraftField(event.target)) { drafts.current.add(event.target as HTMLInputElement); recheck(); } }}>
      <TrackSwitch track={track} counts={counts} onTrack={setTrack} />
      <div className="vault-dock__frame">
        <VaultNav section={section} counts={sections} query={query} owner={owner} onSection={setSection} onQuery={setQuery} />
        <main className="vault-dock__main">
          <header className="vault-dock__head">
            <div className="vault-dock__crumb">Schránka zadání · {owner} · {trackLabel(track)}</div>
            <h2 className="vault-dock__title">{title}</h2>
          </header>
          {notice && <p className="vault-dock__notice" role="status">{notice}</p>}
          {vault.error && vault.tree && <p className="vault-dock__notice" role="status">Obnovení selhalo, ukazuji poslední načtený stav.</p>}
          {content()}
        </main>
      </div>
    </div>
  );
}
