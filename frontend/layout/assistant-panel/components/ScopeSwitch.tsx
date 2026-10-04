import type { AssistantScope } from "../logic/assistant-api";
import { SCOPE_LABEL, selectionLabel } from "../logic/work-scope";

const OPTIONS: { scope: AssistantScope; hint: string }[] = [
  { scope: "selection", hint: "Jen vybrané uzly do hloubky; navazující uzly asistent jen propojí vazbou" },
  { scope: "board", hint: "Asistent pracuje samostatně nad celým plátnem" },
];

/**
 * Přepínač rozsahu práce u pole zprávy (docs/asistent.md §6.1). Volbu drží rodič jako preferenci
 * aplikace; dílek ji jen ukazuje a hlásí změnu. V módu Výběr vedle stojí, kolik uzlů je vybráno.
 */
export default function ScopeSwitch({
  scope,
  selectedCount,
  onScope,
}: {
  scope: AssistantScope;
  selectedCount: number;
  onScope: (scope: AssistantScope) => void;
}) {
  return (
    <div className="assistant-panel__scope">
      <div className="assistant-panel__scope-options" role="group" aria-label="Rozsah práce asistenta">
        {OPTIONS.map((o) => (
          <button
            key={o.scope}
            type="button"
            className={"assistant-panel__scope-option" + (o.scope === scope ? " assistant-panel__scope-option--on" : "")}
            aria-pressed={o.scope === scope}
            title={o.hint}
            onClick={() => onScope(o.scope)}
          >
            {SCOPE_LABEL[o.scope]}
          </button>
        ))}
      </div>
      {scope === "selection" && (
        <span
          className={"assistant-panel__scope-count" + (selectedCount ? "" : " assistant-panel__scope-count--empty")}
          aria-live="polite"
        >
          {selectionLabel(selectedCount)}
        </span>
      )}
    </div>
  );
}
