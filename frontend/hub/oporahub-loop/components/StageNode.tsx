import type { CSSProperties } from "react";
import type { StageView } from "@/hub/oporahub-agent-state/logic/loop-model";
import { actorLabel } from "@/hub/oporahub-agent-state/logic/loop-model";
import HealthMark, { ActorMark } from "@/hub/oporahub-health/components/HealthMark";

/** Jedna etapa smyčky: číslo, název, kdo ji dělá, počet a strojový důvod v češtině. Klik otevře detail. */
export default function StageNode({ stage, onOpen }: { stage: StageView; onOpen: () => void }) {
  const place = { "--oh-row": stage.row, "--oh-col": stage.col } as CSSProperties;
  return <button type="button" className={`oporahub-loop__stage oporahub-loop__stage--${stage.tone}`} style={place} onClick={onOpen}
    data-oh-stage={stage.id} data-oh-health={stage.health} data-oh-reason={stage.reason} data-oh-count={stage.count}
    aria-label={`${stage.n}. ${stage.label}: ${stage.count} ${stage.unit}, ${stage.reasonText}`}>
    <span className="oporahub-loop__stage-head">
      <span className="oporahub-loop__num">{stage.n}</span>{stage.label}
      <ActorMark actor={stage.actor} label={actorLabel[stage.actor]} />
    </span>
    {stage.health === "not_connected"
      ? <span className="oporahub-loop__count oporahub-loop__count--none">—</span>
      : <span className="oporahub-loop__count">{stage.count}<small className="oporahub-loop__unit">{stage.unit}</small></span>}
    <HealthMark health={stage.health} />
    <span className="oporahub-loop__reason">{stage.reasonText}</span>
    {stage.extra && <span className={`oporahub-loop__extra oporahub-loop__extra--${stage.extra.tone}`} {...stage.extra.attrs}>{stage.extra.text}</span>}
  </button>;
}
