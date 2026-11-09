// Editor storyboardu jedné karty (rodič dílků): drží koncept, výběr momentu, čas, přehrávání, nástroj a viditelné vrstvy;
// jen on ukládá. Přehrávání je jediný časovač (requestAnimationFrame) a jen posouvá t. Dílky vrací přímo do mřížky módu.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ANIMATIONS, animationOf } from "../logic/animations";
import { EMPTY_CODE, codeStoryboard } from "../logic/animations/code";
import { defaultVisible, paintLayers, toggleLayer } from "../logic/storyboard-layout";
import { api } from "@/shared/types/logic/types";
import type { DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";
import { checkAssetFile, newAsset, patchAsset } from "../logic/asset-upload";
import { downloadFiles, packageAssets, renderPackage } from "../logic/render-package";
import { EMPTY_SCENE, sceneStoryboard } from "../logic/scene-document";
import { uploadImage } from "../logic/sketch-files";
import {
  CODE_ANIMATION, SCENE_ANIMATION, addMomentAt, duplicateMoment, openComments, removeAnnotation, removeMoment, serialize, setAnnotation, updateMoment, validate,
  type Annotation, type StateValue, type Storyboard,
} from "../logic/storyboard-model";
import { useCodeAnimation } from "../logic/use-code-animation";
import { useSceneAnimation } from "../logic/use-scene-animation";
import { useSketchImages } from "../logic/use-sketch-images";
import { useSketchSession } from "../logic/use-sketch-session";
import { statusLabel } from "../logic/storyboard-status";
import { useStoryboardAutosave } from "../logic/use-storyboard-autosave";
import { useStoryboardStore } from "../logic/use-storyboard-store";
import { useStoryboardProposal } from "../logic/use-storyboard-proposal";
import StoryboardReview from "./StoryboardReview";
import LayerRail from "./LayerRail";
import MiniPreview from "./MiniPreview";
import MomentStrip from "./MomentStrip";
import MomentTimeline from "./MomentTimeline";
import SketchOverlay from "./SketchOverlay";
import StoryboardBar from "./StoryboardBar";
import StoryboardStage, { type StageTool } from "./StoryboardStage";
import StoryboardSide from "./StoryboardSide";
import StoryboardStart from "./StoryboardStart";

export default function StoryboardEditor({ project, workspace, nodeId, readOnly, picker, onMark, onDraw }: {
  project: string;
  workspace: string;
  nodeId: string;
  readOnly: boolean;
  picker: ReactNode;
  /** Po načtení a po založení/smazání: má karta storyboard? */
  onMark: (nodeId: string, has: boolean) => void;
  onDraw: (nodeId: string) => void;
}) {
  const store = useStoryboardStore(project, workspace, nodeId);
  const proposal = useStoryboardProposal(project, workspace, nodeId, store.revision);
  const { draft: board, setDraft } = store;
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(0);
  const [annotation, setAnnotationIndex] = useState(-1);
  const [tool, setTool] = useState<StageTool>("select");
  const [viewSketch, setViewSketch] = useState(false);
  const [custom, setCustom] = useState<{ animation: string; visible: ReadonlySet<string> } | null>(null);
  const [assetBusy, setAssetBusy] = useState(false);
  const [assetMessage, setAssetMessage] = useState("");
  // Chyba exportu balíčku patří do lišty (vidí ji člověk v kterékoli záložce), ne jen do panelu Podklady.
  const [exportMessage, setExportMessage] = useState("");
  const fileIds = board ? [...board.moments.flatMap((m) => (m.sketch ? [m.sketch.fileId] : [])), ...(board.assets ?? []).map((a) => a.fileId)] : [];
  const sketches = useSketchImages(project, workspace, fileIds);
  const codeState = useCodeAnimation(board, sketches);
  const sceneState = useSceneAnimation(board, sketches);
  const animation = board ? (board.animation === CODE_ANIMATION ? codeState.animation : board.animation === SCENE_ANIMATION ? sceneState.animation : animationOf(board.animation)) : undefined;
  const animationError = codeState.error ? "Kód animace selhal: " + codeState.error : sceneState.error ? "Scéna selhala: " + sceneState.error : "";
  const locked = readOnly || store.serverReadOnly;
  const duration = board?.duration ?? 0;
  const visible = useMemo(() => (animation ? (custom && custom.animation === animation.id ? custom.visible : defaultVisible(animation)) : new Set<string>()), [animation, custom]);
  const allPaint = useMemo(() => (animation ? paintLayers(defaultVisible(animation)) : new Set<string>()), [animation]);
  const has = board !== null;
  const sketch = useSketchSession({ project, workspace, nodeId, board, animation, onBoard: setDraft, onSave: store.save });

  useEffect(() => { if (store.status === "idle") onMark(nodeId, has); }, [store.status, has, nodeId, onMark]);
  useEffect(() => {
    if (!playing || !duration) return;
    let last = performance.now(), frame = 0;
    const tick = (now: number) => {
      const dt = (now - last) / 1000; last = now;
      setT((current) => (current + dt >= duration ? 0 : current + dt));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, duration]);

  const currentIndex = board ? Math.min(selected, board.moments.length - 1) : 0;
  const current = board?.moments[currentIndex];
  const errors = board ? validate(board, [...Object.keys(ANIMATIONS), CODE_ANIMATION, SCENE_ANIMATION]) : [];
  // Koncept se ukládá sám (700 ms po změně, při odchodu z karty i zavření stránky); „Uložit“ jen uloží hned.
  useStoryboardAutosave({ project, workspace, nodeId, store, valid: !errors.length, readOnly: locked });
  const label = statusLabel({ status: store.status, dirty: store.dirty, autosave: !errors.length && !locked, message: store.message || errors[0] || "", savedAt: store.savedAt, openComments: board ? openComments(board) : 0 });
  const hasXY = !!animation && animation.fields.some((f) => f.key === "x") && animation.fields.some((f) => f.key === "y");
  const exportPackage = async () => {
    if (!board) return;
    const files = renderPackage(board);
    if (!files) return;
    if ((board.assets ?? []).some((a) => !a.id) || store.dirty) { setExportMessage("Balíček se nevydal: nejdřív storyboard uložte (potřebuje uložené podklady s id)."); return; }
    setExportMessage("");
    try {
      const ids = (board.assets ?? []).map((a) => a.fileId);
      const value = ids.length ? await api<{ files: DrawingFile[] }>("/api/drawing-files?" + new URLSearchParams({ project, workspace, ids: ids.join(",") })) : { files: [] };
      await downloadFiles([...files, ...packageAssets(board, value.files)]);
    } catch (e) { setExportMessage("Balíček se nevydal: " + (e instanceof Error ? e.message : String(e))); }
  };
  const uploadAsset = async (file: File) => {
    if (!board) return;
    const problem = checkAssetFile(file);
    if (problem) { setAssetMessage(problem); return; }
    setAssetBusy(true); setAssetMessage("");
    try {
      const fileId = await uploadImage(project, workspace, file, file.type);
      setDraft({ ...board, assets: [...(board.assets ?? []), newAsset(file.name, fileId, file.type)] });
    } catch (e) { setAssetMessage(e instanceof Error ? e.message : String(e)); }
    finally { setAssetBusy(false); }
  };
  const bar = (
    <StoryboardBar picker={picker} status={store.status} label={label} notice={exportMessage} dirty={store.dirty} readOnly={locked || !board} canPlace={hasXY} tool={tool} hasDraw onPackage={() => void exportPackage()}
      review={<StoryboardReview disabled={locked || store.dirty || store.status !== "idle" || !store.revision || !!errors.length}
        busy={proposal.busy} href={proposal.href} error={proposal.error} onPropose={() => void proposal.propose()} />}
      sketchLabel={locked ? "Zobrazit skicu" : "Skica"} sketchDisabled={sketch.busy || !current || (locked ? !current.sketch : !current.id)}
      onSketch={() => { if (locked) setViewSketch(true); else void sketch.open(currentIndex); }}
      onTool={setTool} onSave={() => { if (board && !errors.length) void store.save(board); }} onReload={() => { setDraft(null); void store.reload(); }}
      onOpenWindow={() => window.open("/?" + new URLSearchParams({ mode: "storyboard", project, workspace, node: nodeId }), "_blank")} onDraw={() => onDraw(nodeId)}
      onDownload={() => board && download(board)} onDelete={() => { if (window.confirm("Smazat storyboard této karty?")) void store.save(null); }} />
  );
  if (store.status === "loading" && !board) return <>{bar}<p className="storyboard__empty" role="status">Načítám storyboard…</p></>;
  if (store.status === "error" && !board) return <>{bar}<p className="storyboard__empty storyboard__status--conflict" role="alert">{store.message}</p></>;
  if (!board) {
    const options = store.animations.length ? store.animations : Object.values(ANIMATIONS).map(({ id, label }) => ({ id, label }));
    return <>{bar}<div className="storyboard__empty"><StoryboardStart animations={options} locked={locked} onCreate={(id) => { setDraft(id === CODE_ANIMATION ? codeStoryboard(EMPTY_CODE) : id === SCENE_ANIMATION ? sceneStoryboard(EMPTY_SCENE) : animationOf(id)!.defaults()); setSelected(0); setT(0); }} /></div></>;
  }
  if (!animation) return <>{bar}<p className="storyboard__empty storyboard__status--conflict" role="alert">Neznámá animace „{board.animation}“.</p></>;

  const index = Math.min(selected, board.moments.length - 1);
  const moment = board.moments[index];
  const apply = (edit: { board: Storyboard; index: number }) => { setDraft(edit.board); setSelected(edit.index); };
  const setState = (key: string, value: StateValue) => apply(updateMoment(board, index, { state: { ...moment.state, [key]: value } }));
  const addAnnotation = (a: Annotation) => { setDraft(setAnnotation(board, index, -1, a)); setAnnotationIndex(moment.annotations.length); setTool("select"); };
  const removeNote = (i: number) => { setDraft(removeAnnotation(board, index, i)); setAnnotationIndex(-1); };
  const select = (i: number) => { setSelected(i); setT(board.moments[i].t); setPlaying(false); setAnnotationIndex(-1); };
  const add = () => apply(addMomentAt(board, animation, t));
  const momentImage = moment.sketch ? sketches.get(moment.sketch.fileId) : undefined;

  return (
    <>
      {bar}
      <MomentStrip board={board} animation={animation} paintVisible={allPaint} sketches={sketches} selected={index} readOnly={locked} onSelect={select} onAdd={add} />
      <LayerRail board={board} animation={animation} thumbT={moment.t} annotations={moment.annotations} sketch={momentImage} stale={!!moment.sketch?.imageStale} visible={visible} error={animationError}
        onToggle={(id) => setCustom({ animation: animation.id, visible: toggleLayer(visible, id) })} />
      <div className="storyboard__stage-area">
        <StoryboardStage board={board} animation={animation} t={t} visible={visible} annotations={moment.annotations} sketch={momentImage} selectedAnnotation={annotation} tool={tool} readOnly={locked}
          onPlace={(x, y) => apply(updateMoment(board, index, { state: { ...moment.state, x, y } }))} onAnnotationAdd={addAnnotation}
          onAnnotationSelect={setAnnotationIndex} onAnnotationRemove={removeNote} />
        <MiniPreview board={board} animation={animation} t={t} visible={allPaint} sketch={momentImage} />
        {(sketch.session || viewSketch) && (
          <SketchOverlay project={project} workspace={workspace} layer={sketch.session?.layer ?? moment.sketch?.layer ?? ""} title={sketch.session?.title ?? `Skica momentu ${moment.t} s · ${moment.title || "bez názvu"}`}
            backdrop={sketch.session?.backdrop ?? []} readOnly={locked} image={momentImage} busy={sketch.busy} message={sketch.message}
            onApi={sketch.onApi} onSaved={() => void sketch.exportSketch()} onExport={() => void sketch.exportSketch()} onClose={() => { sketch.close(); setViewSketch(false); }} />
        )}
      </div>
      <MomentTimeline moments={board.moments} duration={board.duration} t={t} selected={index} playing={playing} readOnly={locked}
        onSeek={(v) => { setT(v); setPlaying(false); }} onSelect={select} onPlay={setPlaying} onAdd={add} />
      <StoryboardSide animationId={animation.id} code={board.code} scene={board.scene} readOnly={locked} workerError={codeState.error} sceneError={sceneState.error} slowMs={codeState.slowMs}
        assets={{
          assets: board.assets ?? [], layers: animation.layers, moments: board.moments, images: sketches, readOnly: locked, busy: assetBusy, message: assetMessage,
          onUpload: (file) => void uploadAsset(file),
          onChange: (i, patch) => setDraft({ ...board, assets: (board.assets ?? []).map((a, k) => (k === i ? patchAsset(a, patch) : a)) }),
          onRemove: (i) => setDraft({ ...board, assets: (board.assets ?? []).filter((_, k) => k !== i) }),
        }}
        onApplyCode={(code) => setDraft({ ...board, code })}
        onApplyScene={(scene) => setDraft({ ...board, scene })}
        onUseAsCode={() => setDraft({ ...board, animation: CODE_ANIMATION, code: { source: animation.source, title: animation.label, fields: animation.fields, layers: animation.layers } })}
        form={{
          moment, fields: animation.fields, readOnly: locked, selectedAnnotation: annotation, canRemove: board.moments.length > 1,
          onChange: (patch) => apply(updateMoment(board, index, patch)), onState: setState,
          onAnnotationText: (i, text) => setDraft(setAnnotation(board, index, i, { ...moment.annotations[i], text })),
          onAnnotationSelect: setAnnotationIndex, onAnnotationRemove: removeNote,
          onDuplicate: () => apply(duplicateMoment(board, index)), onRemove: () => apply(removeMoment(board, index)),
        }} />
    </>
  );
}

function download(board: Storyboard) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(serialize(board), null, 2)], { type: "application/json" }));
  Object.assign(document.createElement("a"), { href: url, download: "storyboard.json" }).click();
  URL.revokeObjectURL(url);
}
