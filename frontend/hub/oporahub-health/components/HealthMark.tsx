import type { ReactNode } from "react";
import type { Health } from "@/hub/oporahub-agent-state/logic/agent-state";
import { healthGlyph, healthLabel } from "@/hub/oporahub-agent-state/logic/loop-model";
import "../styles/oporahub-health.css";

/** Štítek zdraví: tvar značky + slovo + barva; žádný stav se nerozlišuje jen odstínem. */
export default function HealthMark({ health, text }: { health: Health; text?: string }) {
  return <span className={`oporahub-health oporahub-health--${health}`}>
    <span className="oporahub-health__glyph" aria-hidden="true">{healthGlyph[health]}</span>{text ?? healthLabel[health]}
  </span>;
}

/** Kdo krok dělá: člověk zlatě (kulatý), agent tyrkysově (hranatý), aby rozdíl nesla i forma. */
export function ActorMark({ actor, label }: { actor: "human" | "agent" | "both" | "system"; label: string }) {
  return <span className={`oporahub-health__actor oporahub-health__actor--${actor}`} data-oh-actor={actor}>{label}</span>;
}

/** Obecný čip s tónem pro rizika a stavy, které nejsou zdravím etapy. */
export function ToneChip({ tone, children }: { tone: "ok" | "warn" | "bad" | "gap" | "acc"; children: ReactNode }) {
  return <span className={`oporahub-health__chip oporahub-health__chip--${tone}`}>{children}</span>;
}
