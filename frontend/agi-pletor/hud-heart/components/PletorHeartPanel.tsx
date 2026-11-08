import "../styles/pletor-heart.css";
import { useEffect, useState } from "react";
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { STEP_TAG, heartPanel } from "../logic/heart-panel";

type Props = {
  /** Stav srdce z pollingu Pletora: `undefined` = ještě nenačteno (nic se neukáže), `null` = dotaz selhal. */
  status: HeartStatus | null | undefined;
  /** Otevřená otázka Pletora má odpověď srdce. */
  answered: boolean;
  /** `hud` = pod readoutem PRJ/MOZEK v kokpitu, `window` = menší nad řádkem otázky v okně. */
  place: "hud" | "window";
};

/** Co dělá Srdce a zda má člověk čekat, nebo mluvit; jen čte, co dal rodič. Během práce si sám tiká po vteřině kvůli času. */
export default function PletorHeartPanel({ status, answered, place }: Props) {
  const [now, setNow] = useState(() => Date.now());
  const running = !!status?.running;
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  if (status === undefined && !answered) return null;
  const view = heartPanel({ status: status ?? null, answered, now });
  const steps = place === "window" ? view.steps.slice(-3) : view.steps;
  return (
    <section className={`pletor-heart pletor-heart--${place} pletor-heart--${view.kind}`} role="status" aria-live="polite" aria-label="Srdce">
      <p className="pletor-heart__title">
        <i className="pletor-heart__pulse" aria-hidden="true" />
        {view.title}
      </p>
      {view.detail && <p className="pletor-heart__detail" title={view.detail}>{view.detail}</p>}
      {steps.length > 0 && (
        <ol className="pletor-heart__steps">
          {steps.map((step, index) => (
            <li key={`${step.t}-${index}`} className={`pletor-heart__step pletor-heart__step--${step.kind}`} title={step.text}>
              <span className="pletor-heart__tag">{STEP_TAG[step.kind] ?? step.kind}</span>
              <span className="pletor-heart__text">{step.text}</span>
            </li>
          ))}
        </ol>
      )}
      {view.hint && <p className="pletor-heart__hint">{view.hint}</p>}
    </section>
  );
}
