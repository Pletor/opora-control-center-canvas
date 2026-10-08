import { useRef, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

export default function MemoryItemText({ id, text, disabled, save, actionLabel = "Upravit" }: {
  id: string; text: string; disabled: boolean; save: (text: string) => Promise<boolean>; actionLabel?: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const original = useRef(text);
  const submit = useRef(save);
  useScopedSaveParticipant({ id: `memory-item:${id}`, label: "Položka paměti", dirty: draft !== null && draft !== original.current,
    blocked: "Uložte nebo zrušte rozepsanou položku paměti." });
  return draft === null ? <>
    <span>{text}</span>
    <button type="button" disabled={disabled} onClick={() => { original.current = text; submit.current = save; setDraft(text); }}>{actionLabel}</button>
  </> : <>
    <textarea aria-label="Text položky paměti" value={draft} disabled={disabled} onChange={(e) => setDraft(e.target.value)} />
    <button type="button" disabled={disabled || !draft.trim()} onClick={async () => {
      if (await submit.current(draft.trim())) setDraft(null);
    }}>Uložit</button>
    <button type="button" disabled={disabled} onClick={() => setDraft(null)}>Zrušit</button>
  </>;
}
