import { MODELS, type AssistantModel, type AssistantSession } from "../logic/assistant-api";
import { isBusy, type SessionState } from "../logic/assistant-events";

/** Záložky session projektu, výběr modelu pro novou session a tlačítko „+ Nová session“. */
export default function SessionTabs({
  sessions,
  activeId,
  activeState,
  model,
  onSelect,
  onClose,
  onModel,
  onCreate,
}: {
  sessions: AssistantSession[];
  activeId: string | null;
  activeState: SessionState;
  model: AssistantModel;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onModel: (model: AssistantModel) => void;
  onCreate: () => void;
}) {
  return (
    <div className="assistant-panel__tabs">
      <div className="assistant-panel__tablist" role="tablist" aria-label="Session asistenta">
        {sessions.map((s, i) => {
          const active = s.id === activeId;
          const state = active ? activeState : s.state;
          return (
            <span key={s.id} className={"assistant-panel__tab" + (active ? " assistant-panel__tab--active" : "")}>
              <button type="button" role="tab" aria-selected={active} className="assistant-panel__tab-name" onClick={() => onSelect(s.id)} title={s.title || `Session ${i + 1}`}>
                {isBusy(state) && <span className="assistant-panel__dot" aria-label="pracuje" />}
                {s.title || `Session ${i + 1}`}
              </button>
              <button type="button" className="assistant-panel__tab-close" aria-label="Zavřít session" title="Zavřít session" onClick={() => onClose(s.id)}>×</button>
            </span>
          );
        })}
      </div>
      <div className="assistant-panel__new">
        <select className="assistant-panel__model" aria-label="Model nové session" value={model} onChange={(e) => onModel(e.target.value as AssistantModel)}>
          {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <button type="button" className="assistant-panel__new-button" onClick={onCreate}>+ Nová session</button>
      </div>
    </div>
  );
}
