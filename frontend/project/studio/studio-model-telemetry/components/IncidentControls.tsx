import { useState } from "react";
import type { IncidentKind, ModelIncident } from "../../model/simulation/logic";
import { INCIDENT_LABELS, PLANNABLE } from "../../studio-model-run/logic/incident-plan";

export type IncidentActions = {
  onIncident: (kind: "crash" | "slow" | "restore", nodeId: string) => void;
  /** Uloží plánovaný incident do modelu; vrací důvod, proč nešel, nebo null. */
  onPlan: (kind: IncidentKind, nodeId: string, tick: number) => string | null;
  onUnplan: (index: number, nodeId: string) => void;
};

/** Incidenty vybrané komponenty (Chaos Lab z prototypu, jen model): Crash, Slow ×5 a Restore hned do běhu; pod tím
 * „Uložit jako plánovaný incident“ (druh a tick od 1) do definice modelu a výpis plánu komponenty s odebráním.
 * Plán se uloží až tlačítkem Uložit v liště modelu. */
export default function IncidentControls({ nodeId, tick, planned, actions }: { nodeId: string; tick: number; planned: { index: number; incident: ModelIncident }[]; actions: IncidentActions }) {
  const [kind, setKind] = useState<IncidentKind>("crash");
  // Prázdné pole = další tick běhu (nápověda v poli se posouvá s během).
  const [at, setAt] = useState("");
  const [error, setError] = useState("");
  const plan = () => setError(actions.onPlan(kind, nodeId, at.trim() ? Number(at) : tick + 1) ?? "");
  return <section className="studio-model-telemetry__incidents" aria-label="Incidenty komponenty">
    <h3 className="studio-model-telemetry__heading">Incident · jen model</h3>
    <div className="studio-model-telemetry__row">
      {PLANNABLE.map((item) => <button key={item} type="button" className={"studio-model-telemetry__button studio-model-telemetry__button--" + item}
        data-testid={`studio-model-incident-${item}`} onClick={() => actions.onIncident(item, nodeId)}>{INCIDENT_LABELS[item]}</button>)}
    </div>
    <div className="studio-model-telemetry__row">
      <select className="studio-model-telemetry__input" value={kind} aria-label="Druh plánovaného incidentu" onChange={(event) => setKind(event.target.value as IncidentKind)}>
        {PLANNABLE.map((item) => <option key={item} value={item}>{INCIDENT_LABELS[item]}</option>)}
      </select>
      <label className="studio-model-telemetry__tick">tick
        <input className="studio-model-telemetry__input studio-model-telemetry__input--tick" type="number" min={1} step={1} value={at} placeholder={String(tick + 1)} data-testid="studio-model-plan-tick"
          onChange={(event) => setAt(event.target.value)}/>
      </label>
      <button type="button" className="studio-model-telemetry__button" data-testid="studio-model-plan" onClick={plan}>Uložit jako plánovaný incident</button>
    </div>
    {error && <p className="studio-model-telemetry__error" role="alert">{error}</p>}
    {planned.length > 0 && <ul className="studio-model-telemetry__plan" data-testid="studio-model-plan-list">
      {planned.map(({ index, incident }) => <li key={`${index}-${incident.kind}`} className="studio-model-telemetry__plan-row">
        tick {incident.tick} · {INCIDENT_LABELS[incident.kind]}
        <button type="button" className="studio-model-telemetry__remove" onClick={() => actions.onUnplan(index, nodeId)} aria-label={`Odebrat plán tick ${incident.tick}`}>×</button>
      </li>)}
    </ul>}
  </section>;
}
