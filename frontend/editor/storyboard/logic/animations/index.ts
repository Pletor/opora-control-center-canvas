// Registr animací: storyboard nese jen id a stav momentů, vzhled a pole stavu určuje animace.
import type { Storyboard, StateRecord } from "../storyboard-model";
import { kulicka } from "./kulicka";
import { ritualBoduNula } from "./ritual-bodu-nula";

export type Field = { key: string; label: string; kind: "number" | "color" | "boolean" | "string"; min?: number; max?: number; step?: number };
export type AnimationDef = {
  id: string;
  label: string;
  fields: Field[];
  /** Vrstvy odspodu nahoru; editor je ukazuje v pásu vrstev a smí je schovat. */
  layers: { id: string; label: string }[];
  /** Textová podoba animace: samostatný ES modul bez importů (`fields`, `layers`, `defaults`, `paint`) v kontraktu Workeru. */
  source: string;
  defaults(): Storyboard;
  /** Vlastní interpolace stavů; u je už po ease. Bez ní platí výchozí (čísla a barvy lerp, ostatní drží). */
  interpolate?: (a: StateRecord, b: StateRecord, u: number) => StateRecord;
  /** Webová scéna (`animation: "scena"`): dokument pro iframe, podklady jako data URL a hlášení chyb; `paint` pak nic nekreslí. */
  scene?: SceneDef;
  paint(ctx: CanvasRenderingContext2D, W: number, H: number, state: StateRecord, t: number, board: Storyboard, visible: ReadonlySet<string>, images?: AssetImages): void;
};
export type SceneDef = {
  /** Hotový `srcdoc` (`sceneDocument(html)`): CSP a runtime už vložené. */
  srcdoc: string;
  /** Podklady podle `assets[].id` jako data URL (`window.STORYBOARD_ASSETS`). */
  assets: Readonly<Record<string, string>>;
  /** Chyba z iframe (výjimka v seek, chyba stránky); patří do pásu vrstev. */
  onError?: (message: string) => void;
};
/** Obrázky podkladů podle `assets[].id`; u kódu animace je Worker dostane z hosta, render balíček ze souborů vedle stránky. */
export type AssetImages = Readonly<Record<string, ImageBitmap | HTMLImageElement>>;

export const ANIMATIONS: Record<string, AnimationDef> = { [kulicka.id]: kulicka, [ritualBoduNula.id]: ritualBoduNula };
export const animationOf = (id: string): AnimationDef | undefined => ANIMATIONS[id];
