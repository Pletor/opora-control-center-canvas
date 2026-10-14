import { useState } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { productFingerprint, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import ArchitectureProductForm from "@/project/architecture-editor/domain-map/components/ArchitectureProductForm";
import DomainCard, { type DomainCardLive } from "./DomainCard";
import type { WorktreeNav } from "@/project/architecture-editor/live-status/components/WorktreeRow";
import { countsOf, domainLive, type WorkStatus } from "@/project/architecture-editor/live-status/logic/live-model";
import { loadNotice, staleNote, type LiveSlot } from "@/project/architecture-editor/live-status/logic/live-poll";
import { mainSessionsSummary } from "@/project/architecture-editor/live-status/logic/session-state";
import { webLoadNotice, webView, type WebLive } from "@/project/architecture-editor/live-status/logic/web-slots";
import type { ArchiveShelfState } from "@/project/architecture-editor/live-status/logic/worktree-archive";
import { domainChoices } from "../logic/domain-choices";
import SplitConfirm from "./SplitConfirm";
import UnassignedWorktrees from "./UnassignedWorktrees";
import ArchiveShelf from "./ArchiveShelf";
import "../styles/architecture-landing.css";

const LEGACY = "Původní sdílená struktura";
const GROUP_NOTE: Record<string, string> = { Produkce: "Aktivní prostředí", Vývoj: "Oddělený prostor pro změny a ověření" };
const toneOf = (name: string) => (name === "Produkce" ? "prod" : name === "Vývoj" ? "dev" : "legacy");
const NO_WORK = { counts: countsOf([]), worktrees: [] };

/** Živý stav pro přehled (data drží ArchitectureEditor): web po doménách, stav práce, hlavní relace a akce nahoru. */
export type LandingLive = {
  web: WebLive; work: LiveSlot<WorkStatus>; worktreeLive: boolean; nav: WorktreeNav;
  onStartMainSession: () => void; onCreateWorktree: (domainId: string) => void;
  /** Přiřazení nepřiřazeného worktree k doméně a skladiště (jen ke čtení); obojí ukládá editor. */
  onAssign: (worktreeId: string, domainId: string) => Promise<void>;
  shelf: ArchiveShelfState; onLoadShelf: () => void;
};
const newDomain = (): ProductDraft => ({ parentId: null, name: "", purpose: "", site: { kind: "application", environments: [{ name: "Produkce", host: "" }] } });

/** Step 1: pick an environment and a domain; Production and Development rows, one card per domain. */
/** `lockReason` = proč jsou úpravy domén zakázané (věta stojí v `DomainLockNote` pod hlavičkou editoru, tady jde do `title`). */
export default function ArchitectureLanding({ graph, disabled, lockReason = "", live, onOpen, onSave, onSplit }: {
  graph: Graph; disabled: boolean; lockReason?: string; live?: LandingLive; onOpen: (id: string) => void;
  onSave: (draft: ProductDraft) => Promise<void>; onSplit: (id: string, host: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [split, setSplit] = useState<{ id: string; host: string } | null>(null);
  const [error, setError] = useState("");
  const apps = graph.nodes.filter((node) => node.site?.kind === "application");
  const group = (node: CanvasNode) => node.site?.kind === "application" && node.site.environments.length === 1 ? node.site.environments[0].name : LEGACY;
  const groups = [...new Set(["Produkce", "Vývoj", ...apps.map(group)])];
  const edit = (node: CanvasNode) => node.site && setDraft({
    id: node.id, original: productFingerprint(node), parentId: node.parentId, name: node.name, purpose: node.purpose,
    site: node.site.kind === "application" && !node.site.environments.length ? { kind: "application", environments: [{ name: "Produkce", host: "" }] } : structuredClone(node.site),
  });
  const work = live?.worktreeLive ? live.work.data : null;
  const workStale = live?.worktreeLive ? staleNote(live.work) : "";
  const cardLive = (node: CanvasNode): DomainCardLive | undefined => live && {
    web: webView(live.web, node.id), worktrees: live.worktreeLive, work: work ? domainLive(work, node.id) ?? NO_WORK : null, workStale,
    nav: live.nav, onCreateWorktree: () => live.onCreateWorktree(node.id),
  };
  const notices = live ? [live.worktreeLive ? loadNotice(live.work, "Stav práce") : "", webLoadNotice(live.web)].filter(Boolean) : [];
  const choices = domainChoices(graph);
  const confirmSplit = () => { if (split) void onSplit(split.id, split.host).then(() => setSplit(null)).catch((cause) => setError(String(cause))); };
  return <main className="arch-landing" data-testid="architecture-domain-landing">
    <header className="arch-landing__head">
      <div>
        <h2 className="arch-landing__title">Mapy architektury</h2>
        <p className="arch-landing__lead">Vyber prostředí a doménu. Každá doména má vlastní mapu stránek a jejich editory.</p>
        {live?.worktreeLive && <p className="arch-landing__flow" data-testid="architecture-work-flow">Jak začít práci: <b className="arch-landing__flow-step">1) Nový worktree na doméně</b> → <b className="arch-landing__flow-step">2) Nová relace</b> → <b className="arch-landing__flow-step">3) karta</b></p>}
      </div>
      <div className="arch-landing__head-tools">
        {live?.worktreeLive && <p className="arch-landing__sessions" data-testid="architecture-main-sessions">
          <span>{mainSessionsSummary(work ? work.mainSessions : null)}</span>{workStale && <small className="arch-landing__stale"> · {workStale}</small>}
          <button type="button" className="arch-landing__quiet" title="Relace asistenta nad celým projektem (prostor main); práce na doméně začíná novým worktree" onClick={live.onStartMainSession}>Nová hlavní relace</button>
        </p>}
        <button type="button" disabled={disabled} title={disabled ? lockReason : "Založit novou doménu (jeden host)"} data-testid="architecture-add-domain" onClick={() => setDraft(newDomain())}>+ Doména</button>
      </div>
    </header>
    {notices.map((text) => <p key={text} className="arch-landing__alert" role="alert">{text}</p>)}
    {draft && <ArchitectureProductForm key={draft.id ?? "new"} initial={draft} disabled={disabled} onSave={onSave} onClose={() => setDraft(null)}/>}
    {groups.map((name) => {
      const items = apps.filter((node) => group(node) === name);
      return <section className="arch-landing__group" key={name}>
        <h3 className="arch-landing__group-title"><span className={"arch-landing__tag arch-landing__tag--" + toneOf(name)}>{name}</span>{GROUP_NOTE[name] && <span className="arch-landing__note">{GROUP_NOTE[name]}</span>}</h3>
        {name === LEGACY && <p className="arch-landing__note">Tyto starší aplikace mají více hostů nebo zatím žádný. Jejich uložené stránky zůstávají společné.</p>}
        <div className="arch-landing__grid">
          {items.map((node) => <DomainCard key={node.id} node={node} tone={toneOf(name)} disabled={disabled} live={cardLive(node)} onOpen={() => onOpen(node.id)} onEdit={() => edit(node)} onSplit={(host) => { setError(""); setSplit({ id: node.id, host }); }}/>)}
        </div>
        {!items.length && <p className="arch-landing__empty">Zatím žádná doména.</p>}
      </section>;
    })}
    {!!work?.unassigned.length && <UnassignedWorktrees worktrees={work.unassigned} choices={choices} stale={workStale} nav={live?.nav} onAssign={live?.onAssign}/>}
    {live?.worktreeLive && <ArchiveShelf shelf={live.shelf} choices={choices} onLoad={live.onLoadShelf}/>}
    {split && <SplitConfirm host={split.host} error={error} disabled={disabled} onConfirm={confirmSplit} onCancel={() => setSplit(null)}/>}
  </main>;
}
