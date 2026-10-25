import type { LineDiff, SpecDiffView, StepDiff, TextDiff } from "../logic/spec-diff";
import HarnessKit from '@/shared/harness-kit/components/HarnessKit';

export type SpecMode = "accepted" | "working" | "diff";
const SIGN = { added: "+", removed: "−", changed: "~", same: "" } as const;

function TextBlock({ field, label, diff, mode, extra }: { field: string; label: string; diff: TextDiff; mode: SpecMode; extra?: string }) {
  const text = mode === "accepted" ? diff.before : diff.after;
  return <section className="spec-tab__block" data-oh-spec-field={field} data-oh-diff={diff.state}>
    <h4 className="spec-tab__label">{label} · {diff.state === "same" ? "beze změny" : "změněno"}</h4>
    {mode === "diff" && diff.state === "changed"
      ? <><p className="spec-tab__line spec-tab__line--removed"><span aria-hidden="true">−</span>{diff.before || "(prázdné)"}</p>
        <p className="spec-tab__line spec-tab__line--added"><span aria-hidden="true">+</span>{diff.after || "(prázdné)"}</p></>
      : <p className="spec-tab__text">{text || <span className="spec-tab__muted">(nevyplněno)</span>}</p>}
    {extra && <p className="spec-tab__muted">Účel komponenty: {extra}</p>}
  </section>;
}

function AcceptanceBlock({ lines, mode }: { lines: LineDiff[]; mode: SpecMode }) {
  const shown = lines.filter(line => mode === "diff" || (mode === "accepted" ? line.kind !== "added" : line.kind !== "removed"));
  const changes = lines.filter(line => line.kind !== "same").length;
  return <section className="spec-tab__block" data-oh-spec-field="acceptance" data-oh-diff={changes ? "changed" : "same"}>
    <h4 className="spec-tab__label">Akceptace karty · {changes ? `${changes} změn` : "beze změny"}</h4>
    {shown.length ? <ul className="spec-tab__list">
      {shown.map((line, index) => <li key={`${line.kind}:${index}`} data-oh-line={line.kind}
        className={mode === "diff" && line.kind !== "same" ? `spec-tab__line spec-tab__line--${line.kind}` : "spec-tab__item"}>
        <span aria-hidden="true">{mode === "diff" && line.kind !== "same" ? SIGN[line.kind] : "•"}</span>{line.text}</li>)}
    </ul> : <p className="spec-tab__muted">(bez podmínek)</p>}
  </section>;
}

function stepText(row: StepDiff) {
  const step = row.after ?? row.before!;
  const deps = step.dependsOn.length ? ` · závisí na ${step.dependsOn.join(", ")}` : "";
  return `${step.id} ${step.title}${step.kind ? ` · ${step.kind}` : ""}${deps}`;
}

function StepsBlock({ steps, mode }: { steps: StepDiff[] | null; mode: SpecMode }) {
  if (!steps) return <section className="spec-tab__block" data-oh-spec-field="steps" data-oh-diff="unknown">
    <h4 className="spec-tab__label">Kroky · nenapojeno</h4>
    <p className="spec-tab__muted">◌ Server zatím nevydává kroky plánu (`spec.steps`); kroky přibudou s modulem kroků plánu.</p>
  </section>;
  const shown = steps.filter(row => mode === "diff" ? row.kind !== "same" : mode === "accepted" ? row.kind !== "added" : row.kind !== "removed");
  const changes = steps.filter(row => row.kind !== "same").length;
  return <section className="spec-tab__block" data-oh-spec-field="steps" data-oh-diff={changes ? "changed" : "same"}>
    <h4 className="spec-tab__label">Kroky · {changes ? `${changes} změn` : "beze změny"}</h4>
    {shown.length ? <ul className="spec-tab__list">{shown.map(row => <li key={row.id} data-oh-step-diff={row.id} data-oh-diff={row.kind}
      className={mode === "diff" ? `spec-tab__line spec-tab__line--${row.kind}` : "spec-tab__item"}>
      <span aria-hidden="true">{mode === "diff" ? SIGN[row.kind] : "•"}</span>{stepText(row)}
      {row.kind === "changed" && <span className="spec-tab__muted"> — změna: {row.changed.join(", ")}</span>}
    </li>)}</ul> : <p className="spec-tab__muted">{mode === "diff" ? "Kroky beze změny." : "(bez kroků)"}</p>}
  </section>;
}

/** Zadání ve třech pohledech: přijaté, pracovní a rozdíl (− přijaté, + pracovní, ~ změněný krok). */
export default function SpecDiff({ view, mode, purpose }: { view: SpecDiffView; mode: SpecMode; purpose: string }) {
  return <div className="spec-tab__card" data-oh-spec-mode={mode} data-oh-spec-changes={view.changes}>
    <TextBlock field="goal" label="Cíl" diff={view.goal} mode={mode} extra={purpose} />
    <TextBlock field="non_goals" label="Ne-cíle" diff={view.nonGoals} mode={mode} />
    <AcceptanceBlock lines={view.acceptance} mode={mode} />
    <StepsBlock steps={view.steps} mode={mode} />
    {view.harness && <HarnessKit {...view.harness} mode={mode} />}
  </div>;
}
