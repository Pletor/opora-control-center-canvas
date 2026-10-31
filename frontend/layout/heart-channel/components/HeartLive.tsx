import type { HeartCurrent } from "../logic/heart-api";
import { liveLine, type StepRow } from "../logic/heart-live";
import StepList from "./StepList";

/** Srdce právě teď: od kdy pracuje, co ho probudilo, a pod tím živé kroky běžící dávky. */
export default function HeartLive({ current, steps }: { current: HeartCurrent; steps: StepRow[] }) {
  return (
    <div className="heart-channel__live" aria-live="polite">
      <p className="heart-channel__live-line">{liveLine(current)}</p>
      <StepList steps={steps} empty="Zatím nic nezapsalo, čte a přemýšlí…" label="Kroky běžící dávky" />
    </div>
  );
}
