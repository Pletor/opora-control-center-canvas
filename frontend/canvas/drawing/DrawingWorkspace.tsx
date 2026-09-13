import { useCallback, useEffect, useRef, useState } from "react";
import {
  Excalidraw,
  restoreElements,
  CaptureUpdateAction,
  convertToExcalidrawElements,
  newElementWith,
} from "@excalidraw/excalidraw";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import "@excalidraw/excalidraw/index.css";
import { api } from "@/shared/types/types";
import { useDesktopAppearance } from "@/app/DesktopThemeControls";
import {
  drawingDrafts,
  drawingSaves,
  sceneSignature,
  isDrawingTool,
  type DrawingSnapshot,
  type DrawingScene,
  type DrawingTool,
} from "@/canvas/drawing/drawing-state";
import type { SurfaceSettings } from "@/project-detail/workspace/workspace-settings";
import type { WireframeKind, WireframeMetadata } from "@/project-detail/inspector/wireframe-model";
import { buildWireframeMetadata, getWireframeTemplate, sanitizeWireframeMetadata } from "@/project-detail/inspector/wireframe-model";
import WireframeInspector, { type InspectableWireframe } from "@/project-detail/inspector/WireframeInspector";
import WireframePreview from "@/project-detail/inspector/WireframePreview";
import "@/canvas/drawing/drawing.css";

export type WireframeInsert = { kind: WireframeKind; sequence: number };
type WireframeContext = { drawingRevision: number; blocks: unknown[]; elements: unknown[]; annotations: unknown[]; source: string };

function labelElement(kind: WireframeKind, x: number, y: number, width: number, height: number, frameId: string | null) {
  const template = getWireframeTemplate(kind);
  const customData = buildWireframeMetadata(kind);
  if (kind === "heading" || kind === "text") {
    return convertToExcalidrawElements([
      { type: "text", x, y, text: template.label, fontSize: kind === "heading" ? 28 : 18, frameId, customData },
    ], { regenerateIds: true });
  }
  return convertToExcalidrawElements([
    {
      type: "rectangle",
      x,
      y,
      width,
      height,
      frameId,
      strokeColor: "#8fb3c9",
      backgroundColor: "transparent",
      roughness: 0,
      label: { text: template.label },
      customData,
    },
  ], { regenerateIds: true });
}

function insertWireframeElements(kind: WireframeKind, sequence: number, x: number, y: number, parentFrameId: string | null): readonly ExcalidrawElement[] {
  const template = getWireframeTemplate(kind);
  if (template.role === "element") return labelElement(kind, x, y, template.width, template.height, parentFrameId).map((element) => newElementWith(element, { frameId: parentFrameId }));
  const frame = convertToExcalidrawElements([
    {
      type: "frame",
      x,
      y,
      width: template.width,
      height: template.height,
      name: template.label,
      children: [],
      strokeColor: "#7699ae",
      backgroundColor: "transparent",
      customData: buildWireframeMetadata(kind),
    },
  ], { regenerateIds: true });
  const frameId = frame[0]?.id;
  if (!frameId) return frame;
  if (kind === "two-columns" || kind === "three-columns") {
    const slots = template.slots ?? 2;
    const columns = Array.from({ length: slots }, (_, index) => ({
      type: "rectangle" as const,
      x: x + 24 + index * ((template.width - 48) / slots),
      y: y + 62,
      width: (template.width - 48) / slots - 12,
      height: template.height - 86,
      frameId,
      strokeColor: "#526b7a",
      backgroundColor: "transparent",
      roughness: 0,
    }));
    return [...frame, ...convertToExcalidrawElements(columns, { regenerateIds: true })];
  }
  return frame;
}

function inspectable(element: ExcalidrawElement | null): InspectableWireframe | null {
  if (!element) return null;
  const customData = sanitizeWireframeMetadata(element.customData);
  if (!customData) return null;
  return {
    id: element.id,
    type: element.type,
    ...(element.type === "text" ? { text: element.text } : {}),
    ...(element.type === "frame" || element.type === "magicframe" ? { name: element.name } : {}),
    strokeColor: element.strokeColor,
    backgroundColor: element.backgroundColor,
    metadata: customData.oporaWireframe,
  };
}

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
  const [initialScene, setInitialScene] = useState<DrawingScene | null>(null);
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
      setSnapshot(value);
      setInitialScene(chosen.scene);
      setScene(chosen.scene);
      setRevision(chosen.revision);
      setSavedSignature(chosen.savedSignature);
      setError(dirty && cached!.revision !== value.revision ? "Kresba se změnila v jiném okně. Místní kresba zůstala zachovaná." : "");
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
    const promise = api<DrawingSnapshot>("/api/drawing", { project, workspace, layer, expected_revision: revision, scene: sent });
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
      {snapshot?.readOnly ? <div className="drawing-unavailable"><h2>Kreslení v pracovním prostoru</h2><p>{snapshot.source}</p><p>Pro úpravy přepni do pracovního prostoru nebo lokálního návrhu.</p></div> : initialScene && <div className="drawing-main"><div className="drawing-editor" data-testid="drawing-surface" onDropCapture={(e) => { if (e.dataTransfer.files.length) { e.preventDefault(); e.stopPropagation(); setError("Import souborů do kresby zatím není podporovaný."); } }}>
        <Excalidraw initialData={{ elements: initialScene.elements, scrollToContent: true }} excalidrawAPI={captureAPI} theme={theme} langCode="cs-CZ" name="Opora kresba" viewModeEnabled={saving} gridModeEnabled={settings.drawingGrid} handleKeyboardGlobally={false} aiEnabled={false} validateEmbeddable={false} UIOptions={{ tools: { image: false }, canvasActions: { loadScene: false, saveToActiveFile: false, export: false, saveAsImage: false, toggleTheme: false, clearCanvas: false } }} onPaste={(data) => !Object.keys(data.files ?? {}).length && !data.mixedContent?.some((item) => item.type === "imageUrl") && !data.elements?.some((e) => ["image", "embeddable", "iframe", "magicframe"].includes(e.type))} onLinkOpen={(_, event) => event.preventDefault()} onChange={(elements, state) => {
          if (renderedGeneration !== generation.current) return;
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
