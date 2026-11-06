import type { KeyboardEvent } from "react";
import { badgeWidth, clip, textWidth, type GraphBadge, type GraphLayout } from "../logic/linie-graph";

type Props = { layout: GraphLayout; selected: string; links: Record<string, string>; onPick: (name: string) => void };

const ICON: Record<GraphBadge["kind"], string> = { accepted: "✓ ", stale: "! ", preview: "◉ ", pr: "" };
const HEADER_MAX = 18;
const SUBTITLE_MAX = 22;

const curve = ({ from, to }: { from: { x: number; y: number }; to: { x: number; y: number } }) => {
  const mid = (from.y + to.y) / 2;
  return `M ${from.x} ${from.y} C ${from.x} ${mid}, ${to.x} ${mid}, ${to.x} ${to.y}`;
};

/**
 * Graf Linie jako SVG: hlavičky větví nahoře (klik vybere větev), svislé linie, oblouky odbočení a návratu,
 * body commitů s popiskem vpravo a štítky u špičky. Bublina náhledu a štítek PR otevřou odkaz z `links` (klíč `kind:lane`).
 */
export default function LinieGraph({ layout, selected, links, onPick }: Props) {
  const key = (name: string) => (event: KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(name); } };
  const open = (badge: GraphBadge) => {
    const url = links[`${badge.kind}:${badge.lane}`];
    if (url) window.open(url, "_blank", "noopener");
  };

  return (
    <svg className="pletor-dashboard__linie-svg" width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label="Graf větví">
      <defs>
        <marker id="linie-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--linie-main)" />
        </marker>
      </defs>

      {layout.lanes.map((lane) => (
        <line key={`line-${lane.name}`} x1={lane.x} y1={lane.top} x2={lane.x} y2={lane.bottom} stroke={lane.color} strokeWidth={3}
          markerEnd={lane.role === "main" ? "url(#linie-arrow)" : undefined} />
      ))}
      {layout.links.map((link, index) => (
        <path key={`link-${index}`} d={curve(link)} fill="none" stroke={link.color} strokeWidth={3} />
      ))}

      {layout.lanes.map((lane) => {
        const name = clip(lane.name, HEADER_MAX);
        return (
          <g key={`head-${lane.name}`} className={`pletor-dashboard__linie-head${lane.name === selected ? " pletor-dashboard__linie-head--selected" : ""}`}
            role="button" tabIndex={0} aria-label={`Vybrat ${lane.name}`} aria-pressed={lane.name === selected}
            onClick={() => onPick(lane.name)} onKeyDown={key(lane.name)}>
            <title>{lane.name}</title>
            <rect x={lane.x - 12} y={8} width={textWidth(name) + 20} height={26} rx={7} stroke={lane.color} />
            <text x={lane.x - 2} y={26} fill={lane.color} className="pletor-dashboard__linie-name">{name}</text>
            <text x={lane.x - 10} y={52} className="pletor-dashboard__linie-sub">{clip(lane.label, SUBTITLE_MAX)}</text>
          </g>
        );
      })}

      {layout.dots.map((dot) => {
        const lane = layout.lanes.find((item) => item.name === dot.lane);
        return (
          <g key={dot.sha}>
            <circle cx={dot.x} cy={dot.y} r={7} fill={lane?.color} className="pletor-dashboard__linie-dot" />
            <text x={dot.x + 14} y={dot.y + 4} className="pletor-dashboard__linie-label">
              {dot.title} <tspan className="pletor-dashboard__linie-sha">{dot.sha7}</tspan>
            </text>
          </g>
        );
      })}

      {layout.badges.map((badge) => {
        const text = ICON[badge.kind] + badge.text;
        const url = links[`${badge.kind}:${badge.lane}`];
        return (
          <g key={`${badge.kind}-${badge.lane}`} className={`pletor-dashboard__linie-badge pletor-dashboard__linie-badge--${badge.kind}`}
            role={url ? "link" : undefined} tabIndex={url ? 0 : undefined} onClick={url ? () => open(badge) : undefined}
            onKeyDown={url ? (event) => { if (event.key === "Enter") open(badge); } : undefined}>
            <rect x={badge.x} y={badge.y - 10} width={badgeWidth(text)} height={20} rx={6} />
            <text x={badge.x + 8} y={badge.y + 4}>{text}</text>
          </g>
        );
      })}
    </svg>
  );
}
