// Pole karty „Pro agenta“: ruční stav, doporučený model, effort a termín ve dvou sloupcích
// (docs/kontext-karet-a-index.md §1). Dílek nic neukládá ani nenormalizuje — ukáže rozepsanou kartu
// a každou změnu ohlásí celou nahoru přes onChange. Pop-up tvorby ho balí do sbalitelné sekce,
// detail karty ho ukazuje rovnou.
import type { CardDraft } from "@/editor/canvas/create-dialog/logic/card-draft";
import { CARD_EFFORTS, CARD_MODELS, CARD_STATUSES } from "@/shared/card-context/logic/card-context";
import "@/editor/canvas/create-dialog/styles/create-dialog.css";

const STATUS_LABEL: Record<string, string> = { draft: "Rozpracovaná (draft)", ready: "Připravená (ready)" };
const MODEL_LABEL: Record<string, string> = { fable: "Fable", opus: "Opus", sonnet: "Sonnet", haiku: "Haiku" };

type Choice = { key: "status" | "model" | "effort"; label: string; options: string[]; names?: Record<string, string> };
const CHOICES: Choice[] = [
  { key: "status", label: "Stav", options: CARD_STATUSES, names: STATUS_LABEL },
  { key: "model", label: "Model", options: CARD_MODELS, names: MODEL_LABEL },
  { key: "effort", label: "Effort", options: CARD_EFFORTS },
];

export default function AgentFields({
  value,
  disabled = false,
  onChange,
}: {
  value: CardDraft;
  disabled?: boolean;
  onChange: (next: CardDraft) => void;
}) {
  return (
    <div className="create-dialog__agent" role="group" aria-label="Pro agenta">
      {CHOICES.map((choice) => (
        <label key={choice.key} className="field create-dialog__agent-field">
          {choice.label}
          <select
            aria-label={choice.label}
            value={value[choice.key]}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, [choice.key]: e.target.value })}
          >
            <option value="">Neurčeno</option>
            {choice.options.map((option) => (
              <option key={option} value={option}>{choice.names?.[option] ?? option}</option>
            ))}
          </select>
        </label>
      ))}
      <label className="field create-dialog__agent-field">
        Termín
        <input
          type="date"
          aria-label="Termín"
          value={value.due}
          disabled={disabled}
          onChange={(e) => onChange({ ...value, due: e.target.value })}
        />
      </label>
    </div>
  );
}
