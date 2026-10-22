import { ViewportPortal, useStore, type ReactFlowState } from "@xyflow/react";
import type { CSSProperties } from "react";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { loopBadges } from "../logic/loop-badges";
import "../styles/loop-badges.css";

type Place = { id: string; x: number; y: number; w: number };
// Poloha karet vrstvy z React Flow: absolutní pozice a změřená šířka; řetězec drží výběr stabilní.
const placesOf = (state: ReactFlowState) => [...state.nodeLookup.values()]
  .filter(node => node.type === "canvas" && !node.hidden)
  .map(node => [node.id, Math.round(node.internals.positionAbsolute.x), Math.round(node.internals.positionAbsolute.y),
    Math.round(node.measured.width ?? node.width ?? 240)].join("|"))
  .join("\n");
const parse = (value: string): Place[] => value ? value.split("\n").map(line => {
  const [id, x, y, w] = line.split("|"); return { id, x: Number(x), y: Number(y), w: Number(w) };
}) : [];

/** Odznaky etap OporaHubu nad kartami plátna: jedno sdílené čtení agent-state, klik otevře drawer karty. */
export default function LoopBadgeLayer({ project, workspace, onOpen }: { project: string; workspace: string; onOpen: (nodeId: string) => void }) {
  const agent = useAgentState(project, workspace);
  const places = parse(useStore(placesOf));
  const badges = loopBadges(agent.state, places.map(item => item.id));
  const where = new Map(places.map(item => [item.id, item]));
  return <>
    <JsonMirror id="oh-card-stages" value={agent.state?.cards ?? null} />
    <ViewportPortal>
      <div className="loop-badges" data-oh-view="canvas-badges" data-oh-etag={agent.etag} data-oh-generated-at={agent.state?.generatedAt ?? ""}>
        {badges.map(badge => {
          const place = where.get(badge.nodeId)!;
          const style = { transform: `translate(${place.x + place.w}px, ${place.y}px) translate(-100%, -100%)` } as CSSProperties;
          return <button key={badge.nodeId} type="button" style={style} title={badge.title} aria-label={badge.title}
            className={`loop-badges__badge loop-badges__badge--${badge.tone} nodrag nopan`} onClick={() => onOpen(badge.nodeId)}
            data-oh-card-badge={badge.nodeId} data-oh-stage={badge.stage} data-oh-health={badge.health} data-oh-reason={badge.reason}
            data-oh-execution={badge.executionId ?? ""}>
            <span className="loop-badges__glyph" aria-hidden="true">{badge.glyph}</span>
            <span className="loop-badges__stage">{badge.stageLabel}</span>
            <span className="loop-badges__word">{badge.word}</span>
          </button>;
        })}
      </div>
    </ViewportPortal>
  </>;
}
