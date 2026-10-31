import type { StepRow } from "../logic/heart-live";

/** Kroky srdce jako věty, nejnovější nahoře: čas, co udělalo, karty a štítek selhání u ne-2xx. */
export default function StepList({ steps, empty, label }: { steps: StepRow[]; empty: string; label: string }) {
  if (steps.length === 0) return <p className="heart-channel__steps-empty">{empty}</p>;
  return (
    <ol className="heart-channel__steps" aria-label={label}>
      {steps.map((step) => (
        <li key={step.key} className={`heart-channel__step${step.failed ? " heart-channel__step--failed" : ""}`}>
          <span className="heart-channel__step-time">{step.time}</span>
          <span className="heart-channel__step-text">
            {step.text}
            {step.cards.length > 0 && <span className="heart-channel__step-cards"> · {step.cards.join(", ")}</span>}
          </span>
          {step.failed && <span className="heart-channel__step-failed" title={`HTTP ${step.status}`}>selhalo</span>}
        </li>
      ))}
    </ol>
  );
}
