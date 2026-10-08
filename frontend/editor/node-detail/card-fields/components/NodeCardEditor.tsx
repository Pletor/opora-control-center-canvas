// Karta existujícího uzlu v záložce Zadání: tatáž pole jako v pop-upu tvorby — vrstva jako řada čipů
// a pod ní pole pro agenta (stav, model, effort, termín). Rozepsanou kartu drží u sebe; „Uložit kartu“ ohlásí celý uzel nahoru přes onSave a rodič (App)
// uloží graf. Prázdná karta klíč `card` z uzlu odstraní; ostatní pole uzlu zůstanou, jak byla.
import { useEffect, useRef, useState } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import AgentFields from "@/editor/canvas/create-dialog/components/AgentFields";
import DesignEditor from "./DesignEditor";
import ChecksEditor from "./ChecksEditor";
import ScenarioEditor from "./ScenarioEditor";
import LayerChips from "@/editor/canvas/create-dialog/components/LayerChips";
import { cardDraftOf, sameCardDraft } from "@/editor/canvas/create-dialog/logic/card-draft";
import { withCard } from "@/shared/card-context/logic/card-context";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/editor/node-detail/card-fields/styles/card-fields.css";

export default function NodeCardEditor({
  node,
  readOnly,
  busy,
  onSave,
}: {
  node: CanvasNode;
  readOnly: boolean;
  busy: boolean;
  onSave: (node: CanvasNode) => void;
}) {
  const stored = cardDraftOf(node.card);
  const [draft, setDraft] = useState(stored);
  const previousStored = useRef(stored);
  const storedKey = JSON.stringify(stored);
  useEffect(() => {
    const previous = previousStored.current;
    previousStored.current = stored;
    setDraft((value) => sameCardDraft(value, previous) ? stored : value);
  }, [storedKey]);
  const dirty = !sameCardDraft(draft, stored);
  const changed = useRef(dirty); changed.current = dirty;
  useScopedSaveParticipant({ id: `card-fields:${node.id}`, label: `Nastavení karty: ${node.name}`,
    dirty, isDirty: () => changed.current, blocked: readOnly ? "Karta je pouze ke čtení." : undefined,
    flush: () => confirmSavedChange(() => onSave(withCard(node, draft)), () => changed.current) });
  return (
    <section className="card-fields" aria-label="Karta uzlu">
      <h3>Karta</h3>
      <p className="card-fields__note">Vrstva, ruční stav a doporučení pro agenta. Stav „hotovo“ dává jen uzavření karty.</p>
      <LayerChips value={draft} disabled={readOnly || busy} onChange={setDraft} />
      <AgentFields value={draft} disabled={readOnly || busy} onChange={setDraft} />
      <DesignEditor key={node.id} node={node} disabled={readOnly || busy} onSave={onSave} />
      <ChecksEditor key={`checks:${node.id}`} node={node} disabled={readOnly || busy} onSave={onSave} />
      <ScenarioEditor key={`scenario:${node.id}`} node={node} disabled={readOnly || busy} onSave={onSave} />
      {!readOnly && dirty && (
        <button type="button" className="card-fields__save" disabled={busy} onClick={() => onSave(withCard(node, draft))}>
          Uložit kartu
        </button>
      )}
    </section>
  );
}
