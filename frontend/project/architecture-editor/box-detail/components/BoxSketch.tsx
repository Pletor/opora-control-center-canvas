import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { DrawingTool } from "@/editor/canvas/drawing/logic/drawing-state";
import { readSettings } from "@/shared/surface-settings/logic/workspace-settings";
import { useSketchPreview } from "../logic/use-sketch-preview";

// Excalidraw je velký: načte se až s prvním otevřením okna skici, jako v App.
const DrawingWorkspace = lazy(() => import("@/editor/canvas/drawing/components/DrawingWorkspace"));

type Props = {
  project: string; workspace: string; layer: string; title: string;
  /** Proč skicu nejde kreslit (zámek obsahu, Git main); `null` = jde. */
  lock: string | null;
  /** Kresba se uložila (nová revize); rodič obnoví značky boxu. */
  onSaved: () => void;
};

/** Skica boxu: náhled uložené kresby a Kreslit skicu, které otevře velké okno s existujícím kreslením (Excalidraw)
 * nad vrstvou `box/<pageId>/<sectionId>`. Ukládá samo kreslení (`/api/drawing`, revize, obrázky). Okno je obyčejná
 * vrstva (`div role=dialog`), ne `<dialog>`: nabídky Excalidraw se vykreslují do `body` a v top layeru by byly mrtvé. */
export default function BoxSketch({ project, workspace, layer, title, lock, onSaved }: Props) {
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState(0);
  const [tool, setTool] = useState<DrawingTool>("selection");
  const settings = useMemo(() => readSettings(), []);
  const preview = useSketchPreview(project, workspace, layer, version);
  useEffect(() => {
    if (!open) return;
    // Esc uvnitř kreslení patří Excalidraw (zruší výběr nástroje); okno zavře Esc mimo něj.
    const close = (event: KeyboardEvent) => { if (event.key === "Escape" && !(event.target instanceof Element && event.target.closest(".excalidraw"))) setOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);
  return <section className="box-detail__block" aria-label="Skica">
    <h4 className="box-detail__block-title">Skica</h4>
    {preview.src ? <img className="box-detail__sketch" src={preview.src} alt={`Skica: ${title}`}/>
      : <p className="box-detail__hint">{preview.loading ? "Načítám skicu…" : preview.error ? "Skicu se nepodařilo načíst." : "Box zatím nemá skicu."}</p>}
    <button type="button" className="box-detail__action" disabled={!!lock} data-testid="architecture-box-sketch" onClick={() => setOpen(true)}>✎ Kreslit skicu</button>
    {lock && <p className="box-detail__hint">{lock}</p>}
    {open && <div className="box-detail__modal" role="dialog" aria-label={`Skica: ${title}`} data-testid="architecture-box-sketch-dialog">
      <div className="box-detail__modal-bar">
        <strong className="box-detail__modal-title">Skica: {title}</strong>
        <button type="button" onClick={() => setOpen(false)}>Zavřít</button>
      </div>
      <div className="box-detail__modal-body">
        <Suspense fallback={<p className="box-detail__hint">Načítám kreslení…</p>}>
          <DrawingWorkspace project={project} workspace={workspace} layer={layer} tool={tool} toolSequence={0} settings={settings}
            onTool={setTool} onReady={() => undefined} onSaved={() => { setVersion((value) => value + 1); onSaved(); }}/>
        </Suspense>
      </div>
    </div>}
  </section>;
}
