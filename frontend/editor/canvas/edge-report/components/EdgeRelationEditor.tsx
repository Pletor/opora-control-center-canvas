import { useEffect, useRef, useState } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { MAX_RELATION_REASON, RELATION_LABELS, withEdgeRelation } from "@/editor/canvas/edge-report/logic/edge-relation";
import type { EdgeRelation, GraphEdge, InputRequirement } from "@/shared/types/logic/types";
import RequirementFields from "./RequirementFields";

export default function EdgeRelationEditor({ edge, readOnly, busy, onSave }: {
  edge: GraphEdge; readOnly: boolean; busy: boolean; onSave: (edge: GraphEdge) => void;
}) {
  const stored: { relation: EdgeRelation | ""; reason: string; requirement?: InputRequirement } = {
    relation: edge.relation ?? "", reason: edge.reason ?? "", requirement: edge.requirement };
  const [draft, setDraft] = useState(stored);
  const previous = useRef(stored);
  const storedKey = JSON.stringify(stored);
  useEffect(() => {
    const before = previous.current;
    previous.current = stored;
    setDraft(value => JSON.stringify(value) === JSON.stringify(before) ? stored : value);
  }, [storedKey]);
  const updated = () => withEdgeRelation(edge, draft.relation, draft.reason, draft.requirement);
  const next = updated();
  const dirty = next.relation !== edge.relation || next.reason !== edge.reason || JSON.stringify(next.requirement) !== JSON.stringify(edge.requirement);
  const changed = useRef(dirty); changed.current = dirty;
  useScopedSaveParticipant({ id: `edge-relation:${edge.id}`, label: "Význam vazby", dirty,
    isDirty: () => changed.current, blocked: readOnly ? "Vazba je pouze ke čtení." : undefined,
    flush: () => confirmSavedChange(() => onSave(updated()), () => changed.current) });
  return <section className="edge-report__fields" aria-label="Význam vazby">
    <label className="field">Význam vazby
      <select aria-label="Význam vazby" value={draft.relation} disabled={readOnly || busy}
        onChange={event => setDraft({ ...draft, relation: event.target.value as EdgeRelation | "", reason: event.target.value ? draft.reason : "" })}>
        <option value="">Neurčeno</option>
        {(Object.keys(RELATION_LABELS) as EdgeRelation[]).map(relation => <option key={relation} value={relation}>{RELATION_LABELS[relation]}</option>)}
      </select>
    </label>
    {draft.relation && <label className="field">Zdůvodnění vazby
      <textarea aria-label="Zdůvodnění vazby" value={draft.reason} maxLength={MAX_RELATION_REASON} rows={3}
        disabled={readOnly || busy} onChange={event => setDraft({ ...draft, reason: event.target.value })} />
    </label>}
    {draft.relation === "requires" && <p>Zdrojová karta vyžaduje cílovou kartu. Blokující závislosti nesmějí tvořit cyklus.</p>}
    {draft.relation === "requires" && <RequirementFields value={draft.requirement} disabled={readOnly || busy}
      onChange={requirement => setDraft({ ...draft, requirement })} />}
    {!readOnly && dirty && <button type="button" disabled={busy} onClick={() => onSave(updated())}>Uložit význam vazby</button>}
  </section>;
}
