import { MODELS, type AssistantModel } from "../logic/assistant-api";

/** „+ Nový úkol“ s výběrem modelu vedle; model se volí jen při založení úkolu. Volby hlásí nahoru. */
export default function NewTask({ model, onModel, onCreate }: { model: AssistantModel; onModel: (model: AssistantModel) => void; onCreate: () => void }) {
  return (
    <span className="assistant-panel__new">
      <select className="assistant-panel__model" aria-label="Model nového úkolu" title="Model nového úkolu" value={model} onChange={(e) => onModel(e.target.value as AssistantModel)}>
        {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <button type="button" className="assistant-panel__new-task" onClick={onCreate}>+ Nový úkol</button>
    </span>
  );
}
