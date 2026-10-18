import { useEffect, useRef, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";

const draftOf = (node: CanvasNode) => ({ checks: node.checks ?? [], goal_mode: node.goal_mode ?? "manual" });
export default function ChecksEditor({ node, disabled, onSave }: { node: CanvasNode; disabled: boolean; onSave: (node: CanvasNode) => void }) {
  const stored = JSON.stringify(draftOf(node));
  const [draft, setDraft] = useState(() => draftOf(node));
  const previous = useRef(stored);
  useEffect(() => { const old = previous.current; previous.current = stored;
    setDraft(value => JSON.stringify(value) === old ? JSON.parse(stored) : value);
  }, [stored]);
  const dirty = JSON.stringify(draft) !== stored;
  const valid = draft.checks.length <= 200 && new Set(draft.checks.map(c => c.id)).size === draft.checks.length
    && draft.checks.every(c => /^[A-Za-z0-9_-]{1,80}$/.test(c.id) && !!c.command.trim() && c.command.length <= 4000 && !c.command.includes("\0"))
    && (draft.goal_mode !== "until_checks_pass" || draft.checks.length > 0);
  const changed = useRef(dirty); changed.current = dirty;
  const save = () => { if (valid && !disabled) onSave({ ...node, ...draft }); };
  useScopedSaveParticipant({ id: `checks:${node.id}`, label: `Kontroly: ${node.name}`, dirty, isDirty: () => changed.current,
    blocked: disabled ? "Kontroly nyní nelze uložit." : !valid ? "Vyplňte jedinečná ID a příkazy kontrol." : undefined,
    flush: () => confirmSavedChange(save, () => changed.current) });
  return <fieldset disabled={disabled}><legend>Kontroly a GOAL</legend>
    <label>Režim <select value={draft.goal_mode} onChange={e => setDraft({ ...draft, goal_mode: e.target.value as typeof draft.goal_mode })}>
      <option value="manual">Ruční dokončení</option><option value="until_checks_pass">GOAL: do úspěchu všech kontrol</option>
    </select></label>
    <p>Příkazy se uložením nespouštějí. Výsledky zapisujte do důkazů dokončení pod stejným ID.</p>
    {draft.checks.map((check, index) => <div key={index}>
      <input aria-label={`ID kontroly ${index + 1}`} value={check.id} maxLength={80} onChange={e => setDraft({ ...draft, checks: draft.checks.map((c, i) => i === index ? { ...c, id: e.target.value } : c) })} />
      <input aria-label={`Příkaz kontroly ${index + 1}`} value={check.command} maxLength={4000} onChange={e => setDraft({ ...draft, checks: draft.checks.map((c, i) => i === index ? { ...c, command: e.target.value } : c) })} />
      <button type="button" onClick={() => setDraft({ ...draft, checks: draft.checks.filter((_, i) => i !== index) })}>Odebrat</button>
    </div>)}
    <button type="button" disabled={draft.checks.length >= 200} onClick={() => setDraft({ ...draft, checks: [...draft.checks, { id: "", command: "" }] })}>Přidat kontrolu</button>
    {!valid && <p role="alert">Každá kontrola potřebuje jedinečné ID a příkaz; GOAL potřebuje alespoň jednu kontrolu.</p>}
    {dirty && <><button type="button" disabled={!valid} onClick={save}>Uložit kontroly</button><button type="button" onClick={() => setDraft(draftOf(node))}>Zrušit změny kontrol</button></>}
  </fieldset>;
}
