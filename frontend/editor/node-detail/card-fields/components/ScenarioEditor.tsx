import { useEffect, useRef, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

export default function ScenarioEditor({ node, disabled, onSave }: { node: CanvasNode; disabled: boolean; onSave: (node: CanvasNode) => void }) {
  const stored = node.scenario?.command ?? "";
  const [command, setCommand] = useState(stored);
  const previous = useRef(stored);
  useEffect(() => { const old = previous.current; previous.current = stored; setCommand(value => value === old ? stored : value); }, [stored]);
  const dirty = command !== stored;
  const valid = !command || (!!command.trim() && command.length <= 4000 && !command.includes("\0"));
  const changed = useRef(dirty); changed.current = dirty;
  const save = () => { if (!valid || disabled) return;
    const { scenario: _old, ...rest } = node;
    onSave(command ? { ...rest, scenario: { command } } : rest);
  };
  useScopedSaveParticipant({ id: `scenario:${node.id}`, label: `Scénář brány: ${node.name}`, dirty, isDirty: () => changed.current,
    blocked: disabled ? "Scénář nyní nelze uložit." : !valid ? "Vyplňte platný příkaz scénáře." : undefined,
    flush: () => confirmSavedChange(save, () => changed.current) });
  return <fieldset disabled={disabled}><legend>Scénář brány</legend>
    <label>Příkaz E2E<textarea value={command} maxLength={4000} onChange={e => setCommand(e.target.value)} placeholder="uv run python -m e2e" /></label>
    <p>Prázdné pole scénář odebere. Uložení příkaz nespouští; agent odevzdá počty OK/FAIL a odkaz na log.</p>
    {dirty && <><button type="button" disabled={!valid} onClick={save}>Uložit scénář</button><button type="button" onClick={() => setCommand(stored)}>Zrušit</button></>}
  </fieldset>;
}
