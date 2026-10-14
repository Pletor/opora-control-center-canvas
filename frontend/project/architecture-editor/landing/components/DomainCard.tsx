import type { CanvasNode } from "@/shared/types/logic/types";
import { DOMAIN_KIND_LABEL, domainKindOf } from "../logic/domain-kind";
import DomainKindIcon from "./DomainKindIcon";
import DomainWork from "./DomainWork";
import WebStatusBadge from "@/project/architecture-editor/live-status/components/WebStatusBadge";
import type { WorktreeNav } from "@/project/architecture-editor/live-status/components/WorktreeRow";
import type { LiveDomain } from "@/project/architecture-editor/live-status/logic/live-model";
import type { WebView } from "@/project/architecture-editor/live-status/logic/web-slots";

/** Živý stav domény pro kartu: web domény a (u projektů s worktree) práce na ní; `work = null` = ještě nenačteno. */
export type DomainCardLive = {
  web: WebView; worktrees: boolean; work: Pick<LiveDomain, "counts" | "worktrees"> | null; workStale: string;
  nav: WorktreeNav; onCreateWorktree: () => void;
};

/** One domain: icon of its kind, host, web badge, "kind · purpose", work on it, ID, link to its page map and a quiet Edit. */
export default function DomainCard({ node, tone, disabled, live, onOpen, onEdit, onSplit }: {
  node: CanvasNode; tone: "prod" | "dev" | "legacy"; disabled: boolean; live?: DomainCardLive;
  onOpen: () => void; onEdit: () => void; onSplit: (host: string) => void;
}) {
  const environments = node.site?.kind === "application" ? node.site.environments : [];
  const kind = domainKindOf(node);
  const shared = environments.length > 1;
  return <article className={"arch-landing__card arch-landing__card--" + tone} data-testid={"architecture-domain-" + node.id}>
    <DomainKindIcon kind={kind}/>
    <h3 className="arch-landing__host">{environments[0]?.host || node.name}</h3>
    {live && <WebStatusBadge host={live.web.host} stale={live.web.stale}/>}
    {live?.web.stale && <small className="arch-landing__stale">{live.web.stale}</small>}
    <p className="arch-landing__meta">{DOMAIN_KIND_LABEL[kind]} · {node.purpose || node.name}</p>
    {live?.worktrees && live.work && <DomainWork counts={live.work.counts} worktrees={live.work.worktrees} label={"Worktree domény " + (environments[0]?.host || node.name)}
      stale={live.workStale} nav={live.nav} onCreateWorktree={live.onCreateWorktree}/>}
    {shared && environments.map((env) => <div className="arch-landing__env" key={env.host}>
      <code>{env.host}</code>
      <button type="button" className="arch-landing__quiet" disabled={disabled} onClick={() => onSplit(env.host)}>Oddělit doménu</button>
    </div>)}
    <small className="arch-landing__id">ID: {node.id}</small>
    <div className="arch-landing__actions">
      <button type="button" className="arch-landing__open" data-testid={"architecture-open-domain-" + node.id} onClick={onOpen}>Otevřít mapu projektu</button>
      <button type="button" className="arch-landing__quiet" disabled={disabled} onClick={onEdit}>Upravit</button>
    </div>
  </article>;
}
