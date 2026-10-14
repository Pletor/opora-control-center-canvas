import { useState } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { productFingerprint, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import ArchitectureProductForm from "@/project/architecture-editor/domain-map/components/ArchitectureProductForm";
import DomainCard, { type DomainCardLive } from "./DomainCard";
import WorktreeTree from "@/project/architecture-editor/live-status/components/WorktreeTree";
import { countsOf, domainLive, type WorkStatus } from "@/project/architecture-editor/live-status/logic/live-model";
import { mainSessionsSummary } from "@/project/architecture-editor/live-status/logic/session-state";
import { hostOf, type WebHost } from "@/project/architecture-editor/live-status/logic/web-status";
import SplitConfirm from "./SplitConfirm";
import "../styles/architecture-landing.css";

const LEGACY = "Původní sdílená struktura";
const GROUP_NOTE: Record<string, string> = { Produkce: "Aktivní prostředí", Vývoj: "Oddělený prostor pro změny a ověření" };
const toneOf = (name: string) => (name === "Produkce" ? "prod" : name === "Vývoj" ? "dev" : "legacy");
const NO_WORK = { counts: countsOf([]), worktrees: [] };

/** Živý stav pro přehled (data drží ArchitectureEditor): hosty webu, stav práce a hlavní relace. */
export type LandingLive = { hosts: WebHost[]; webStale: string; work: WorkStatus | null; workStale: string; worktreeLive: boolean; onStartMainSession: () => void };
const newDomain = (): ProductDraft => ({ parentId: null, name: "", purpose: "", site: { kind: "application", environments: [{ name: "Produkce", host: "" }] } });

/** Step 1: pick an environment and a domain; Production and Development rows, one card per domain. */
export default function ArchitectureLanding({ graph, disabled, live, onOpen, onSave, onSplit }: {
  graph: Graph; disabled: boolean; live?: LandingLive; onOpen: (id: string) => void;
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
  const cardLive = (node: CanvasNode): DomainCardLive | undefined => live && {
    host: hostOf(live.hosts, node.id), stale: live.webStale, worktrees: live.worktreeLive, work: live.work ? domainLive(live.work, node.id) ?? NO_WORK : null,
  };
  const work = live?.worktreeLive ? live.work : null;
  const confirmSplit = () => { if (split) void onSplit(split.id, split.host).then(() => setSplit(null)).catch((cause) => setError(String(cause))); };
  return <main className="arch-landing" data-testid="architecture-domain-landing">
    <header className="arch-landing__head">
      <div>
        <h2 className="arch-landing__title">Mapy architektury</h2>
        <p className="arch-landing__lead">Vyber prostředí a projekt. Každý projekt má vlastní mapu stránek a jejich editory.</p>
      </div>
      <div className="arch-landing__head-tools">
        {work && live && <p className="arch-landing__sessions" data-testid="architecture-main-sessions">
          <span>{mainSessionsSummary(work.mainSessions)}</span>{live.workStale && <small className="arch-landing__note"> · {live.workStale}</small>}
          <button type="button" className="arch-landing__quiet" onClick={live.onStartMainSession}>Nová hlavní relace</button>
        </p>}
        <button type="button" disabled={disabled} data-testid="architecture-add-domain" onClick={() => setDraft(newDomain())}>+ Doména</button>
      </div>
    </header>
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
    {!!work?.unassigned.length && <section className="arch-landing__group" data-testid="architecture-unassigned">
      <h3 className="arch-landing__group-title"><span className="arch-landing__tag arch-landing__tag--legacy">Nepřiřazené</span><span className="arch-landing__note">Worktree, které zatím nepatří žádné doméně.</span></h3>
      <WorktreeTree worktrees={work.unassigned} label="Nepřiřazené worktree" compact/>
    </section>}
    {split && <SplitConfirm host={split.host} error={error} disabled={disabled} onConfirm={confirmSplit} onCancel={() => setSplit(null)}/>}
  </main>;
}
