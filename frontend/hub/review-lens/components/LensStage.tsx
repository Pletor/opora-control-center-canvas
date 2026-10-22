import { useEffect, useMemo, useRef, useState } from "react";
import type { LensRecord } from "../logic/lens-read";
import { parseSpec, renderStage } from "../logic/stage-render";
import { useAppTheme } from "../logic/use-review-lens";
import { focusBoxes, stageFlow, stagesOf, stepStage, walkKey, walkReducer, type Stage, type WalkAction } from "../logic/walkthrough";
import LensViewport, { type Selection } from "./LensViewport";
import WalkthroughBar from "./WalkthroughBar";
import CardPanel from "./CardPanel";
import PayloadPanel from "./PayloadPanel";

const typing = (target: EventTarget | null) => target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));

/** Plátno Lens (líně načtené): ověří spec schématem, vykreslí zvolené plátno a vede průvodce. */
export default function LensStage({ record }: { record: LensRecord }) {
  const parsed = useMemo(() => parseSpec(record.spec), [record.spec]);
  const doc = parsed.doc;
  const stages = useMemo(() => doc ? stagesOf(doc) : [], [doc]);
  const steps = doc?.walkthrough?.steps ?? [];
  const [chosen, setChosen] = useState<Stage | null>(null);
  const [walk, setWalk] = useState({ index: -1 });
  const [selected, setSelected] = useState<Selection>(null);
  const theme = useAppTheme();
  const stage = chosen ?? stages[0] ?? null;
  const step = walk.index >= 0 ? steps[walk.index] ?? null : null;
  const drawn = useMemo(() => doc && stage ? renderStage(doc, stage, theme) : null, [doc, stage, theme]);
  const flow = stage ? stageFlow(stage, step) : null;
  const focus = useMemo(() => step && drawn && "atlas" in drawn ? focusBoxes(step, drawn.atlas, flow) : [], [step, drawn, flow]);

  const act = useRef<(action: WalkAction) => void>(() => {});
  act.current = (action: WalkAction) => {
    if (!doc || !stage) return;
    const next = walkReducer(walk, action, steps.length);
    setWalk(next);
    const target = steps[next.index];
    if (target) setChosen(stepStage(doc, target, stage, stages));
  };
  // Klávesy průvodce v zachytávací fázi: Esc zastaví průvodce dřív, než by zavřel celý detail karty.
  useEffect(() => {
    const keyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || typing(event.target)) return;
      const action = walkKey(event.key, walk.index >= 0);
      if (!action || !steps.length) return;
      event.preventDefault(); event.stopPropagation();
      act.current(action);
    };
    document.addEventListener("keydown", keyDown, true);
    return () => document.removeEventListener("keydown", keyDown, true);
  }, [walk.index, steps.length]);

  if (!doc) return <p className="review-lens__warning" role="alert" data-oh-lens-invalid="">Spec neprošel schématem PR Lens, proto se nekreslí: {parsed.error}</p>;
  const repo = doc.provenance.repo;
  return <div className={`review-lens__stage${step ? " review-lens__stage--walking" : ""}`} data-oh-lens-stage={stage?.key ?? ""} data-oh-lens-theme={theme} data-oh-walk-step={step?.id ?? ""}>
    <div className="review-lens__toolbar" role="toolbar" aria-label="Plátno Lens">
      <div className="review-lens__switch" role="group" aria-label="Čočka a pohled">
        {stages.map(item => <button key={item.key} type="button" className="review-lens__switch-item" aria-pressed={item.key === stage?.key}
          data-oh-lens-switch={item.key} data-oh-lens-lens={item.lens} onClick={() => { setChosen(item); setSelected(null); }}>
          <span className="review-lens__switch-lens">{item.lens === "architecture" ? "◫" : "⇄"}</span>{item.label}</button>)}
        {stage && !stages.some(item => item.key === stage.key) && <span className="review-lens__switch-item" aria-pressed="true">⇄ {stage.label}</span>}
      </div>
      <span className="review-lens__grow" />
      {steps.length > 0 && walk.index < 0 && <button type="button" className="review-lens__play" data-oh-walk-start="" onClick={() => act.current("start")}>
        ▶ Průvodce <kbd className="review-lens__kbd">W</kbd> <span className="review-lens__muted">{steps.length} kroků</span></button>}
    </div>
    {step && <WalkthroughBar step={step} index={walk.index} total={steps.length} onAction={action => act.current(action)} />}
    <div className="review-lens__grid">
      {drawn && "svg" in drawn ? <LensViewport drawn={drawn} title={stage?.label ?? doc.title} lens={stage?.lens ?? "architecture"} flow={flow}
        focus={focus} selected={selected} onSelect={setSelected} doc={doc} />
        : <p className="review-lens__warning" role="alert">{drawn && "error" in drawn ? drawn.error : "Spec nemá co kreslit."}</p>}
      <aside className="review-lens__side" aria-label="Detail části">
        {selected?.kind === "node" && <CardPanel doc={doc} nodeId={selected.id} repo={repo} headSha={record.headSha ?? doc.provenance.head.sha}
          onSelect={id => setSelected({ kind: "node", id })} onClose={() => setSelected(null)} />}
        {selected?.kind === "message" && <PayloadPanel doc={doc} flowId={selected.flow} messageId={selected.id} onClose={() => setSelected(null)} />}
        {!selected && <div className="review-lens__hint">
          <b>{doc.title}</b><p>{doc.summary}</p>
          <p className="review-lens__muted">Klik na část ukáže soubory a vazby, klik na krok toku jeho payload. Kolečko přibližuje, tažení posouvá.</p>
        </div>}
      </aside>
    </div>
  </div>;
}
