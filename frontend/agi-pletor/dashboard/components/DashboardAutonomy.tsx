import "../styles/pletor-dashboard-autonomy.css";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { AgentAutonomyApi } from "@/shared/agent-autonomy/logic/use-agent-autonomy";
import { sinceLabel } from "@/shared/agent-autonomy/logic/agent-autonomy";
import { autonomyVerdict, waitingForHuman, type WaitingItem } from "../logic/autonomy-waiting";

/**
 * Autonomie (`?part=autonomie`): jedno ovládání pro otevřený projekt. Přepínač zapíše plnou autonomii agentů
 * i průchod bránou mozku; pod ním je, co v agent-state ještě čeká na člověka a proč. Stav drží a ukládá App.
 */
export default function DashboardAutonomy({ project, workspace, autonomy }: { project: string; workspace: string; autonomy: AgentAutonomyApi }) {
  const [waiting, setWaiting] = useState<WaitingItem[] | null>(null);
  const [readError, setReadError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const load = useCallback(() => {
    const query = new URLSearchParams({ project, workspace });
    return api<unknown>("/api/oporahub/agent-state?" + query).then(
      (state) => { setWaiting(waitingForHuman(state)); setReadError(""); },
      (e: unknown) => setReadError(e instanceof Error ? e.message : "Načtení stavu agentů selhalo."));
  }, [project, workspace]);
  useEffect(() => { setWaiting(null); void load(); }, [load]);
  const { autonomy: state, gate, loading, saving, error } = autonomy;
  const on = state.full && (!gate.on || gate.passes);
  const toggle = async (next: boolean) => { setConfirming(false); await autonomy.setAutonomous(next); await load(); };
  const since = sinceLabel(state.since);
  return (
    <section className="pletor-autonomy" aria-labelledby="pletor-autonomy-title">
      <h2 id="pletor-autonomy-title" className="pletor-dashboard__group-title">Plná autonomie projektu</h2>
      <p className={"pletor-autonomy__verdict" + (on ? " pletor-autonomy__verdict--on" : "")} role="status">
        {loading ? "Načítám…" : autonomyVerdict(state.full, gate)}
      </p>
      <dl className="pletor-autonomy__facts">
        <dt>Autonomie agentů</dt><dd>{state.full ? "zapnuto" + (since ? ` od ${since}` : "") : "vypnuto"}</dd>
        <dt>Brána mozku</dt><dd>{gate.on ? "zapnutá" : "vypnutá"}</dd>
        <dt>Průchod bránou</dt><dd>{gate.passes ? "agent projde" : "jen člověk a srdce"}</dd>
      </dl>
      {on ? (
        <button type="button" className="pletor-dashboard__button" disabled={loading || saving} onClick={() => void toggle(false)}>
          {saving ? "Ukládám…" : "Vypnout plnou autonomii"}
        </button>
      ) : !confirming ? (
        <button type="button" className="pletor-dashboard__button pletor-autonomy__start" disabled={loading || saving} onClick={() => setConfirming(true)}>
          Zapnout plnou autonomii
        </button>
      ) : (
        <div className="pletor-autonomy__confirm" role="alertdialog" aria-label="Potvrzení plné autonomie">
          <p>Agenti v projektu budou přijímat, uzavírat karty a slučovat bez tebe, i za zapnutou bránou mozku. Záznam činnosti dál říká, že to byl agent.</p>
          <button type="button" className="pletor-dashboard__button pletor-autonomy__start" disabled={saving} onClick={() => void toggle(true)}>Zapnout</button>
          <button type="button" className="pletor-dashboard__button" disabled={saving} onClick={() => setConfirming(false)}>Zrušit</button>
        </div>
      )}
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      <h2 className="pletor-dashboard__group-title">Co ještě čeká na člověka{waiting ? ` (${waiting.length})` : ""}</h2>
      {readError && <p className="pletor-dashboard__error" role="alert">{readError}</p>}
      {waiting && waiting.length === 0 && <p className="pletor-dashboard__note">Nic. Agenti mají volnou cestu.</p>}
      {waiting && waiting.length > 0 && (
        <table className="pletor-dashboard__table">
          <thead><tr><th>Co</th><th>Cíl</th><th>Proč čeká</th></tr></thead>
          <tbody>{waiting.map((item) => <tr key={item.id}><td>{item.what}</td><td><code>{item.target}</code></td><td>{item.reason}</td></tr>)}</tbody>
        </table>
      )}
      <button type="button" className="pletor-dashboard__button" onClick={() => void load()}>Obnovit</button>
    </section>
  );
}
