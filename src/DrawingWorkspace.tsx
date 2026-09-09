import { useCallback, useEffect, useRef, useState } from "react";
import {
  Excalidraw,
  restoreElements,
  CaptureUpdateAction,
} from "@excalidraw/excalidraw";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import "@excalidraw/excalidraw/index.css";
import { api } from "./types";
import {
  drawingDrafts,
  drawingSaves,
  sceneSignature,
  isDrawingTool,
  type DrawingSnapshot,
  type DrawingScene,
  type DrawingTool,
} from "./drawing-state";
import type { SurfaceSettings } from "./workspace-settings";
import "./drawing.css";

export default function DrawingWorkspace({
  project,
  workspace,
  layer,
  tool,
  toolSequence,
  settings,
  onTool,
  onReady,
}: {
  project: string;
  workspace: string;
  layer: string;
  tool: DrawingTool;
  toolSequence: number;
  settings: SurfaceSettings;
  onTool: (tool: DrawingTool) => void;
  onReady: (ready: boolean) => void;
}) {
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
  const generation = useRef(0);
  const renderedGeneration = generation.current;
  useEffect(() => {
    const ticket = ++generation.current;
    setSnapshot(null);
    setInitialScene(null);
    setEditor(null);
    onReady(false);
    (async () => {
      try {
        await drawingSaves.get(key);
      } catch {
        /* Chybný save zachová místní draft. */
      }
      const value = await api<DrawingSnapshot>(
        "/api/drawing?" + new URLSearchParams({ project, workspace, layer }),
      );
      if (ticket !== generation.current) return;
      const restored = {
        elements: restoreElements(value.scene.elements, null, {
          repairBindings: true,
        }),
      };
      const baseline = sceneSignature(restored);
      const cached = drawingDrafts.get(key);
      const dirty =
        cached && sceneSignature(cached.scene) !== cached.savedSignature;
      const chosen =
        dirty && !value.readOnly
          ? cached!
          : {
              scene: restored,
              revision: value.revision,
              savedSignature: baseline,
            };
      setSnapshot(value);
      setInitialScene(chosen.scene);
      setScene(chosen.scene);
      setRevision(chosen.revision);
      setSavedSignature(chosen.savedSignature);
      setError(
        dirty && cached!.revision !== value.revision
          ? "Kresba se změnila v jiném okně. Místní kresba zůstala zachovaná."
          : "",
      );
      if (!value.readOnly) drawingDrafts.set(key, chosen);
    })().catch((e) => {
      if (ticket === generation.current) setError(String(e));
    });
    return () => {
      generation.current++;
      onReady(false);
    };
  }, [project, workspace, layer, reload]);
  const captureAPI = useCallback(
    (value: ExcalidrawImperativeAPI) => setEditor(value),
    [],
  );
  useEffect(() => {
    onReady(!!editor && !!snapshot && !snapshot.readOnly && !saving);
  }, [editor, snapshot?.readOnly, saving]);
  useEffect(() => {
    if (!editor || snapshot?.readOnly) return;
    if (editor.getAppState().activeTool.type !== tool)
      editor.setActiveTool({ type: tool });
    const frame = requestAnimationFrame(() => {
      const active = editor.getAppState().activeTool.type;
      if (isDrawingTool(active)) onTool(active);
    });
    return () => cancelAnimationFrame(frame);
  }, [editor, toolSequence, tool]);
  useEffect(() => {
    editor?.updateScene({
      appState: { gridSize: settings.gridSize },
      captureUpdate: CaptureUpdateAction.NEVER,
    });
  }, [editor, settings.gridSize]);
  const dirty = sceneSignature(scene) !== savedSignature;
  async function save() {
    if (!snapshot || snapshot.readOnly || saving || !editor) return;
    const ticket = generation.current;
    const sent: DrawingScene = JSON.parse(
      sceneSignature({ elements: editor.getSceneElements() }),
    );
    const signature = sceneSignature(sent);
    setSaving(true);
    setError("");
    const promise = api<DrawingSnapshot>("/api/drawing", {
      project,
      workspace,
      layer,
      expected_revision: revision,
      scene: sent,
    });
    drawingSaves.set(key, promise);
    try {
      const value = await promise;
      const cached = drawingDrafts.get(key);
      if (cached && sceneSignature(cached.scene) === signature)
        drawingDrafts.set(key, {
          scene: sent,
          revision: value.revision,
          savedSignature: signature,
        });
      if (ticket === generation.current) {
        setSnapshot(value);
        setScene(sent);
        setRevision(value.revision);
        setSavedSignature(signature);
      }
    } catch (e) {
      if (ticket === generation.current)
        setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (drawingSaves.get(key) === promise) drawingSaves.delete(key);
      if (ticket === generation.current) setSaving(false);
    }
  }
  return (
    <div className="drawing-workspace">
      <div className="drawing-statusbar">
        <span data-testid="drawing-status" role="status">
          {!snapshot
            ? "Načítám kresbu…"
            : saving
              ? "Ukládám…"
              : dirty
                ? "Neuložená kresba"
                : revision
                  ? `Uloženo · verze ${revision}`
                  : "Prázdná kresba"}
        </span>
        <span>
          Prvky:{" "}
          <strong data-testid="drawing-element-count">
            {scene.elements.filter((e) => !e.isDeleted).length}
          </strong>
        </span>
        <button
          className="primary"
          disabled={!editor || saving || !!snapshot?.readOnly}
          onClick={save}
        >
          Uložit kresbu
        </button>
      </div>
      {error && (
        <div className="drawing-error" role="alert">
          {error}
          <button
            disabled={saving}
            onClick={() => {
              generation.current++;
              drawingDrafts.delete(key);
              onReady(false);
              setInitialScene(null);
              setSnapshot(null);
              setEditor(null);
              setReload(reload + 1);
            }}
          >
            Zahodit místní a načíst uložené
          </button>
        </div>
      )}
      {snapshot?.readOnly ? (
        <div className="drawing-unavailable">
          <h2>Kreslení v pracovním prostoru</h2>
          <p>{snapshot.source}</p>
          <p>Pro úpravy přepni do pracovního prostoru nebo lokálního návrhu.</p>
        </div>
      ) : (
        initialScene && (
          <div
            className="drawing-editor"
            data-testid="drawing-surface"
            onDropCapture={(e) => {
              if (e.dataTransfer.files.length) {
                e.preventDefault();
                e.stopPropagation();
                setError("Import souborů do kresby zatím není podporovaný.");
              }
            }}
          >
            <Excalidraw
              initialData={{
                elements: initialScene.elements,
                scrollToContent: true,
              }}
              excalidrawAPI={captureAPI}
              theme="dark"
              langCode="cs-CZ"
              name="Opora kresba"
              viewModeEnabled={saving}
              gridModeEnabled={settings.drawingGrid}
              handleKeyboardGlobally={false}
              aiEnabled={false}
              validateEmbeddable={false}
              UIOptions={{
                tools: { image: false },
                canvasActions: {
                  loadScene: false,
                  saveToActiveFile: false,
                  export: false,
                  saveAsImage: false,
                  toggleTheme: false,
                  clearCanvas: false,
                },
              }}
              onPaste={(data) =>
                !Object.keys(data.files ?? {}).length &&
                !data.mixedContent?.some((item) => item.type === "imageUrl") &&
                !data.elements?.some((e) =>
                  ["image", "embeddable", "iframe", "magicframe"].includes(
                    e.type,
                  ),
                )
              }
              onLinkOpen={(_, event) => event.preventDefault()}
              onChange={(elements, state) => {
                if (renderedGeneration !== generation.current) return;
                const next = { elements: elements.filter((e) => !e.isDeleted) };
                if (sceneSignature(next) !== sceneSignature(scene))
                  setScene(next);
                drawingDrafts.set(key, {
                  scene: next,
                  revision,
                  savedSignature,
                });
                if (
                  isDrawingTool(state.activeTool.type) &&
                  state.activeTool.type !== tool
                )
                  onTool(state.activeTool.type);
              }}
            />
          </div>
        )
      )}
      <div className="drawing-note">
        Lokální kresba této vrstvy; nemění strukturu ani Git. Před obnovením
        stránky ulož změny.
      </div>
    </div>
  );
}
