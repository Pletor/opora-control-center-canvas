import type { CardState } from "../logic/card-state";
import "../styles/card-state.css";

/** Štítek stavu karty jako ve Studiu (plán, staví se, hotovo, ověřeno, díra) v barvě stavu; bez stavu nic. */
export default function CardStateChip({ state, testId }: { state: CardState | null | undefined; testId?: string }) {
  if (!state) return null;
  return <span className={"card-state__chip card-state--" + state.state} data-testid={testId} title={state.summary}>{state.label}</span>;
}
