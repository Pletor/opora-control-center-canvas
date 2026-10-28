// Přepínač „Plná autonomie agentů“ v nastavení projektu. Zapnutí chce jedno potvrzení navíc (agent pak smí
// skoro všechno); vypnutí je okamžité. Volbu hlásí `onChange` nahoru, ukládá rodič (hned, mimo revizi nastavení).
import { useEffect, useState } from "react";
import { sinceLabel, type AgentAutonomy } from "../logic/agent-autonomy";
import "../styles/agent-autonomy.css";

export default function AgentAutonomySwitch({ autonomy, disabled, saving, error, onChange }: {
  autonomy: AgentAutonomy;
  disabled: boolean;
  saving: boolean;
  error: string;
  onChange: (full: boolean) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  // Po uložení nebo změně stavu odjinud se rozpracované potvrzení zavře.
  useEffect(() => { setConfirming(false); }, [autonomy.full]);
  const since = sinceLabel(autonomy.since);
  const locked = disabled || saving;
  return (
    <div className={"agent-autonomy-switch" + (autonomy.full ? " agent-autonomy-switch--on" : "")} data-testid="agent-autonomy-switch">
      <label className="agent-autonomy-switch__row">
        <input type="checkbox" role="switch" className="agent-autonomy-switch__toggle" aria-label="Plná autonomie agentů"
          checked={autonomy.full || confirming} disabled={locked}
          onChange={(e) => { if (e.target.checked) setConfirming(true); else if (confirming) setConfirming(false); else onChange(false); }} />
        <span className="agent-autonomy-switch__label">Plná autonomie agentů</span>
        <span className="agent-autonomy-switch__state" role="status">
          {saving ? "Ukládám…" : autonomy.full ? "Zapnuto" + (since ? ` od ${since}` : "") + (autonomy.by ? ` · ${autonomy.by}` : "") : "Vypnuto"}
        </span>
      </label>
      <p className="agent-autonomy-switch__hint">
        Agent smí v projektu všechno co člověk kromě přístupu, připojení repozitáře/složky a klíčů.
        Záznam činnosti dál říká, že to udělal agent.
      </p>
      {confirming && !autonomy.full && (
        <div className="agent-autonomy-switch__confirm" role="alertdialog" aria-label="Potvrzení plné autonomie">
          <p>Opravdu svěřit agentům v tomto projektu plnou autonomii? Budou přijímat, uzavírat a commitovat bez tebe.</p>
          <button type="button" className="primary" disabled={locked} onClick={() => onChange(true)}>Zapnout plnou autonomii</button>
          <button type="button" disabled={locked} onClick={() => setConfirming(false)}>Zrušit</button>
        </div>
      )}
      {error && <p className="agent-autonomy-switch__error" role="alert">{error}</p>}
    </div>
  );
}
