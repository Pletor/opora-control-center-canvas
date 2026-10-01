import { useCallback, useEffect, useRef, useState } from "react";
import { Excalidraw, restoreElements, CaptureUpdateAction, newElementWith } from "@excalidraw/excalidraw";
import type { BinaryFiles, ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import "@excalidraw/excalidraw/index.css";
import { api } from "@/shared/types/logic/types";
import { useDesktopAppearance } from "@/app/logic/desktop-appearance";
import {
  drawingDrafts,
  drawingSaves,
  sceneSignature,
  isDrawingTool,
  type DrawingSnapshot,
  type DrawingScene,
  type DrawingTool,
} from "@/editor/canvas/drawing/logic/drawing-state";
import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";
import type { WireframeKind, WireframeMetadata } from "@/editor/canvas/wireframes/logic/wireframe-model";
import { getWireframeTemplate, sanitizeWireframeMetadata } from "@/editor/canvas/wireframes/logic/wireframe-model";
import WireframeInspector from "@/editor/canvas/wireframes/components/WireframeInspector";
import { insertWireframeElements, inspectable } from "@/editor/canvas/drawing/components/wireframe-elements";
import WireframePreview from "@/editor/canvas/wireframes/components/WireframePreview";
import { dropIsBlocked, pasteIsAllowed } from "@/editor/canvas/drawing/logic/drawing-files";
import { useDrawingFiles } from "@/editor/canvas/drawing/components/use-drawing-files";
import "@/editor/canvas/drawing/styles/drawing.css";

export type WireframeInsert = { kind: WireframeKind; sequence: number };
type WireframeContext = { drawingRevision: number; blocks: unknown[]; elements: unknown[]; annotations: unknown[]; source: string };

export default function DrawingWorkspace({
  project,
  workspace,
  layer,
  tool,
  toolSequence,
  settings,
  onTool,
  onReady,
  wireframeMode = false,
  wireframeInsert,
}: {
  project: string;
  workspace: string;
  layer: string;
  tool: DrawingTool;
  toolSequence: number;
  settings: SurfaceSettings;
  onTool: (tool: DrawingTool) => void;
  onReady: (ready: boolean) => void;
  wireframeMode?: boolean;
  wireframeInsert?: WireframeInsert;
}) {
  const { theme } = useDesktopAppearance();
  const key = JSON.stringify([project, workspace, layer]);
  const [snapshot, setSnapshot] = useState<DrawingSnapshot | null>(null);
  const [initialScene, setInitialScene] = useState<(DrawingScene & { files: BinaryFiles }) | null>(null);
  const images = useDrawingFiles(project, workspace);
  const [scene, setScene] = useState<DrawingScene>({ elements: [] });
  const [revision, setRevision] = useState(0);
  const [savedSignature, setSavedSignature] = useState("");
  const [editor, setEditor] = useState<ExcalidrawImperativeAPI | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<ExcalidrawElement | null>(null);
  const [exportStatus, setExportStatus] = useState("");
  const generation = useRef(0);
  const renderedGeneration = generation.current;
  const insertedSequence = useRef<number | null>(wireframeInsert?.sequence ?? null);
  useEffect(() => {
    const ticket = ++generation.current;
    setSnapshot(null);
    setInitialScene(null);
    setEditor(null);
    setSelected(null);
    setExportStatus("");
    onReady(false);
    (async () => {
      try {
        await drawingSaves.get(key);
      } catch {
        /* Chybný save zachová místní draft. */
      }
      const value = await api<DrawingSnapshot>("/api/drawing?" + new URLSearchParams({ project, workspace, layer }));
      if (ticket !== generation.current) return;
      const restored = { elements: restoreElements(value.scene.elements, null, { repairBindings: true }) };
      const baseline = sceneSignature(restored);
      const cached = drawingDrafts.get(key);
      const dirty = cached && sceneSignature(cached.scene) !== cached.savedSignature;
      const chosen = dirty && !value.readOnly ? cached! : { scene: restored, revision: value.revision, savedSignature: baseline };
      const loaded = await images.load(chosen.scene.elements);
      if (ticket !== generation.current) return;
      setSnapshot(value);
      setInitialScene({ ...chosen.scene, files: loaded.files });
      setScene(chosen.scene);
      setRevision(chosen.revision);
      setSavedSignature(chosen.savedSignature);
      setError(dirty && cached!.revision !== value.revision ? "Kresba se změnila v jiném okně. Místní kresba zůstala zachovaná." : loaded.failed ? "Některé obrázky kresby se nepodařilo načíst." : "");
      if (!value.readOnly) drawingDrafts.set(key, chosen);
    })().catch((e) => {
      if (ticket === generation.current) setError(String(e));
    });
    return () => {
      generation.current++;
      onReady(false);
    };
  }, [project, workspace, layer, reload]);
  const captureAPI = useCallback((value: ExcalidrawImperativeAPI) => setEditor(value), []);
  useEffect(() => {
    onReady(!!editor && !!snapshot && !snapshot.readOnly && !saving);
  }, [editor, snapshot?.readOnly, saving]);
  useEffect(() => {
    if (!editor || snapshot?.readOnly) return;
    if (editor.getAppState().activeTool.type !== tool) editor.setActiveTool({ type: tool });
    const frame = requestAnimationFrame(() => {
      const active = editor.getAppState().activeTool.type;
      if (isDrawingTool(active)) onTool(active);
    });
    return () => cancelAnimationFrame(frame);
  }, [editor, toolSequence, tool]);
  useEffect(() => {
    editor?.updateScene({ appState: { gridSize: settings.gridSize }, captureUpdate: CaptureUpdateAction.NEVER });
  }, [editor, settings.gridSize]);
  useEffect(() => {
    if (!editor || !wireframeInsert || snapshot?.readOnly || insertedSequence.current === wireframeInsert.sequence) return;
    insertedSequence.current = wireframeInsert.sequence;
    const elements = editor.getSceneElements();
    const state = editor.getAppState();
    const template = getWireframeTemplate(wireframeInsert.kind);
    const selectedElement = elements.find((e) => state.selectedElementIds[e.id]);
    const parentFrame = template.role === "element" ? elements.find((e) => e.type === "frame" && (e.id === selectedElement?.id || e.id === selectedElement?.frameId) && sanitizeWireframeMetadata(e.customData)?.oporaWireframe.role === "block") : undefined;
    const x = parentFrame ? parentFrame.x + 28 : state.width / (2 * state.zoom.value) - state.scrollX - template.width / 2;
    const y = parentFrame ? parentFrame.y + 66 + (wireframeInsert.sequence % 3) * 16 : state.height / (2 * state.zoom.value) - state.scrollY - template.height / 2;
    const added = insertWireframeElements(wireframeInsert.kind, wireframeInsert.sequence, x, y, parentFrame?.id ?? null);
    const primary = added.find((e) => sanitizeWireframeMetadata(e.customData));
    editor.setActiveTool({ type: "selection" });
    editor.updateScene({
      elements: [...elements, ...added],
      appState: { selectedElementIds: primary ? { [primary.id]: true } : {}, selectedGroupIds: {} },
      captureUpdate: CaptureUpdateAction.IMMEDIATELY,
    });
    if (primary) setSelected(primary);
    const frame = requestAnimationFrame(() => {
      const ids = editor.getAppState().selectedElementIds;
      setSelected(editor.getSceneElements().find((e) => ids[e.id] && sanitizeWireframeMetadata(e.customData)) ?? null);
    });
    return () => cancelAnimationFrame(frame);
  }, [editor, snapshot?.readOnly, wireframeInsert]);
  const dirty = sceneSignature(scene) !== savedSignature;
  const selectedWireframe = inspectable(selected);
  function updateSelected(update: (element: ExcalidrawElement) => ExcalidrawElement) {
    if (!editor || !selected || snapshot?.readOnly) return;
    const next = update(selected);
    setSelected(next);
    editor.updateScene({ elements: editor.getSceneElements().map((element) => element.id === selected.id ? next : element), captureUpdate: CaptureUpdateAction.IMMEDIATELY });
  }
  function updateMetadata(patch: Partial<WireframeMetadata>) {
    if (!selectedWireframe) return;
    const value = sanitizeWireframeMetadata({
      oporaWireframe: {
        ...selectedWireframe.metadata,
        ...patch,
        animation: patch.animation ?? selectedWireframe.metadata.animation,
        parallax: patch.parallax ?? selectedWireframe.metadata.parallax,
      },
    });
    if (value) updateSelected((element) => newElementWith(element, { customData: value }));
  }
  function updateColors(colors: { strokeColor?: string; backgroundColor?: string }) {
    updateSelected((element) => newElementWith(element, colors));
  }
  async function save() {
    if (!snapshot || snapshot.readOnly || saving || !editor) return;
    const ticket = generation.current;
    const sent: DrawingScene = JSON.parse(sceneSignature({ elements: editor.getSceneElements() }));
    const signature = sceneSignature(sent);
    setSaving(true);
    setError("");
    const files = editor.getFiles();
    // Nejdřív obrázky, pak scéna: server scénu s neznámým fileId odmítne a draft zůstane.
    const promise = images.upload(sent.elements, files).then(() => api<DrawingSnapshot>("/api/drawing", { project, workspace, layer, expected_revision: revision, scene: sent }));
    drawingSaves.set(key, promise);
    try {
      const value = await promise;
      const cached = drawingDrafts.get(key);
      if (cached && sceneSignature(cached.scene) === signature) drawingDrafts.set(key, { scene: sent, revision: value.revision, savedSignature: signature });
      if (ticket === generation.current) {
        setSnapshot(value);
        setScene(sent);
        setRevision(value.revision);
        setSavedSignature(signature);
      }
    } catch (e) {
      if (ticket === generation.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (drawingSaves.get(key) === promise) drawingSaves.delete(key);
      if (ticket === generation.current) setSaving(false);
    }
  }
  async function exportSavedContext() {
    if (dirty || !revision || saving) return;
    setExportStatus("Načítám uložený kontext…");
    try {
      const epoch = generation.current;
      const context = await api<WireframeContext>("/api/wireframe-context?" + new URLSearchParams({ project, workspace, layer }));
      if (epoch !== generation.current) return;
      if (context.drawingRevision !== revision || !editor || sceneSignature({ elements: editor.getSceneElements() }) !== savedSignature) throw new Error("Kresba se mezitím změnila. Nejprve ji ulož nebo obnov.");
      const url = URL.createObjectURL(new Blob([JSON.stringify(context, null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = "opora-wireframe-context.json"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setExportStatus(`Uložený kontext verze ${context.drawingRevision}: ${context.blocks.length} bloků, ${context.elements.length} prvků.`);
    } catch (e) {
      setExportStatus(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <div className={wireframeMode ? "drawing-workspace wireframe-active" : "drawing-workspace"}>
      <div className="drawing-statusbar">
        <span data-testid="drawing-status" role="status">
          {!snapshot ? "Načítám kresbu…" : saving ? "Ukládám…" : dirty ? "Neuložená kresba" : revision ? `Uloženo · verze ${revision}` : "Prázdná kresba"}
        </span>
        <span>Prvky: <strong data-testid="drawing-element-count">{scene.elements.filter((e) => !e.isDeleted).length}</strong></span>
        <button className="primary" disabled={!editor || saving || !!snapshot?.readOnly} onClick={save}>Uložit kresbu</button>
        {wireframeMode && <button disabled={dirty || !revision || saving} onClick={exportSavedContext}>Exportovat uložený kontext</button>}
      </div>
      {exportStatus && <div className="wireframe-export-status" role="status">{exportStatus}</div>}
      {error && <div className="drawing-error" role="alert">{error}<button disabled={saving} onClick={() => { generation.current++; drawingDrafts.delete(key); onReady(false); setInitialScene(null); setSnapshot(null); setEditor(null); setReload(reload + 1); }}>Zahodit místní a načíst uložené</button></div>}
      {snapshot?.readOnly ? <div className="drawing-unavailable"><h2>Kreslení v pracovním prostoru</h2><p>{snapshot.source}</p><p>Pro úpravy přepni do pracovního prostoru nebo lokálního návrhu.</p></div> : initialScene && <div className="drawing-main"><div className="drawing-editor" data-testid="drawing-surface" onDropCapture={(e) => { if (dropIsBlocked(e.dataTransfer.files)) { e.preventDefault(); e.stopPropagation(); setError("Do kresby lze přetáhnout jen obrázky PNG, JPEG, WebP nebo GIF."); } }}>
        <Excalidraw initialData={{ elements: initialScene.elements, files: initialScene.files, scrollToContent: true }} excalidrawAPI={captureAPI} theme={theme} langCode="cs-CZ" name="Opora kresba" viewModeEnabled={saving} gridModeEnabled={settings.drawingGrid} handleKeyboardGlobally={false} aiEnabled={false} validateEmbeddable={false} UIOptions={{ tools: { image: true }, canvasActions: { loadScene: false, saveToActiveFile: false, export: false, saveAsImage: false, toggleTheme: false, clearCanvas: false } }} onPaste={pasteIsAllowed} onLinkOpen={(_, event) => event.preventDefault()} onChange={(elements, state, files) => {
          if (renderedGeneration !== generation.current) return;
          images.remember(files);
          const next = { elements: elements.filter((e) => !e.isDeleted) };
          if (sceneSignature(next) !== sceneSignature(scene)) setScene(next);
          drawingDrafts.set(key, { scene: next, revision, savedSignature });
          const selectedId = Object.keys(state.selectedElementIds).find((id) => state.selectedElementIds[id]);
          setSelected(selectedId ? elements.find((element) => element.id === selectedId) ?? null : null);
          if (isDrawingTool(state.activeTool.type) && state.activeTool.type !== tool) onTool(state.activeTool.type);
        }} />
      </div>{wireframeMode && <div className="wireframe-sidecar"><WireframeInspector selected={selectedWireframe} disabled={saving || !!snapshot?.readOnly} onMetadata={updateMetadata} onColors={updateColors} /><WireframePreview elements={scene.elements} /></div>}</div>}
      <div className="drawing-note">Lokální kresba této vrstvy; nemění strukturu ani Git. Před obnovením stránky ulož změny.</div>
    </div>
  );
}
