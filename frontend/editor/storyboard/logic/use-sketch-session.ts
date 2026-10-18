// Sezení skici jednoho momentu: otevření (snímek `t` → PNG → podklad), export PNG po uložení scény a zápis
// `moment.sketch` do storyboardu. Drží ho StoryboardEditor; Excalidraw a scénu spravuje DrawingWorkspace v překryvu.
import { useCallback, useRef, useState } from "react";
import { exportToBlob } from "@excalidraw/excalidraw";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type { AnimationDef } from "./animations";
import { backdropElements, previousSketchFileId, sketchLayer } from "./sketch-backdrop";
import { renderFrameBlob, uploadPng } from "./sketch-files";
import { updateMoment, validate, type Storyboard } from "./storyboard-model";

export type SketchSession = { momentId: string; layer: string; title: string; backdrop: ExcalidrawElement[] };

export function useSketchSession({ project, workspace, nodeId, board, animation, onBoard, onSave }: {
  project: string;
  workspace: string;
  nodeId: string;
  board: Storyboard | null;
  animation: AnimationDef | undefined;
  /** Koncept se změnil (nový `moment.sketch`). */
  onBoard: (board: Storyboard) => void;
  /** Uloží storyboard; true při úspěchu. */
  onSave: (board: Storyboard) => Promise<boolean>;
}) {
  const [session, setSession] = useState<SketchSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const editor = useRef<ExcalidrawImperativeAPI | null>(null);
  const latest = useRef({ board, onBoard, onSave });
  latest.current = { board, onBoard, onSave };

  const open = useCallback(async (index: number) => {
    const current = latest.current.board;
    const moment = current?.moments[index];
    if (!current || !animation || !moment?.id || busy) return;
    setBusy(true); setMessage("Připravuji snímek…");
    try {
      const frameFileId = await uploadPng(project, workspace, await renderFrameBlob(current, animation, moment.t));
      const backdrop = backdropElements({ frameFileId, prevSketchFileId: previousSketchFileId(current.moments, index), width: current.size.w, height: current.size.h });
      setSession({ momentId: moment.id, layer: sketchLayer(nodeId, moment.id), title: `Skica momentu ${moment.t} s · ${moment.title || "bez názvu"}`, backdrop: backdrop as unknown as ExcalidrawElement[] });
      setMessage("");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [project, workspace, nodeId, animation, busy]);

  /** Vyexportuje scénu do PNG, nahraje ji a zapíše `moment.sketch` i do uloženého storyboardu. */
  const exportSketch = useCallback(async () => {
    const api = editor.current;
    const open = session;
    if (!api || !open) return;
    // Scéna a stav editoru se čtou hned; po uložení kresba znovu načítá a editor se na okamžik odpojí.
    const elements = api.getSceneElements().filter((element) => !element.isDeleted);
    const appState = { ...api.getAppState(), exportBackground: true };
    const files = api.getFiles();
    setBusy(true); setMessage("Ukládám skicu…");
    try {
      const fileId = await uploadPng(project, workspace, await exportToBlob({ elements, appState, files, mimeType: "image/png", exportPadding: 0 }));
      const { board: now, onBoard: setBoard, onSave: save } = latest.current;
      const index = now?.moments.findIndex((m) => m.id === open.momentId) ?? -1;
      if (!now || index < 0) throw new Error("Moment už ve storyboardu není.");
      const next = updateMoment(now, index, { sketch: { layer: open.layer, fileId, imageStale: false } }).board;
      const errors = validate(next);
      if (errors.length) throw new Error(errors[0]);
      setBoard(next);
      setMessage(await save(next) ? "Skica uložena." : "Skicu se nepodařilo zapsat do storyboardu.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [session, project, workspace]);

  const close = useCallback(() => { editor.current = null; setSession(null); setMessage(""); }, []);
  const onApi = useCallback((api: ExcalidrawImperativeAPI | null) => { editor.current = api; }, []);
  return { session, busy, message, open, exportSketch, close, onApi };
}
