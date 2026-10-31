// Rozbalená relace dělníka v ose: jeho shrnutí v uvozovkách (tvrzení, ne fakt) a pod ním kroky s důkazem:
// kontroly zelená/červená, commity a soubory. Kroky bez důkazu zůstanou jen s názvem, nic se nedomýšlí.
import type { TrailRun } from "../logic/card-trail";
import { stepMark } from "../logic/trail-timeline";
import SourceMark from "./SourceMark";

export default function TrailRunBody({ run, filesKnown }: { run: TrailRun; filesKnown: boolean }) {
  return (
    <div className="block-panel__run-body">
      {run.summary.trim() && <p className="block-panel__run-sum"><SourceMark source={run.source} /><span>„{run.summary.trim()}“</span></p>}
      {run.steps.map((step) => {
        const mark = stepMark(step.status);
        return (
          <div key={step.stepId} className={"block-panel__ev block-panel__ev--" + mark.tone} data-oh-step={step.stepId}>
            <div className="block-panel__ev-title"><span className={"block-panel__ev-mark block-panel__ev-mark--" + mark.tone} aria-hidden="true">{mark.glyph}</span>
              <span>{step.stepId} {step.title}</span></div>
            {(step.checks.length > 0 || step.commits.length > 0) && <div className="block-panel__ev-line">
              {step.checks.map((check) => <span key={check.name} className={"block-panel__check block-panel__check--" + check.status}>{check.name}</span>)}
              {step.commits.map((sha) => <code key={sha} className="block-panel__commit" title={sha}>{sha.slice(0, 7)}</code>)}
            </div>}
            {filesKnown && step.files && step.files.length > 0 && <div className="block-panel__ev-line">
              {step.files.slice(0, 4).map((file) => <code key={file} className="block-panel__file">{file}</code>)}
              {step.files.length > 4 && <span className="block-panel__muted">+{step.files.length - 4}</span>}
            </div>}
            {step.notes.trim() && <p className="block-panel__ev-note"><SourceMark source={step.source} />{step.notes.trim()}</p>}
          </div>
        );
      })}
      {run.attempts > 1 && <p className="block-panel__muted">{run.attempts} hlášení</p>}
    </div>
  );
}
