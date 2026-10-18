// Editor webové scény (záložka „Scéna“ vedle formuláře momentu): název, celý HTML dokument a pole a vrstvy jako JSON.
// „Použít“ zkontroluje tvar a externí zdroje a pošle hotový `SceneSpec` rodiči; iframe pak dokument načte znovu.
// Dílek nic neukládá, ukládá se stávajícím „Uložit“ storyboardu.
import { useEffect, useState } from "react";
import { parseSceneDraft } from "../logic/scene-document";
import type { SceneSpec } from "../logic/storyboard-model";

const toDraft = (scene: SceneSpec) => ({ html: scene.html, title: scene.title, fields: JSON.stringify(scene.fields, null, 2), layers: JSON.stringify(scene.layers, null, 2) });

export default function ScenePanel({ scene, readOnly, sceneError, onApply }: {
  scene: SceneSpec;
  readOnly: boolean;
  /** Chyba scény (externí zdroj, výjimka v seek, chyba stránky); ukáže se pod editorem. */
  sceneError: string;
  onApply: (scene: SceneSpec) => void;
}) {
  const [draft, setDraft] = useState(() => toDraft(scene));
  const [localError, setLocalError] = useState("");
  useEffect(() => { setDraft(toDraft(scene)); setLocalError(""); }, [scene]);
  const edit = (key: keyof typeof draft, value: string) => { setDraft({ ...draft, [key]: value }); setLocalError(""); };
  const apply = () => {
    const parsed = parseSceneDraft(draft);
    if ("error" in parsed) setLocalError(parsed.error); else onApply(parsed.scene);
  };
  const error = localError || sceneError;
  return (
    <div className="scene-panel">
      <label className="scene-panel__field">Název scény
        <input type="text" value={draft.title} maxLength={200} disabled={readOnly} onChange={(e) => edit("title", e.target.value)} />
      </label>
      <label className="scene-panel__field">Dokument scény (HTML: vrstvy data-layer, window.scene.seek(t, state), vše inline)
        <textarea className="scene-panel__html" value={draft.html} rows={24} spellCheck={false} disabled={readOnly} onChange={(e) => edit("html", e.target.value)} />
      </label>
      <label className="scene-panel__field">Pole stavu (fields, JSON) – v dokumentu jako CSS proměnné --klíč
        <textarea className="scene-panel__json" value={draft.fields} rows={6} spellCheck={false} disabled={readOnly} onChange={(e) => edit("fields", e.target.value)} />
      </label>
      <label className="scene-panel__field">Vrstvy (layers, JSON) – id odpovídá data-layer
        <textarea className="scene-panel__json" value={draft.layers} rows={4} spellCheck={false} disabled={readOnly} onChange={(e) => edit("layers", e.target.value)} />
      </label>
      <button type="button" className="primary" disabled={readOnly} onClick={apply}>Použít</button>
      {error && <p className="scene-panel__error" role="alert">{error}</p>}
    </div>
  );
}
