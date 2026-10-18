// Překryv skici momentu přes plátno módu Storyboard: nahoře titulek a tlačítka, pod nimi Excalidraw (DrawingWorkspace)
// ve vrstvě `sb/<karta>/<moment>` s podkladem snímku. Dílek nic neukládá; export skici a zápis do storyboardu dělá rodič.
// V režimu jen pro čtení (Main) se místo kreslení ukáže uložené PNG skici.
import { useMemo, useState } from "react";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import DrawingWorkspace from "@/editor/canvas/drawing/components/DrawingWorkspace";
import type { DrawingTool } from "@/editor/canvas/drawing/logic/drawing-state";
import { readSettings } from "@/shared/surface-settings/logic/workspace-settings";

export default function SketchOverlay({ project, workspace, layer, title, backdrop, readOnly, image, busy, message, onApi, onSaved, onExport, onClose }: {
  project: string;
  workspace: string;
  layer: string;
  title: string;
  /** Snímek animace a skica předchozího momentu; v kresbě se při otevření vymění za čerstvé. */
  backdrop: ExcalidrawElement[];
  readOnly: boolean;
  /** Uložená skica (PNG) pro režim jen ke čtení. */
  image?: HTMLImageElement | null;
  busy: boolean;
  message: string;
  onApi: (api: ExcalidrawImperativeAPI | null) => void;
  /** Scéna kresby byla uložena na server; rodič z ní udělá PNG a zapíše `moment.sketch`. */
  onSaved: () => void;
  /** Znovu vyexportovat aktuální (uloženou) scénu do PNG bez nového uložení kresby. */
  onExport: () => void;
  onClose: () => void;
}) {
  const [tool, setTool] = useState<DrawingTool>("selection");
  const settings = useMemo(() => readSettings(), []);
  return (
    <div className="storyboard__sketch" role="dialog" aria-label={title}>
      <div className="storyboard__sketch-bar">
        <strong>{title}</strong>
        <span role="status">{message}</span>
        {!readOnly && <button type="button" className="primary" disabled={busy} onClick={onExport} title="Vyexportuje kresbu do PNG skici momentu. Po uložení kresby (Uložit kresbu) se to udělá samo.">Uložit skicu</button>}
        <button type="button" onClick={onClose}>Zavřít</button>
      </div>
      {readOnly
        ? <div className="storyboard__sketch-view">{image ? <img src={image.src} alt={title} /> : <p>Moment zatím nemá skicu.</p>}</div>
        : <DrawingWorkspace project={project} workspace={workspace} layer={layer} tool={tool} toolSequence={0} settings={settings}
            onTool={setTool} onReady={() => undefined} initialBackdrop={backdrop} onApi={onApi} onSaved={onSaved} />}
    </div>
  );
}
