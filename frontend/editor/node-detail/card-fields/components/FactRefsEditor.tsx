import { useEffect, useRef, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

export default function FactRefsEditor({ node, project, workspace, disabled, onSave }: {
  node: CanvasNode; project: string; workspace: string; disabled: boolean; onSave: (node: CanvasNode) => void;
}) {
  const { state, loading, error } = useDesktopState(project, workspace);
  const stored = JSON.stringify(node.factRefs ?? []);
  const [refs, setRefs] = useState(node.factRefs ?? []);
  const previous = useRef(stored);
  useEffect(() => { const old = previous.current; previous.current = stored; setRefs(value => JSON.stringify(value) === old ? JSON.parse(stored) : value); }, [stored]);
  const dirty = JSON.stringify(refs) !== stored;
  const changed = useRef(dirty); changed.current = dirty;
  const save = () => { if (!disabled) onSave({ ...node, factRefs: refs }); };
  useScopedSaveParticipant({ id: `facts:${node.id}`, label: `Odkazy na fakta: ${node.name}`, dirty, isDirty: () => changed.current,
    blocked: disabled ? "Odkazy nyní nelze uložit." : undefined, flush: () => confirmSavedChange(save, () => changed.current) });
  return <fieldset disabled={disabled || loading}><legend>Použitá fakta projektu</legend>
    <p>Hodnoty upravíte v panelu paměti projektu v sekci Fakta projektu. Karta ukládá jen odkazy.</p>
    {error && <p role="alert">{error}</p>}
    {state.settings.map(fact => <label key={fact.id} style={{ display: "block" }}><input type="checkbox" checked={refs.includes(fact.id)}
      onChange={e => setRefs(e.target.checked ? [...refs, fact.id] : refs.filter(id => id !== fact.id))} />{fact.key}: {fact.value}</label>)}
    {refs.filter(id => !state.settings.some(f => f.id === id)).map(id => <label key={id}><input type="checkbox" checked onChange={() => setRefs(refs.filter(ref => ref !== id))} />Chybějící fakt {id}</label>)}
    {!state.settings.length && !loading && <p>Zatím nejsou zapsaná fakta.</p>}
    {dirty && <><button type="button" onClick={save}>Uložit odkazy</button><button type="button" onClick={() => setRefs(node.factRefs ?? [])}>Zrušit</button></>}
  </fieldset>;
}
