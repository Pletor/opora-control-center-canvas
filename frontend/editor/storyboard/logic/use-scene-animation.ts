// Webová scéna pro editor: z `board.scene` složí AnimationDef (`paint` nic nekreslí, snímek dělá iframe `SceneFrame`),
// připraví `srcdoc` jednou na dokument, podklady jako data URL podle `assets[].id` (u neuloženého podle fileId) a drží
// chybu scény: textovou kontrolu externích zdrojů a chyby hlášené z iframe (výjimka v seek, chyba stránky).
import { useMemo, useState } from "react";
import type { AnimationDef } from "./animations";
import { forbiddenScene, sceneDocument, sceneStoryboard } from "./scene-document";
import { SCENE_ANIMATION, type Storyboard } from "./storyboard-model";
import { assetSources, type AssetSources } from "./use-code-animation";

export type SceneAnimationState = { animation: AnimationDef | undefined; error: string };

/** Obrázek jako data URL: načtené podklady ho mají v `src`, jinak se překreslí přes canvas. */
export function imageDataURL(image: HTMLImageElement): string {
  if (image.src.startsWith("data:")) return image.src;
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  canvas.getContext("2d")?.drawImage(image, 0, 0);
  return canvas.toDataURL("image/png");
}

const nothing = () => undefined;

export function useSceneAnimation(board: Storyboard | null, images: AssetSources = new Map()): SceneAnimationState {
  const scene = board?.animation === SCENE_ANIMATION ? board.scene : undefined;
  const html = scene?.html;
  const [frameError, setFrameError] = useState<{ html: string; message: string } | null>(null);
  const srcdoc = useMemo(() => (html === undefined ? "" : sceneDocument(html)), [html]);
  const wanted = (board?.assets ?? []).filter((a) => images.has(a.fileId)).map((a) => `${a.id ?? a.fileId}=${a.fileId}`).join("|");
  const assets = useMemo(
    () => Object.fromEntries(assetSources(board, images).map(([id, image]) => [id, imageDataURL(image)])),
    // board a images jsou shrnuté ve `wanted`; jiné změny storyboardu podklady nemění.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wanted],
  );
  const animation = useMemo((): AnimationDef | undefined => {
    if (!scene) return undefined;
    const onError = (message: string) => setFrameError((old) => (old && old.html === scene.html && old.message === message ? old : { html: scene.html, message }));
    return {
      id: SCENE_ANIMATION, label: scene.title || "Webová scéna", fields: scene.fields, layers: scene.layers, source: scene.html,
      defaults: () => sceneStoryboard(scene),
      paint: nothing,
      scene: { srcdoc, assets, onError },
    };
  }, [scene, srcdoc, assets]);
  const forbidden = html === undefined ? null : forbiddenScene(html);
  // Chyba z iframe platí jen pro dokument, který ji nahlásil; nový dokument začíná čistý.
  const error = forbidden ?? (frameError && frameError.html === html ? frameError.message : "");
  return { animation, error };
}
