import type { MilestoneFocus } from "../logic/milestone-focus";
import "../styles/milestone-focus.css";

type Props = { choices: MilestoneFocus[]; selected: string; milestone: MilestoneFocus | null; error: string | null;
  loading: boolean; select: (id: string) => void };

export default function MilestoneFocusControl({ choices, selected, milestone, error, loading, select }: Props) {
  return <div className="milestone-focus" data-testid="milestone-focus">
    <label className="milestone-focus__label">Aktivní milník
      <select value={selected} onChange={event => select(event.target.value)} aria-label="Aktivní milník">
        <option value="">{loading ? "Načítám…" : choices.length ? "Všechny prvky" : "Žádný aktivní milník"}</option>
        {choices.map(item => <option key={item.id} value={item.id}>{item.title} · {item.area}</option>)}
      </select>
    </label>
    {milestone && <span className="milestone-focus__evidence">
      {milestone.cards.length} dotčených prvků{milestone.closure === null ? "" : ` · Uzavření karet: ${milestone.closure} %`}
      <span title={milestone.verification?.verified ? `Běh Kanceláře; revize ${milestone.verification.acceptedRevision ?? ""}, commit ${milestone.verification.headSha ?? ""}. Zdroj: ${milestone.verification.source ?? "Kancelář"}. Nejde o nezávislé spuštění testů.` : "Přijetí návrhu nebo prototypu nedokládá funkční průchod."}>
        {milestone.verification?.verified ? "Integrační scénář doložen Kanceláří" : "Integrační ověření nedoloženo"}
      </span>
    </span>}
    {error && <span className="milestone-focus__error" role="alert">{error}</span>}
  </div>;
}
