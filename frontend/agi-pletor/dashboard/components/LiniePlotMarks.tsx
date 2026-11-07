import type { CSSProperties } from "react";
import type { BoardLayout, LaidCommit } from "../logic/linie-board";
import type { LayerState } from "../logic/linie-prefs";
import { commitTip, type Tip } from "../logic/linie-tip";

type Props = {
  layout: BoardLayout; selected: string; layers: LayerState;
  onPickCommit: (ticketId: string, sha: string) => void; onTip: (tip: Tip | null) => void;
};

const visible = (layout: BoardLayout, layers: LayerState, selected: string) => layout.commits.filter((commit) => layers.commits || commit.ticketId === selected);

/**
 * Značky nad čárami řádků (SVG část): čára práce od kuličky k poslednímu commitu, pruhy worktree pod osou s tečkovanou
 * odbočkou, návratem a tečkou „vrácen“, svislé značky tagů a nasazení, kostky commitů (opuštěná kostka červeně s ✕
 * a odbočkou, do cíle nejde). Najetí na kostku ukáže tip, klik otevře detail commitu. Commity a worktree jsou vrstvy;
 * pro vybranou kuličku se ukážou vždy.
 */
export function PlotMarksSvg({ layout, selected, layers, onPickCommit, onTip }: Props) {
  const stub = (c: LaidCommit) => `M${c.x} ${c.y - 5} L${c.x + 22} ${c.y - 24}`;
  return (
    <>
      {layout.works.map((work) => (
        <line key={work.ticketId} className={`pletor-dashboard__linie-work${work.wip ? " pletor-dashboard__linie-work--wip" : ""}`} x1={work.x1} y1={work.y} x2={work.x2} y2={work.y} stroke={work.color} />
      ))}
      {layout.lanes.map((lane, index) => (
        <g key={`${lane.rowId}-${index}`} stroke={lane.color}>
          <path className="pletor-dashboard__linie-lane-turn" d={lane.dIn} />
          <line className={`pletor-dashboard__linie-lane${lane.state === "pracuje" ? " pletor-dashboard__linie-lane--wip" : ""}`} x1={lane.x1} y1={lane.y} x2={lane.x2} y2={lane.y} />
          {lane.dOut && <path className="pletor-dashboard__linie-lane-turn" d={lane.dOut} />}
          {lane.back && <circle cx={lane.back.x} cy={lane.back.y} r={3.5} fill={lane.color} stroke="none"><title>{`worktree ${lane.agent} vrácen`}</title></circle>}
        </g>
      ))}
      {layers.tags && layout.tags.map((tag) => <line key={`${tag.kind}-${tag.text}-${tag.x}`} className="pletor-dashboard__linie-tagmark" x1={tag.x} y1={tag.y - 16} x2={tag.x} y2={tag.y + 16} />)}
      {visible(layout, layers, selected).map((commit) => (
        <g key={`${commit.ticketId}-${commit.ref}`} className={`pletor-dashboard__linie-cubeset${commit.abandoned ? " pletor-dashboard__linie-cubeset--dead" : ""}`} style={{ "--c": commit.color } as CSSProperties}
          role="button" tabIndex={0} aria-label={`Detail commitu ${commit.ref}`}
          onClick={() => onPickCommit(commit.ticketId, commit.sha)} onKeyDown={(event) => { if (event.key === "Enter") onPickCommit(commit.ticketId, commit.sha); }}
          onMouseEnter={() => onTip(commitTip(commit))} onMouseLeave={() => onTip(null)} onFocus={() => onTip(commitTip(commit))} onBlur={() => onTip(null)}>
          {commit.abandoned && <path className="pletor-dashboard__linie-cube-stub" d={stub(commit)} />}
          <rect className="pletor-dashboard__linie-cube" x={commit.x - 3} y={commit.y - 5} width={6} height={10} rx={1} />
        </g>
      ))}
    </>
  );
}

/** HTML část značek: jména pruhů u jejich začátku, štítky tagů a nasazení pod značkou, ✕ u opuštěného commitu, sha pod
 * kostkou při mřížce ≤ 15 min, pilulky PR na spojnici. */
export function PlotMarksHtml({ layout, selected, layers }: Pick<Props, "layout" | "selected" | "layers">) {
  const mine = (ticketId: string) => ticketId === selected;
  const commits = visible(layout, layers, selected);
  const showSha = layout.k * 15 * 60000 >= 84; // stejný práh jako značky osy: mřížka po 5–15 min
  return (
    <>
      {layout.lanes.map((lane, index) => (
        <span key={`lane-${lane.rowId}-${index}`} className="pletor-dashboard__linie-lane-label" style={{ left: lane.x1, top: lane.y }}>⌂ {lane.agent} · {lane.state}</span>
      ))}
      {layers.tags && layout.tags.map((tag) => (
        <span key={`${tag.kind}-${tag.text}-${tag.x}`} className={`pletor-dashboard__linie-taglabel pletor-dashboard__linie-taglabel--${tag.kind}`} style={{ left: tag.x, top: tag.y + 16 }} title={tag.title}>{tag.text}</span>
      ))}
      {commits.filter((c) => c.abandoned).map((c) => <span key={`x-${c.ticketId}-${c.ref}`} className="pletor-dashboard__linie-cube-x" style={{ left: c.x + 28, top: c.y - 27 }}>✕</span>)}
      {showSha && commits.map((c) => <span key={`sha-${c.ticketId}-${c.ref}`} className="pletor-dashboard__linie-cube-sha" style={{ left: c.x, top: c.y + 7 }}>{c.ref}</span>)}
      {layers.prs && layout.links.filter((link) => link.pr && (link.kind === "merged" || layers.plans || mine(link.ticketId))).map((link) => (
        <span key={`pr-${link.ticketId}-${link.kind}-${link.toId}`} className={`pletor-dashboard__linie-pr pletor-dashboard__linie-pr--${link.pr!.unverified ? "unverified" : link.pr!.state}`}
          style={{ left: link.pr!.at.x, top: link.pr!.at.y + (link.kind === "merged" ? 16 : 12) }} title={link.pr!.unverified ? "poslední známý stav, GitHub nepotvrdil" : "potvrzeno GitHubem"}>{link.pr!.text}</span>
      ))}
    </>
  );
}
