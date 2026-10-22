import type { ReactNode } from "react";
import { PHASES } from "../logic/process-event";

/** Tvar stavu: plný kruh hotovo/běží, kosočtverec selhání, dutý kroužek čekání. Barva jen z tokenů. */
export function StateDot({ state }: { state: string }) {
  return <i className={`process-observatory__dot process-observatory__dot--${state}`} aria-hidden="true" />;
}

/** Fáze toku jako malý čip s pořadím (1 Zadání … 7 Paměť); neznámá fáze pomlčka. */
export function PhaseChip({ phase }: { phase: number }) {
  const name = PHASES[phase]?.[1];
  return <span className="process-observatory__phase">
    <span className="process-observatory__num">{name ? phase + 1 : "?"}</span>{name ?? "—"}
  </span>;
}

export function CardHash({ id, ghost = true }: { id: string; ghost?: boolean }) {
  return <span className={`process-observatory__hash${ghost ? " process-observatory__hash--ghost" : ""}`}>{id}</span>;
}

export function Chip({ tone, children, title }: { tone: string; children: ReactNode; title?: string }) {
  return <span className={`process-observatory__chip process-observatory__chip--${tone}`} title={title}>{children}</span>;
}
