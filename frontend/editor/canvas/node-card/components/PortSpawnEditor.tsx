import { useState } from "react";
import type { BlockPortDef } from "@/shared/desktop-state/logic/types";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

export default function PortSpawnEditor({ port, blockId, disabled, onSave }: {
  port: BlockPortDef; blockId: string; disabled: boolean; onSave: (action: BlockPortDef["onMet"]) => void;
}) {
  const template = port.onMet?.template;
  const initial = { enabled: !!template, name: template?.name ?? "", purpose: template?.purpose ?? "", goal: template?.spec?.goal ?? "", acceptance: template?.spec?.acceptance ?? "", text: template?.text ?? "" };
  const [draft, setDraft] = useState(initial);
  // Klíč editoru je id portu, takže uloženou šablonu ze serveru převezme jen nerozepsaný editor.
  const [base, setBase] = useState(initial);
  if (JSON.stringify(base) !== JSON.stringify(initial)) {
    setBase(initial);
    if (JSON.stringify(draft) === JSON.stringify(base)) setDraft(initial);
  }
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);
  useScopedSaveParticipant({ id: `port-spawn:${blockId}:${port.id}`, label: `Navazující karta ${port.label}`,
    dirty, isDirty: () => dirty, blocked: "Uložte nebo zrušte rozepsanou šablonu navazující karty." });
  return <details className="nodrag nopan node-card__port-editor" data-dirty={dirty || undefined} onClick={e => e.stopPropagation()} onDoubleClick={e => e.stopPropagation()}>
    <summary title={template ? "Navazující karta je nastavená: vznikne, až bude blok splněný" : "Navazující karta: vznikne, až bude blok splněný"} aria-label="Navazující karta">{template ? "⤳+" : "⤳"}</summary>
    <label><input type="checkbox" disabled={disabled} checked={draft.enabled}
      onChange={e => setDraft({ ...draft, enabled: e.target.checked })} />Po splnění bloku vytvořit kartu</label>
    <p>Jednou pro tento port. Zamítnutý port kartu nevytvoří. Nastavte před splněním bloku.</p>
    {draft.enabled && <>
      {([['name', 'Název'], ['purpose', 'Účel'], ['goal', 'Cíl'], ['acceptance', 'Podmínky přijetí'], ['text', 'Zadání']] as const).map(([key, label]) =>
        <label key={key}>{label}<textarea aria-label={`${label} navazující karty`} disabled={disabled} value={draft[key]}
          onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>)}
    </>}
    {dirty && <><button type="button" disabled={disabled || (draft.enabled && !draft.name.trim())} onClick={() => onSave(draft.enabled ? {
      kind: "spawn", template: { ...template, name: draft.name.trim(), purpose: draft.purpose,
        spec: { ...template?.spec, goal: draft.goal, acceptance: draft.acceptance }, text: draft.text },
    } : undefined)}>Uložit šablonu</button><button type="button" onClick={() => setDraft(initial)}>Zrušit</button></>}
  </details>;
}
