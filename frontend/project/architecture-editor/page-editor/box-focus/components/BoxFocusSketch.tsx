import { lazy, Suspense, useMemo, useRef, useState } from "react";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { DrawingTool } from "@/editor/canvas/drawing/logic/drawing-state";
import { useDrawingFiles } from "@/editor/canvas/drawing/logic/use-drawing-files";
import { readSettings } from "@/shared/surface-settings/logic/workspace-settings";
import { useSketchPreview } from "../../../box-detail/logic/use-sketch-preview";
import { besideScene, inspirationSkeletons, notInScene } from "../logic/box-focus";

// Excalidraw je velký: načte se až s prvním zanořením do boxu.
const DrawingWorkspace = lazy(() => import("@/editor/canvas/drawing/components/DrawingWorkspace"));

type Props = {
  project: string; workspace: string; layer: string; title: string;
  /** Obrázky inspirace boxu (`fileId` z `/api/drawing-files`). */
  inspiration: readonly string[];
  /** `undefined` = přechodný stav (ukládání): platí poslední známý zámek, kresba se neodpojí. */
  lock: string | null | undefined; onSaved: () => void;
};

const naturalSize = (src: string) => new Promise<{ width: number; height: number }>((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
  image.onerror = () => reject(new Error("Obrázek inspirace se nepodařilo přečíst."));
  image.src = src;
});

/** Kresba skici boxu přes celou plochu: existující kreslení (`DrawingWorkspace`) nad vrstvou `box/<pageId>/<sectionId>`
 * a nad ním **Vložit inspiraci do kresby**, které obrázky inspirace boxu vloží jako obrázky Excalidraw (`fileId`), aby šla
 * stažená část webu graficky upravit. Pod zámkem obsahu (Git main, kompletní stránka) jen náhled a věta proč. */
export default function BoxFocusSketch({ project, workspace, layer, title, inspiration, lock, onSaved }: Props) {
  const [tool, setTool] = useState<DrawingTool>("selection");
  const settings = useMemo(() => readSettings(), []);
  const [editor, setEditor] = useState<ExcalidrawImperativeAPI | null>(null);
  const images = useDrawingFiles(project, workspace);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const known = useRef<string | null>(null);
  if (lock !== undefined) known.current = lock;
  if (known.current) return <LockedSketch project={project} workspace={workspace} layer={layer} title={title} lock={known.current}/>;
  async function insert() {
    if (!editor || busy) return;
    setBusy(true); setNote("");
    try {
      const scene = editor.getSceneElements();
      const ids = notInScene(inspiration, scene);
      if (!ids.length) { setNote("Všechny obrázky inspirace už v kresbě jsou."); return; }
      // `load` obrázky stáhne a označí jako nahrané: uložení kresby je podruhé neposílá.
      const loaded = await images.load(ids.map((fileId) => ({ type: "image", fileId })));
      const ready = ids.filter((id) => loaded.files[id]);
      const sizes = await Promise.all(ready.map((id) => naturalSize(loaded.files[id].dataURL)));
      const { convertToExcalidrawElements, CaptureUpdateAction } = await import("@excalidraw/excalidraw");
      editor.addFiles(ready.map((id) => loaded.files[id]));
      const added = convertToExcalidrawElements(inspirationSkeletons(ready.map((fileId, index) => ({ fileId, ...sizes[index] })), besideScene(scene)) as never);
      editor.updateScene({ elements: [...scene, ...added], captureUpdate: CaptureUpdateAction.IMMEDIATELY });
      editor.scrollToContent(added, { fitToContent: true });
      setNote(loaded.failed ? "Některé obrázky inspirace se nepodařilo načíst." : "Inspirace je v kresbě. Upravte ji a uložte kresbu.");
    } catch (cause) { setNote(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  return <section className="box-focus__stage" aria-label={`Skica: ${title}`}>
    <div className="box-focus__tools">
      <button type="button" className="box-focus__insert" disabled={!editor || busy || !inspiration.length} data-testid="architecture-box-focus-insert" onClick={() => void insert()}
        title={inspiration.length ? undefined : "Box nemá obrázky inspirace; přidáte je v Detailu boxu."}>🖼 Vložit inspiraci do kresby ({inspiration.length})</button>
      {note && <span className="box-focus__note" role="status">{note}</span>}
    </div>
    <div className="box-focus__drawing" data-testid="architecture-box-focus-drawing">
      <Suspense fallback={<p className="box-focus__hint">Načítám kreslení…</p>}>
        <DrawingWorkspace project={project} workspace={workspace} layer={layer} tool={tool} toolSequence={0} settings={settings}
          onTool={setTool} onReady={() => undefined} onApi={setEditor} onSaved={onSaved}/>
      </Suspense>
    </div>
  </section>;
}

/** Kresba pod zámkem: uložená skica jako obrázek a věta, proč ji teď nejde měnit; nikdy prázdná plocha. */
function LockedSketch({ project, workspace, layer, title, lock }: { project: string; workspace: string; layer: string; title: string; lock: string }) {
  const preview = useSketchPreview(project, workspace, layer, 0);
  return <section className="box-focus__stage box-focus__stage--locked" aria-label={`Skica: ${title}`} data-testid="architecture-box-focus-locked">
    <p className="box-focus__lock" role="note">Kresba je jen ke čtení. {lock}</p>
    {preview.src ? <img className="box-focus__preview" src={preview.src} alt={`Skica: ${title}`}/>
      : <p className="box-focus__hint">{preview.loading ? "Načítám skicu…" : preview.error ? "Skicu se nepodařilo načíst." : "Box zatím nemá skicu."}</p>}
  </section>;
}
