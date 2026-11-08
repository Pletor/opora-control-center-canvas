import "../styles/pletor-brain-picker.css";
import { CLAUDE_EFFORTS, codexEfforts, type LlmModel } from "../logic/llm-settings";
import type { PletorBrain, PletorBrainKind } from "../logic/pletor-client";
import PletorEffortSelect from "./PletorEffortSelect";
import PletorLlmModelSelect from "./PletorLlmModelSelect";

type Props = {
  brain: PletorBrain; claude: LlmModel[]; codex: (LlmModel & { reasoning?: string[] })[];
  onChoose: (brain: PletorBrainKind, model?: string, effort?: string) => void;
};

const KINDS: [PletorBrainKind, string][] = [["claude", "Claude (předplatné)"], ["codex", "Codex (předplatné)"], ["ollama", "Lokální (Ollama)"]];
const EMPTY: Record<PletorBrainKind, string> = { claude: "výchozí", codex: "výchozí z Codexu", ollama: "bez modelu" };
const WHY: Record<PletorBrainKind, string> = {
  claude: "", codex: "Seznam modelů Codexu chybí (Codex nejede nebo se ještě načítá)", ollama: "Ollama nenabízí žádný model",
};

/**
 * Volba mozku Pletora: tři tlačítka Claude / Codex / Lokální a pod nimi výběr modelu zvoleného mozku. Dílek dostane
 * hotová data (`brain` ze stavu, modely Claude a Codexu z `/llm`) a každou volbu jen hlásí `onChoose(mozek, model?)`;
 * ukládá rodič. Vedle modelu Claude a Codexu je výběr effortu (`onChoose(mozek, undefined, effort)`, "" = výchozí), u Ollamy
 * se neukáže. Mozek bez nabídky modelů je zhasnutý a `title` říká proč (Claude zůstává vždy volitelný).
 */
export default function PletorBrainPicker({ brain, claude, codex, onChoose }: Props) {
  const options: Record<PletorBrainKind, LlmModel[]> = { claude, codex, ollama: brain.available.map((id) => ({ id, label: id })) };
  const current = brain.models[brain.brain] ?? "";
  const kind = brain.brain;
  const levels = kind === "claude" ? CLAUDE_EFFORTS : kind === "codex" ? codexEfforts(codex, current) : [];
  return (
    <div className="brain-picker">
      <div className="brain-picker__kinds" role="group" aria-label="Mozek Pletora">
        {KINDS.map(([kind, label]) => {
          const off = kind !== "claude" && options[kind].length === 0 && brain.brain !== kind;
          return (
            <button key={kind} type="button" className="brain-picker__kind" aria-pressed={brain.brain === kind} disabled={off}
              title={off ? WHY[kind] : undefined} onClick={() => onChoose(kind)}>{label}</button>
          );
        })}
      </div>
      <PletorLlmModelSelect className="brain-picker__model" label={`Model mozku ${brain.brain}`} models={options[brain.brain]} value={current}
        emptyLabel={EMPTY[brain.brain]} onChange={(model) => onChoose(brain.brain, model)} />
      {kind !== "ollama" && (
        <PletorEffortSelect className="brain-picker__model" label={`Effort mozku ${kind}`} levels={levels} value={brain.efforts[kind] ?? ""}
          onChange={(effort) => onChoose(kind, undefined, effort)} />
      )}
    </div>
  );
}
