// Balíček pro render bez Reactu: pět textových souborů a obrázky podkladů, ze kterých agent ve VS Code vyrenderuje video
// (`python render.py`). ZIP bez nové závislosti nejde, proto se soubory stahují jeden po druhém jedním klikem (downloadFiles).
// Obrázky jdou jako `asset-<id>.<přípona>` a storyboard.json u každého podkladu nese `file`; index.html je načte před
// seek(t) a bez nich skončí chybou (žádný tichý fallback na barvu nebo šablonu). Webová scéna (`scena`) místo
// `animation.js` nese `scene.html` (čistý dokument) a `index.html` = týž dokument se CSP a runtime (`sceneDocument`).
import claude from "../assets/render-package/CLAUDE.md?raw";
import indexHtml from "../assets/render-package/index.html?raw";
import renderPy from "../assets/render-package/render.py?raw";
import { animationOf } from "./animations";
import { sceneDocument } from "./scene-document";
import { SCENE_ANIMATION, serialize, type Storyboard, type StoryboardAsset } from "./storyboard-model";

export type PackageFile = { name: string; type: string; text?: string; dataURL?: string };
const EXT: Record<string, string> = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp" };

/** Zdroj animace: kód ze storyboardu, dokument scény, jinak textová podoba šablony z registru; bez něj null. */
export function packageSource(board: Storyboard): string | null {
  if (board.animation === "kod") return board.code?.source ?? null;
  if (board.animation === SCENE_ANIMATION) return board.scene?.html ?? null;
  return animationOf(board.animation)?.source ?? null;
}

/** Název souboru podkladu v balíčku; prohlížeč při stahování cestu zahodí, proto plochý název. */
export const assetFileName = (asset: StoryboardAsset): string => `asset-${asset.id ?? asset.fileId}.${EXT[asset.mimeType] ?? "bin"}`;

/** Textové soubory balíčku; `storyboard.json` nese u podkladů `file`. Obrázky doplní `packageAssets`. */
export function renderPackage(board: Storyboard): PackageFile[] | null {
  const source = packageSource(board);
  if (source === null) return null;
  const serialized = serialize(board);
  const json = { ...serialized, assets: (serialized.assets ?? []).map((a) => ({ ...a, file: assetFileName(a) })) };
  if (board.animation === SCENE_ANIMATION) return [
    { name: "storyboard.json", text: JSON.stringify(json, null, 2), type: "application/json" },
    { name: "scene.html", text: source, type: "text/html" },
    { name: "index.html", text: sceneDocument(source), type: "text/html" },
    { name: "render.py", text: renderPy, type: "text/x-python" },
    { name: "CLAUDE.md", text: claude, type: "text/markdown" },
  ];
  return [
    { name: "storyboard.json", text: JSON.stringify(json, null, 2), type: "application/json" },
    { name: "animation.js", text: source, type: "text/javascript" },
    { name: "CLAUDE.md", text: claude, type: "text/markdown" },
    { name: "render.py", text: renderPy, type: "text/x-python" },
    { name: "index.html", text: indexHtml, type: "text/html" },
  ];
}

/** Obrázky podkladů jako soubory balíčku; chybějící obrázek je chyba, balíček se bez něj nevydá. */
export function packageAssets(board: Storyboard, files: readonly { id: string; dataURL: string }[]): PackageFile[] {
  return (board.assets ?? []).map((asset) => {
    const file = files.find((f) => f.id === asset.fileId);
    if (!file) throw new Error(`Obrázek podkladu „${asset.name}“ není k dispozici (${asset.fileId}); balíček by byl neúplný.`);
    return { name: assetFileName(asset), type: asset.mimeType, dataURL: file.dataURL };
  });
}

function toBlob(file: PackageFile): Blob {
  if (file.text !== undefined) return new Blob([file.text], { type: file.type });
  const encoded = (file.dataURL ?? "").split(",", 2)[1] ?? "";
  const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: file.type });
}

/** Stáhne soubory po jednom (krátký odstup, aby je prohlížeč nesloučil do jedné žádosti). */
export async function downloadFiles(files: PackageFile[]): Promise<void> {
  for (const file of files) {
    const url = URL.createObjectURL(toBlob(file));
    Object.assign(document.createElement("a"), { href: url, download: file.name }).click();
    URL.revokeObjectURL(url);
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
}
