import { MODELS, type AssistantModel } from "../logic/assistant-api";

const EXAMPLES = [
  "Co je na plátně hotové a co ještě chybí?",
  "Které karty nemají úplné zadání pro agenta?",
  "/grill-me Chci přidat export projektu do PDF.",
];

/**
 * Prázdný asistent: jedna věta, co tu jde dělat, tlačítko „+ Nový úkol“ a tři příklady otázek.
 * Klik na příklad založí úkol a otázku předvyplní do pole; odeslat ji musí uživatel sám.
 */
export default function TasksEmpty({
  withCreate,
  model,
  onModel,
  onCreate,
  onExample,
}: {
  /** Na celé ploše je „+ Nový úkol“ už ve sloupci úkolů; podruhé se neukazuje. */
  withCreate: boolean;
  model: AssistantModel;
  onModel: (model: AssistantModel) => void;
  onCreate: () => void;
  onExample: (text: string) => void;
}) {
  return (
    <div className="assistant-panel__empty">
      <p className="assistant-panel__empty-lead">
        Každý úkol je samostatná konverzace s Claude Code nad tímto projektem.
        Asistent čte plátno a radí, nic nezapisuje.
      </p>
      {withCreate && (
        <span className="assistant-panel__new">
          <select
            className="assistant-panel__model"
            aria-label="Model nového úkolu"
            title="Model nového úkolu"
            value={model}
            onChange={(e) => onModel(e.target.value as AssistantModel)}
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="assistant-panel__new-task"
            onClick={onCreate}
          >
            + Nový úkol
          </button>
        </span>
      )}
      <p className="assistant-panel__empty-label">
        {withCreate ? "Nebo začněte otázkou:" : "Začněte otázkou:"}
      </p>
      <ul className="assistant-panel__examples">
        {EXAMPLES.map((text) => (
          <li key={text} className="assistant-panel__example-row">
            <button
              type="button"
              className="assistant-panel__example"
              onClick={() => onExample(text)}
            >
              {text}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
