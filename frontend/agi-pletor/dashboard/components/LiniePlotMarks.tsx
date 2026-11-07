import type { CSSProperties } from "react";
import type { BoardLayout, LaidCommit } from "../logic/linie-board";
import type { LayerState } from "../logic/linie-prefs";

type Props = { layout: BoardLayout; selected: string; layers: LayerState; onPickCommit: (ticketId: string) => void };

/**
 * Značky nad čárami řádků (SVG část): čára práce od kuličky k poslednímu commitu, pruhy worktree pod osou s tečkovanou
 * odbočkou a návratem, svislé značky tagů a nasazení, kostky commitů (opuštěná kostka červeně s ✕ a odbočkou, do cíle
 * nejde). Commity a worktree jsou vrstvy; pro vybranou kuličku se ukážou vždy.
 */
export function PlotMarksSvg({ layout, selected, layers, onPickCommit }: Props) {
  const mine = (ticketId: string) => ticketId === selected;
  const commits = layout.commits.filter((commit) => layers.commits || mine(commit.ticketId));
  const stub = (c: LaidCommit) => `M${c.x} ${c.y - 5} L${c.x + 22} ${c.y - 24}`;
  return (
    <>
      {layout.works.map((work) => (
        <line key={work.ticketId} className={`pletor-dashboard__linie-work${work.wip ? " pletor-dashboard__linie-work--wip" : ""}`} x1={work.x1} y1={work.y} x2={work.x2} y2={work.y} stroke={work.color} />
      ))}
      {layout.lanes.map((lane, index) => {
        const row = layout.rows.find((r) => r.id === lane.rowId);
        const axis = row?.y ?? lane.y;
        return (
          <g key={`${lane.rowId}-${index}`} stroke={lane.color}>
            <path className="pletor-dashboard__linie-lane-turn" d={`M${lane.x1} ${axis} L${lane.x1 + 14} ${lane.y}`} />
            <line className={`pletor-dashboard__linie-lane${lane.state === "pracuje" ? " pletor-dashboard__linie-lane--wip" : ""}`} x1={lane.x1 + 14} y1={lane.y} x2={lane.x2} y2={lane.y} />
            {lane.state === "vrácen" && <><path className="pletor-dashboard__linie-lane-turn" d={`M${lane.x2} ${lane.y} L${lane.x2 + 14} ${axis}`} /><circle cx={lane.x2 + 14} cy={axis} r={3.5} fill={lane.color} stroke="none" /></>}
          </g>
        );
      })}
      {layers.tags && layout.tags.map((tag) => <line key={`${tag.kind}-${tag.text}-${tag.x}`} className="pletor-dashboard__linie-tagmark" x1={tag.x} y1={tag.y - 16} x2={tag.x} y2={tag.y + 16} />)}
      {commits.map((commit) => (
        <g key={`${commit.ticketId}-${commit.ref}`} className={`pletor-dashboard__linie-cubeset${commit.abandoned ? " pletor-dashboard__linie-cubeset--dead" : ""}`} style={{ "--c": layout.balls.find((b) => b.ticketId === commit.ticketId)?.color } as CSSProperties}
          role="button" tabIndex={-1} onClick={() => onPickCommit(commit.ticketId)}>
          {commit.abandoned && <path className="pletor-dashboard__linie-cube-stub" d={stub(commit)} />}
          <rect className="pletor-dashboard__linie-cube" x={commit.x - 3} y={commit.y - 5} width={6} height={10} rx={1} />
          <title>{`${commit.ref} ${commit.title}${commit.abandoned ? " · opuštěno (zůstává v historii, do cíle nejde)" : ""} · ${commit.at}`}</title>
        </g>
      ))}
    </>
  );
}

/** HTML část značek: štítky tagů a nasazení pod značkou, ✕ u opuštěného commitu, sha při přiblížení, pilulky PR na spojnici. */
export function PlotMarksHtml({ layout, selected, layers }: Omit<Props, "onPickCommit">) {
  const mine = (ticketId: string) => ticketId === selected;
  const commits = layout.commits.filter((commit) => layers.commits || mine(commit.ticketId));
  const showSha = layout.k * 15 * 60000 >= 84; // sha jen při přiblížení se značkami osy po 5–15 min
  return (
    <>
      {layers.tags && layout.tags.map((tag) => (
        <span key={`${tag.kind}-${tag.text}-${tag.x}`} className={`pletor-dashboard__linie-taglabel pletor-dashboard__linie-taglabel--${tag.kind}`} style={{ left: tag.x, top: tag.y + 16 }} title={tag.title}>{tag.text}</span>
      ))}
      {commits.filter((c) => c.abandoned).map((c) => <span key={`x-${c.ticketId}-${c.ref}`} className="pletor-dashboard__linie-cube-x" style={{ left: c.x + 28, top: c.y - 27 }}>✕</span>)}
      {showSha && commits.map((c) => <span key={`sha-${c.ticketId}-${c.ref}`} className="pletor-dashboard__linie-cube-sha" style={{ left: c.x, top: c.y - 22 }}>{c.ref}</span>)}
      {layers.prs && layout.links.filter((link) => link.pr && (link.kind === "merged" || layers.plans || mine(link.ticketId))).map((link) => (
        <span key={`pr-${link.ticketId}-${link.kind}`} className={`pletor-dashboard__linie-pr pletor-dashboard__linie-pr--${link.pr!.unverified ? "unverified" : link.pr!.state}`}
          style={{ left: link.pr!.at.x, top: link.pr!.at.y + (link.kind === "merged" ? 16 : 12) }} title={link.pr!.unverified ? "poslední známý stav, GitHub nepotvrdil" : "potvrzeno GitHubem"}>{link.pr!.text}</span>
      ))}
    </>
  );
}
