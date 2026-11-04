import { useEffect, useRef } from "react";
import type { HeartStep } from "@/layout/heart-channel/logic/heart-api";
import { stepTime } from "../logic/heart-work";
import "../styles/heart-work.css";

const ICON: Record<HeartStep["kind"], string> = { thinking: "…", text: "¶", tool: "›", result: "=" };
const LABEL: Record<HeartStep["kind"], string> = { thinking: "přemýšlí", text: "píše", tool: "příkaz", result: "výsledek" };

/** Živý seznam kroků dávky od prvního k poslednímu; u běžící dávky drží posuv dole, aby byl vidět poslední krok. */
export default function WorkSteps({ steps, follow }: { steps: readonly HeartStep[]; follow: boolean }) {
  const box = useRef<HTMLOListElement>(null);
  useEffect(() => { if (follow && box.current) box.current.scrollTop = box.current.scrollHeight; }, [steps.length, follow]);
  return <ol className="heart-work__steps" ref={box} aria-label="Kroky srdce" data-testid="heart-work-steps">
    {steps.map((step, index) => <li key={index} className={`heart-work__step heart-work__step--${step.kind}`}>
      <span className="heart-work__time">{stepTime(step.t)}</span>
      <span className="heart-work__icon" title={LABEL[step.kind]} aria-label={LABEL[step.kind]}>{ICON[step.kind]}</span>
      <span className="heart-work__text">{step.kind === "thinking" && <em className="heart-work__tag">přemýšlí </em>}{step.text}</span>
    </li>)}
  </ol>;
}
