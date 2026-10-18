// Kontrakt kódu animace bez Reactu a bez Workeru: zprávy mezi hlavním vláknem a Workerem, sestavení zdroje modulu,
// kontrola exportů, text chyby a kontrola konceptu z editoru kódu. Sdílí ho host, worker i editor.
import { MAX_CODE_SOURCE, type CodeSpec, type StateRecord, type Storyboard } from "./storyboard-model";

export const SLOW_PAINT_MS = 50;
/** Globály, které worker před importem modulu zahodí: kód animace nesmí na síť ani načítat další skripty. */
export const BLOCKED_GLOBALS = ["fetch", "XMLHttpRequest", "importScripts", "WebSocket"] as const;

export type PaintRequest = { state: StateRecord; t: number; board: Storyboard; visible: string[]; width: number; height: number };
/** Obrázky podkladů pro worker: `assets[].id` → ImageBitmap (přenáší se, host je vyrábí znovu z načteného obrázku). */
export type AssetBitmaps = { id: string; bitmap: ImageBitmap }[];
export type WorkerRequest =
  | { type: "load"; id: number; source: string }
  | { type: "assets"; id: number; images: AssetBitmaps }
  | ({ type: "paint"; id: number } & PaintRequest);
export type WorkerReply =
  | { type: "loaded"; id: number }
  | { type: "frame"; id: number; bitmap: ImageBitmap }
  | { type: "slow"; id: number; ms: number }
  | { type: "error"; id: number; message: string };

export type AnimationModule = { paint: (...args: unknown[]) => unknown; fields: unknown; layers: unknown; defaults?: unknown };

/** Text, který worker předá `import()` přes Blob URL; sourceURL zlepší hlášení chyb. */
export const buildModuleSource = (source: string): string => `${source}\n//# sourceURL=opora-animation.js\n`;

/** Statický import nebo vnořený Worker v kódu animace: CSP workeru (`script-src blob:`) je zablokuje, tohle dá českou větu dřív. */
export function forbiddenImport(source: string): string | null {
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  if (/^\s*import\s/m.test(stripped) || /\bimport\s*\(/.test(stripped)) return "Kód animace nesmí nic importovat (import, import()).";
  if (/\bnew\s+(Shared)?Worker\s*\(/.test(stripped)) return "Kód animace nesmí spouštět další Worker.";
  return null;
}

/** Chybějící nebo špatné exporty modulu jako česká zpráva; null = modul je použitelný. */
export function checkExports(mod: Record<string, unknown>): string | null {
  if (typeof mod.paint !== "function") return "Modul musí exportovat funkci paint(ctx, W, H, state, t, board, visible).";
  if (!Array.isArray(mod.fields)) return "Modul musí exportovat pole fields.";
  if (!Array.isArray(mod.layers)) return "Modul musí exportovat pole layers.";
  return null;
}

export function describeError(error: unknown): string {
  if (error instanceof Error) return error.message || error.name;
  return typeof error === "string" ? error : "neznámá chyba";
}

const KINDS = ["number", "color", "boolean", "string"];
const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Pole stavu a vrstvy z JSON textu konceptu (editor kódu i scény); chyba jako česká věta. */
export function parseShape(fieldsText: string, layersText: string): { fields: CodeSpec["fields"]; layers: CodeSpec["layers"] } | { error: string } {
  let fields: unknown, layers: unknown;
  try { fields = JSON.parse(fieldsText); } catch { return { error: "Pole fields nejsou platný JSON." }; }
  try { layers = JSON.parse(layersText); } catch { return { error: "Pole layers nejsou platný JSON." }; }
  if (!Array.isArray(fields) || fields.some((f) => !isObject(f) || typeof f.key !== "string" || typeof f.label !== "string" || !KINDS.includes(String(f.kind))))
    return { error: "Každé pole fields musí mít key, label a kind (number, color, boolean, string)." };
  if (!Array.isArray(layers) || layers.some((l) => !isObject(l) || typeof l.id !== "string" || typeof l.label !== "string"))
    return { error: "Každá vrstva musí mít id a label." };
  return { fields: fields as CodeSpec["fields"], layers: layers as CodeSpec["layers"] };
}

/** Koncept z editoru kódu (text zdroje, název, JSON polí a vrstev) na `CodeSpec`; chyba jako česká věta. */
export function parseCodeDraft(draft: { source: string; title: string; fields: string; layers: string }): { code: CodeSpec } | { error: string } {
  if (!draft.source.trim()) return { error: "Zdroj kódu je prázdný." };
  if (draft.source.length > MAX_CODE_SOURCE) return { error: "Zdroj kódu je delší než 64 kB." };
  const shape = parseShape(draft.fields, draft.layers);
  if ("error" in shape) return shape;
  return { code: { source: draft.source, title: draft.title, ...shape } };
}
