import { useEffect, useRef, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import { safeDesignUrl } from "@/editor/canvas/node-card/components/CardDesign";

const draftOf = (node: CanvasNode) => ({ artifactUrl: node.design?.artifactUrl ?? "", version: node.design?.version ?? "", previewUrl: node.design?.previewUrl ?? "" });
export default function DesignEditor({ node, disabled, onSave }: {
  node: CanvasNode; disabled: boolean; onSave: (node: CanvasNode) => void;
}) {
  const stored = JSON.stringify(draftOf(node));
  const [draft, setDraft] = useState(() => draftOf(node));
  const previous = useRef(stored);
  useEffect(() => {
    const old = previous.current; previous.current = stored;
    setDraft(value => JSON.stringify(value) === old ? JSON.parse(stored) : value);
  }, [stored]);
  const dirty = JSON.stringify(draft) !== stored;
  const empty = !draft.artifactUrl && !draft.version && !draft.previewUrl;
  const valid = empty || (safeDesignUrl(draft.artifactUrl) && !!draft.version.trim() &&
    draft.version.length <= 200 && !/[\u0000-\u001f]/.test(draft.version) && (!draft.previewUrl || safeDesignUrl(draft.previewUrl)));
  const changed = useRef(dirty); changed.current = dirty;
  const save = () => {
    if (!valid || disabled) return;
    const { design: _old, ...rest } = node;
    onSave(empty ? rest : { ...rest, design: { artifactUrl: draft.artifactUrl, version: draft.version,
      ...(draft.previewUrl ? { previewUrl: draft.previewUrl } : {}) } });
  };
  useScopedSaveParticipant({ id: `design:${node.id}`, label: `Návrh: ${node.name}`, dirty,
    isDirty: () => changed.current,
    blocked: disabled ? "Návrh nyní nelze uložit." : !valid ? "Vyplňte platný odkaz a verzi návrhu." : undefined,
    flush: () => confirmSavedChange(save, () => changed.current) });
  return <fieldset disabled={disabled}>
    <legend>Návrh rozhraní</legend>
    {([["artifactUrl", "Odkaz na návrh"], ["version", "Verze návrhu"], ["previewUrl", "Odkaz na obrázek náhledu (volitelný)"]] as const).map(([key, label]) =>
      <label key={key} style={{ display: "block" }}>{label}
        <input value={draft[key]} type={key === "version" ? "text" : "url"} maxLength={key === "version" ? 200 : 2048}
          onChange={event => setDraft({ ...draft, [key]: event.target.value })} />
      </label>)}
    {!valid && <p role="alert">Vyplňte úplný HTTP(S) odkaz a verzi; pro odebrání vymažte všechna pole.</p>}
    {dirty && <button type="button" disabled={!valid} onClick={save}>Uložit návrh</button>}
  </fieldset>;
}
