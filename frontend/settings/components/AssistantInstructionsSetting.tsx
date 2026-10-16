import { INSTRUCTIONS_LIMIT, instructionsView, type AssistantInstructions } from "@/settings/logic/assistant-instructions";

/**
 * Pole „Pokyny asistenta“. Dostává stav ze serveru a rozepsaný text v props, každou změnu hlásí
 * nahoru; ukládá rodič (AssistantSection).
 */
export default function AssistantInstructionsSetting({ config, draft, saving, error, onDraftChange, onSave, onReset }: {
  config: AssistantInstructions | null;
  draft: string;
  saving: boolean;
  error: string;
  onDraftChange: (text: string) => void;
  onSave: () => void;
  onReset: () => void;
}) {
  const view = instructionsView(config, draft);
  return (
    <div className="assistant-instructions">
      <textarea
        className="assistant-instructions__textarea"
        aria-label="Pokyny asistenta"
        value={draft}
        disabled={!config}
        spellCheck={false}
        onChange={(event) => onDraftChange(event.target.value)}
      />
      <div className="assistant-instructions__meta">
        <span>{view.detail}</span>
        <span className={view.overLimit ? "assistant-instructions__count--over" : undefined}>
          {view.chars} / {INSTRUCTIONS_LIMIT} znaků
        </span>
      </div>
      <div className="assistant-instructions__actions">
        <button type="button" disabled={!view.dirty || view.overLimit || saving} onClick={onSave}>Uložit</button>
        <button type="button" disabled={!config || config.isDefault || saving} onClick={onReset}>Obnovit výchozí</button>
      </div>
      {error && <span className="assistant-instructions__error" role="alert">{error}</span>}
    </div>
  );
}
