import { useState } from "react";
import type { PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { isObject } from "@/hub/oporahub-mirror/logic/hub-read";
import { REVIEW_ROOT, reviewQuery, riskLabels, type RiskLevel } from "@/hub/proposal-review/logic/proposal-review";
import ConflictDrawer from "@/hub/oporahub-conflicts/components/ConflictDrawer";

const parseRisk = (raw: unknown): RiskLevel | null => isObject(raw) && isObject(raw.risk) && typeof raw.risk.level === "string" ? raw.risk.level as RiskLevel : null;
const TONE: Record<string, string> = { standard: "ok", elevated: "warn", critical: "bad" };

/** Jeden čekající návrh: předmět, autor, základ a riziko z kontroly návrhu (`proposal-reviews`). */
function Pending({ project, workspace, item, acceptedHead }: { project: string; workspace: string; item: PlanChangeset; acceptedHead: string | null }) {
  const risk = useHubRead(`${REVIEW_ROOT}?${reviewQuery({ project, workspace }, { proposalKind: "spec", proposalId: item.id })}`, parseRisk);
  const stale = !!acceptedHead && item.parentRevision !== acceptedHead;
  const level = risk.data;
  return <li className="spec-tab__pending" data-oh-changeset={item.id} data-oh-parent={item.parentRevision} data-oh-stale={String(stale)} data-oh-risk={level ?? ""}>
    <b>{item.subject || "(bez předmětu)"}</b>
    <span className="spec-tab__muted">{item.by.name} · {item.createdAt.slice(0, 16).replace("T", " ")} · základ {item.parentRevision.slice(0, 8)}</span>
    <span className={`spec-tab__chip spec-tab__chip--${level ? TONE[level] ?? "gap" : "gap"}`}>{level ? `riziko ${riskLabels[level] ?? level}` : risk.busy ? "riziko…" : "◌ riziko neznámé"}</span>
    {stale && <span className="spec-tab__chip spec-tab__chip--warn">◷ starý základ → auto-rebase</span>}
  </li>;
}

/** Čekající návrhy karty s rizikem a odkaz na konflikty auto-rebase (otevře je přímo v detailu). */
export default function SpecPending({ project, workspace, items, acceptedHead, conflicts, onChanged }: {
  project: string; workspace: string; items: PlanChangeset[]; acceptedHead: string | null; conflicts: number; onChanged: () => void;
}) {
  const [showConflicts, setShowConflicts] = useState(false);
  const pending = items.filter(item => !item.accepted);
  return <section className="spec-tab__section" aria-label="Čekající návrhy zadání" data-oh-list="pending-changesets" data-oh-count={pending.length}>
    <h3 className="spec-tab__heading">Čekající návrhy <span className="spec-tab__muted">{pending.length}</span></h3>
    {pending.length ? <ul className="spec-tab__plain">{pending.map(item => <Pending key={item.id} project={project} workspace={workspace} item={item} acceptedHead={acceptedHead} />)}</ul>
      : <p className="spec-tab__muted">Žádný otevřený návrh zadání této karty.</p>}
    <p className="spec-tab__muted" data-oh-conflicts={conflicts}>
      {conflicts ? `◷ Auto-rebase hlásí ${conflicts} konflikt(ů) stejného pole. ` : "Auto-rebase bez konfliktů. "}
      <button type="button" className="spec-tab__link" onClick={() => setShowConflicts(value => !value)}>{showConflicts ? "Skrýt konflikty" : "Konflikty auto-rebase"}</button>
    </p>
    {showConflicts && <ConflictDrawer project={project} workspace={workspace} onResolved={onChanged} />}
  </section>;
}
