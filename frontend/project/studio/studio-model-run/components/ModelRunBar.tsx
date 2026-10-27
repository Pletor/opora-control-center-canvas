import type { EditModel } from "../../studio-model/logic/model-edit";
import { incidentNodes, RUN_SPEEDS, type RunState } from "../logic/run-control";
import { formatNumber, formatPercent, runSummary } from "../logic/run-view";
import "../styles/studio-model-run.css";

export type RunBarActions = {
  onStart: () => void; onPause: () => void; onStep: () => void; onReset: () => void; onSpeed: (speed: number) => void;
  onSurge: () => void; onRestoreAll: () => void; onScenarios: () => void;
};

/** Lišta RUN pod lištou modelu (prototyp `runtimebar`): Start / Pause, +1 krok, rychlost 0,25–5×, čítač ticku, Reset,
 * přepínač zátěže Surge ×5, Obnovit vše a knihovna scénářů; vpravo souhrn běhu (propustnost, chybovost, nejvytíženější
 * komponenta) se štítkem, že jde o výpočet modelu. Akce hlásí rodiči. */
export default function ModelRunBar({ run, model, actions }: { run: RunState; model: EditModel; actions: RunBarActions }) {
  const { sim, running } = run, summary = runSummary(sim, model), incidents = incidentNodes(sim).length, empty = !model.nodes.length;
  return <div className={"studio-model-run" + (running ? " studio-model-run--running" : "")} data-testid="studio-model-run" aria-label="Běh modelu">
    <button type="button" className="studio-model-run__start" data-testid="studio-model-run-start" onClick={running ? actions.onPause : actions.onStart} disabled={empty}>
      {running ? "❚❚ Pause" : "▶ Start"}</button>
    <button type="button" className="studio-model-run__tool" data-testid="studio-model-run-step" onClick={actions.onStep} disabled={running || empty} title="Jeden tick = jedna modelová sekunda">+1 krok</button>
    <label className="studio-model-run__speed">Rychlost
      <select className="studio-model-run__select" value={run.speed} data-testid="studio-model-run-speed" onChange={(event) => actions.onSpeed(Number(event.target.value))}>
        {RUN_SPEEDS.map((speed) => <option key={speed} value={speed}>{speed.toLocaleString("cs-CZ")}×</option>)}
      </select>
    </label>
    <span className={"studio-model-run__tick" + (running ? " studio-model-run__tick--running" : "")} role="status" data-testid="studio-model-run-tick">
      ● {running ? "Běží" : sim.tick ? "Pauza" : "Stojí"} · tick {sim.tick}</span>
    <button type="button" className="studio-model-run__tool" data-testid="studio-model-run-reset" onClick={actions.onReset} disabled={!sim.tick && !incidents && sim.surge === 1}
      title="Odstraní jen dočasný běh, definice modelu zůstane">Reset</button>
    <span className="studio-model-run__divider" aria-hidden="true"/>
    <button type="button" className={"studio-model-run__tool" + (sim.surge !== 1 ? " studio-model-run__tool--on" : "")} data-testid="studio-model-run-surge" onClick={actions.onSurge} disabled={empty}
      aria-pressed={sim.surge !== 1} title="Zdroje modelu nabízejí pětinásobek">Surge ×5</button>
    <button type="button" className="studio-model-run__tool" data-testid="studio-model-run-restore-all" onClick={actions.onRestoreAll} disabled={!incidents}>Obnovit vše{incidents ? ` (${incidents})` : ""}</button>
    <button type="button" className="studio-model-run__tool" data-testid="studio-model-scenarios" onClick={actions.onScenarios}>Scénáře</button>
    <p className="studio-model-run__summary" data-testid="studio-model-run-summary" title="Všechny hodnoty jsou výpočet modelu (jednotky za modelovou sekundu), ne měření projektu">
      <span className="studio-model-run__source">výpočet modelu</span>
      {sim.tick || sim.preview ? <>
        propustnost <strong>{formatNumber(summary.throughput)}/s</strong> · chybovost <strong>{formatPercent(summary.errorRate)}</strong>
        {summary.busiest && <> · nejvytíženější <strong>{summary.busiest.name}</strong> {formatPercent(Math.min(1, summary.busiest.utilization))}</>}
      </> : "Spusťte nebo krokujte model."}
    </p>
    {run.error && <p className="studio-model-run__error" role="alert" data-testid="studio-model-run-error">{run.error}</p>}
  </div>;
}
